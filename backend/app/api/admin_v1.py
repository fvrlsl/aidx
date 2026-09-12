"""运营后台接口 /admin/v1"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.constants import DIMENSIONS, FEEDBACK_TYPES, OVERALL_LEVELS
from app.db import get_db
from app.models import (
    AdminUser,
    CaseArticle,
    Evidence,
    HotWatchlist,
    Merchant,
    MerchantAlias,
    MerchantFeedback,
    MergeLog,
    RatingSnapshot,
    RawSource,
    UserRating,
    UserTip,
)
from app.pipeline import crawlers, tasks
from app.schemas import (
    AdminLoginIn,
    CaseUpsertIn,
    ClipIn,
    EvidenceReviewIn,
    EvidenceUpsertIn,
    FeedbackHandleIn,
    ImportRowIn,
    MergeIn,
    MerchantUpsertIn,
    SnapshotConfirmIn,
    UserRatingReviewIn,
    WatchlistUpsertIn,
    serialize_case,
    serialize_evidence,
    serialize_merchant_brief,
    serialize_rating,
)
from app.services import audit, entity_match
from app.services.rating_engine import recompute_merchant
from app.services.security import create_token, get_current_admin, verify_password

router = APIRouter(prefix="/admin/v1", tags=["admin"], dependencies=[])


def _paginate(db: Session, stmt, page: int, page_size: int):
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return rows, total


# ------------------------------------------------------------ 登录
@router.post("/auth/login")
def admin_login(body: AdminLoginIn, db: Session = Depends(get_db)):
    admin = db.execute(select(AdminUser).where(AdminUser.username == body.username)).scalar_one_or_none()
    if not admin or not admin.enabled or not verify_password(body.password, admin.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return {"token": create_token(str(admin.id), "admin", {"role": admin.role}), "username": admin.username, "role": admin.role}


@router.get("/me")
def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return {"username": admin.username, "role": admin.role}


# ------------------------------------------------------------ 看板
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    def count(model, *conds):
        stmt = select(func.count()).select_from(model)
        for c in conds:
            stmt = stmt.where(c)
        return db.execute(stmt).scalar_one()

    return {
        "merchants": count(Merchant, Merchant.status == "published"),
        "merchants_pending": count(Merchant, Merchant.status == "pending"),
        "sources_new": count(RawSource, RawSource.status.in_(["new", "failed"])),
        "sources_unassigned": count(RawSource, RawSource.status == "used", RawSource.extraction.isnot(None)),
        "evidence_draft": count(Evidence, Evidence.status == "draft"),
        "ratings_need_confirm": count(RatingSnapshot, RatingSnapshot.is_latest.is_(True), RatingSnapshot.needs_confirm.is_(True)),
        "comments_pending": count(UserRating, UserRating.comment_status == "pending", UserRating.comment.isnot(None)),
        "feedback_open": count(MerchantFeedback, MerchantFeedback.status.in_(["new", "reviewing"])),
        "tips_new": count(UserTip, UserTip.status == "new"),
        "level_distribution": {
            OVERALL_LEVELS[k]: v
            for k, v in db.execute(
                select(RatingSnapshot.overall_level, func.count()).where(RatingSnapshot.is_latest.is_(True)).group_by(RatingSnapshot.overall_level)
            ).all()
        },
    }


# ------------------------------------------------------------ 素材池
@router.get("/sources")
def list_sources(status: str | None = None, level: str | None = None, q: str | None = None, page: int = 1, page_size: int = 20,
                 db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    stmt = select(RawSource).order_by(RawSource.id.desc())
    if status:
        stmt = stmt.where(RawSource.status == status)
    if level:
        stmt = stmt.where(RawSource.source_level == level)
    if q:
        stmt = stmt.where(RawSource.title.ilike(f"%{q}%"))
    rows, total = _paginate(db, stmt, page, page_size)
    return {"items": [_source_out(s) for s in rows], "total": total}


def _source_out(s: RawSource) -> dict:
    return {
        "id": s.id, "url": s.url, "title": s.title, "publisher": s.publisher, "source_level": s.source_level,
        "published_at": s.published_at, "fetched_at": s.fetched_at, "summary": s.summary, "status": s.status,
        "origin": s.origin, "extraction": s.extraction, "error": s.error, "event_group_id": s.event_group_id,
    }


@router.post("/sources/clip", status_code=201)
def clip_source(body: ClipIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """剪藏：粘贴链接 → 自动抓元信息 → 入素材池 → （可选）立即跑管道。"""
    meta = crawlers.fetch_page_meta(body.url) if not (body.title and body.summary) else {}
    src = tasks.ingest_source(
        db, url=body.url, title=body.title or meta.get("title") or body.url, source_level=body.source_level,
        publisher=body.publisher or meta.get("publisher"), summary=body.summary or meta.get("summary"),
        published_at=meta.get("published_at"), origin="manual",
    )
    if not src:
        raise HTTPException(409, "该链接已在素材池中")
    db.commit()
    audit.log(db, admin.username, "clip", "raw_source", src.id, after={"url": body.url})
    db.commit()
    result = tasks.process_source_task.delay(src.id).get() if body.process_now else None
    db.refresh(src)
    return {"source": _source_out(src), "pipeline": result, "fetch_error": meta.get("error")}


@router.post("/sources/{source_id}/process")
def reprocess_source(source_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    src = db.get(RawSource, source_id)
    if not src:
        raise HTTPException(404)
    src.status, src.error = "new", None
    db.commit()
    return {"pipeline": tasks.process_source_task.delay(source_id).get()}


@router.post("/sources/{source_id}/assign")
def assign_source(source_id: int, merchant_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """待归属素材人工指定商家：把抽取结果落成依据草稿，并把抽取出的名字挂为别名。"""
    src = db.get(RawSource, source_id)
    if not src or not src.extraction:
        raise HTTPException(404, "素材不存在或尚未抽取")
    if not db.get(Merchant, merchant_id):
        raise HTTPException(404, "商家不存在")
    ex = src.extraction
    for p in ex.get("pending_entities", []):
        entity_match.add_alias(db, merchant_id, p["name"], source="editor")
    polarity = 1 if int(ex.get("polarity", 1)) > 0 else -1
    ev = Evidence(
        merchant_id=merchant_id, raw_source_id=src.id, dimension=ex.get("dimension", "disputes"), polarity=polarity,
        impact=max(1, min(2, abs(int(ex.get("impact") or 1)))) * polarity, summary=(ex.get("summary") or src.title)[:300],
        event_date=src.published_at.date() if src.published_at else None, source_level=src.source_level,
        source_name=src.publisher, source_url=src.url, confidence=ex.get("confidence"), status="draft",
    )
    db.add(ev)
    src.extraction = {**ex, "matched_merchant_ids": [merchant_id], "pending_entities": []}
    db.commit()
    return {"evidence_id": ev.id}


@router.post("/sources/import", status_code=201)
def import_rows(rows: list[ImportRowIn], db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """A 级半自动导入：运营从政务站点下载/整理后的行数据，直接生成已发布依据。"""
    created, unmatched = 0, []
    touched: set[int] = set()
    for r in rows:
        mid, _ = entity_match.resolve(db, r.merchant_name)
        if not mid:
            unmatched.append(r.merchant_name)
            continue
        src = tasks.ingest_source(db, url=r.source_url, title=r.summary[:200], source_level=r.source_level,
                                  publisher=r.source_name, summary=r.summary, origin="import")
        if src:
            src.status = "used"
        db.add(Evidence(
            merchant_id=mid, raw_source_id=src.id if src else None, dimension=r.dimension, polarity=1 if r.polarity > 0 else -1,
            impact=r.impact if r.polarity > 0 else -abs(r.impact), summary=r.summary[:300], event_date=r.event_date,
            source_level=r.source_level, source_name=r.source_name, source_url=r.source_url,
            status="approved", reviewed_by=admin.username, reviewed_at=datetime.now(timezone.utc),
        ))
        touched.add(mid)
        created += 1
    for mid in touched:
        recompute_merchant(db, mid)
    db.commit()
    return {"created": created, "unmatched": unmatched}


# ------------------------------------------------------------ 依据
@router.get("/evidence")
def list_evidence(status: str = "draft", merchant_id: int | None = None, page: int = 1, page_size: int = 20,
                  db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    stmt = select(Evidence).options(selectinload(Evidence.merchant), selectinload(Evidence.raw_source)).order_by(Evidence.id.desc())
    if status:
        stmt = stmt.where(Evidence.status == status)
    if merchant_id:
        stmt = stmt.where(Evidence.merchant_id == merchant_id)
    rows, total = _paginate(db, stmt, page, page_size)
    return {"items": [{**serialize_evidence(e), "merchant_name": e.merchant.canonical_name} for e in rows], "total": total}


@router.post("/evidence", status_code=201)
def create_evidence(body: EvidenceUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if body.dimension not in DIMENSIONS:
        raise HTTPException(422, "维度无效")
    ev = Evidence(**body.model_dump(), status="approved", reviewed_by=admin.username, reviewed_at=datetime.now(timezone.utc))
    ev.impact = abs(ev.impact) * (1 if ev.polarity > 0 else -1)
    db.add(ev)
    db.flush()
    recompute_merchant(db, ev.merchant_id, operator=admin.username)
    audit.log(db, admin.username, "create", "evidence", ev.id, after=body.model_dump(mode="json"))
    db.commit()
    return serialize_evidence(ev)


@router.post("/evidence/{evidence_id}/review")
def review_evidence(evidence_id: int, body: EvidenceReviewIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    ev = db.get(Evidence, evidence_id)
    if not ev:
        raise HTTPException(404)
    before = serialize_evidence(ev)
    if body.patch:
        for k, v in body.patch.model_dump(exclude={"merchant_id", "raw_source_id"}).items():
            setattr(ev, k, v)
        ev.impact = abs(ev.impact) * (1 if ev.polarity > 0 else -1)
    if body.action == "approve":
        ev.status = "approved"
    elif body.action == "reject":
        ev.status = "rejected"
    elif body.action == "archive":
        ev.status = "archived"
    else:
        raise HTTPException(422, "action 无效")
    ev.reviewed_by, ev.reviewed_at = admin.username, datetime.now(timezone.utc)
    db.flush()
    recompute_merchant(db, ev.merchant_id, operator=admin.username)
    audit.log(db, admin.username, f"review:{body.action}", "evidence", ev.id, before=_json(before), after=_json(serialize_evidence(ev)))
    db.commit()
    return serialize_evidence(ev)


def _json(d: dict) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}


# ------------------------------------------------------------ 实体
@router.get("/merchants")
def admin_merchants(q: str | None = None, status: str | None = None, page: int = 1, page_size: int = 20,
                    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    stmt = select(Merchant).options(selectinload(Merchant.aliases), selectinload(Merchant.latest_rating)).order_by(Merchant.id.desc())
    if status:
        stmt = stmt.where(Merchant.status == status)
    if q:
        ids = [h["merchant_id"] for h in entity_match.search(db, q, limit=50, min_score=50)]
        stmt = stmt.where(Merchant.id.in_(ids) | Merchant.canonical_name.ilike(f"%{q}%"))
    rows, total = _paginate(db, stmt, page, page_size)
    return {
        "items": [
            serialize_merchant_brief(m, extra={
                "aliases": [{"id": a.id, "alias": a.alias, "status": a.status, "source": a.source} for a in m.aliases],
                "created_by": m.created_by, "intro": m.intro, "type": m.type, "unified_social_credit_code": m.unified_social_credit_code,
                "rating": serialize_rating(m.latest_rating),
            })
            for m in rows
        ],
        "total": total,
    }


@router.post("/merchants", status_code=201)
def admin_create_merchant(body: MerchantUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = Merchant(**body.model_dump(exclude={"aliases"}), created_by="editor")
    db.add(m)
    db.flush()
    for a in {body.canonical_name, *body.aliases}:
        entity_match.add_alias(db, m.id, a)
    recompute_merchant(db, m.id, operator=admin.username)
    audit.log(db, admin.username, "create", "merchant", m.id, after=body.model_dump())
    db.commit()
    return {"id": m.id}


@router.put("/merchants/{merchant_id}")
def admin_update_merchant(merchant_id: int, body: MerchantUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude={"aliases"}).items():
        setattr(m, k, v)
    for a in {body.canonical_name, *body.aliases}:
        entity_match.add_alias(db, m.id, a)
    db.commit()
    return {"ok": True}


@router.post("/merchants/{merchant_id}/aliases/{alias_id}/{action}")
def alias_action(merchant_id: int, alias_id: int, action: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    a = db.get(MerchantAlias, alias_id)
    if not a or a.merchant_id != merchant_id:
        raise HTTPException(404)
    if action == "approve":
        a.status = "active"
    elif action == "delete":
        db.delete(a)
    else:
        raise HTTPException(422)
    db.commit()
    return {"ok": True}


@router.post("/merchants/merge")
def merge_merchants(body: MergeIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if body.from_id == body.to_id:
        raise HTTPException(422, "不能合并到自身")
    src, dst = db.get(Merchant, body.from_id), db.get(Merchant, body.to_id)
    if not src or not dst or dst.status == "merged":
        raise HTTPException(404, "商家不存在")
    for a in list(src.aliases):
        entity_match.add_alias(db, dst.id, a.alias, source=a.source, status=a.status)
        db.delete(a)
    db.execute(update(Evidence).where(Evidence.merchant_id == src.id).values(merchant_id=dst.id))
    # 同一用户在两边都评过分时保留目标侧，删除源侧
    dst_users = {r[0] for r in db.execute(select(UserRating.user_id).where(UserRating.merchant_id == dst.id)).all()}
    for r in db.execute(select(UserRating).where(UserRating.merchant_id == src.id)).scalars().all():
        if r.user_id in dst_users:
            db.delete(r)
        else:
            r.merchant_id = dst.id
    db.execute(update(MerchantFeedback).where(MerchantFeedback.merchant_id == src.id).values(merchant_id=dst.id))
    db.execute(update(UserTip).where(UserTip.merchant_id == src.id).values(merchant_id=dst.id))
    db.execute(update(HotWatchlist).where(HotWatchlist.merchant_id == src.id).values(merchant_id=dst.id))
    db.execute(update(RatingSnapshot).where(RatingSnapshot.merchant_id == src.id).values(is_latest=False))
    src.status, src.merged_into_id = "merged", dst.id
    db.add(MergeLog(from_id=src.id, to_id=dst.id, operator=admin.username, reason=body.reason))
    db.flush()
    recompute_merchant(db, dst.id, operator=admin.username)
    db.commit()
    return {"ok": True, "merged_into": dst.id}


@router.post("/merchants/{merchant_id}/{action}")
def merchant_status_action(merchant_id: int, action: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    m = db.get(Merchant, merchant_id)
    if not m:
        raise HTTPException(404)
    if action == "publish":
        m.status = "published"
        recompute_merchant(db, m.id, operator=admin.username)
    elif action == "reject":
        m.status = "draft"
    elif action == "recompute":
        recompute_merchant(db, m.id, operator=admin.username)
    else:
        raise HTTPException(422)
    audit.log(db, admin.username, action, "merchant", m.id)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ 评级
@router.get("/ratings/pending")
def pending_ratings(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.execute(
        select(RatingSnapshot, Merchant).join(Merchant, Merchant.id == RatingSnapshot.merchant_id)
        .where(RatingSnapshot.is_latest.is_(True), RatingSnapshot.needs_confirm.is_(True)).order_by(RatingSnapshot.computed_at.desc())
    ).all()
    return {"items": [{"snapshot_id": s.id, "merchant_id": m.id, "merchant_name": m.canonical_name, "previous_level": s.previous_level,
                       "previous_label": OVERALL_LEVELS.get(s.previous_level or "", ""), "new_level": s.overall_level,
                       "new_label": OVERALL_LEVELS.get(s.overall_level), "score": s.overall_score, "computed_at": s.computed_at,
                       "dim_levels": s.dim_levels} for s, m in rows]}


@router.post("/ratings/{snapshot_id}/confirm")
def confirm_rating(snapshot_id: int, body: SnapshotConfirmIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    s = db.get(RatingSnapshot, snapshot_id)
    if not s:
        raise HTTPException(404)
    if body.accept:
        s.needs_confirm, s.confirmed_by = False, admin.username
    else:
        # 拒绝：保持对外显示旧档，直到编辑处理依据后再重算
        s.confirmed_by = admin.username
    audit.log(db, admin.username, "confirm_rating" if body.accept else "reject_rating", "rating_snapshot", s.id)
    db.commit()
    return {"ok": True}


@router.get("/ratings/history/{merchant_id}")
def rating_history(merchant_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.execute(select(RatingSnapshot).where(RatingSnapshot.merchant_id == merchant_id).order_by(RatingSnapshot.id.desc()).limit(30)).scalars()
    return {"items": [{**serialize_rating(s), "id": s.id, "is_latest": s.is_latest, "needs_confirm": s.needs_confirm, "confirmed_by": s.confirmed_by} for s in rows]}


# ------------------------------------------------------------ 案例
@router.get("/cases")
def admin_cases(page: int = 1, page_size: int = 20, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows, total = _paginate(db, select(CaseArticle).order_by(CaseArticle.id.desc()), page, page_size)
    return {"items": [serialize_case(c, with_body=True) for c in rows], "total": total}


@router.post("/cases", status_code=201)
def create_case(body: CaseUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = CaseArticle(**body.model_dump())
    if c.status == "published":
        c.published_at = datetime.now(timezone.utc)
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.put("/cases/{case_id}")
def update_case(case_id: int, body: CaseUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    c = db.get(CaseArticle, case_id)
    if not c:
        raise HTTPException(404)
    was_published = c.status == "published"
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    if c.status == "published" and not was_published:
        c.published_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ 用户评价审核
@router.get("/user-ratings")
def admin_user_ratings(comment_status: str = "pending", page: int = 1, page_size: int = 20,
                       db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    stmt = select(UserRating, Merchant).join(Merchant, Merchant.id == UserRating.merchant_id).where(
        UserRating.comment.isnot(None), UserRating.comment_status == comment_status).order_by(UserRating.id.desc())
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": r.id, "merchant_id": m.id, "merchant_name": m.canonical_name, "level": r.level, "identity_claim": r.identity_claim,
                       "comment": r.comment, "comment_status": r.comment_status, "weight": r.weight, "created_at": r.created_at} for r, m in rows],
            "total": total}


@router.post("/user-ratings/{rating_id}/review")
def review_user_rating(rating_id: int, body: UserRatingReviewIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    r = db.get(UserRating, rating_id)
    if not r:
        raise HTTPException(404)
    r.comment_status = body.comment_status
    if body.weight is not None:
        r.weight = body.weight
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------ 工单 / 线索
@router.get("/feedback")
def admin_feedback(status: str | None = None, page: int = 1, page_size: int = 20, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    stmt = select(MerchantFeedback, Merchant).join(Merchant, Merchant.id == MerchantFeedback.merchant_id).order_by(MerchantFeedback.id.desc())
    if status:
        stmt = stmt.where(MerchantFeedback.status == status)
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": f.id, "ticket_no": f.ticket_no, "merchant_id": m.id, "merchant_name": m.canonical_name, "evidence_id": f.evidence_id,
                       "type": f.type, "type_label": FEEDBACK_TYPES.get(f.type, f.type), "contact_name": f.contact_name, "contact_phone": f.contact_phone,
                       "company_name": f.company_name, "proof_files": f.proof_files, "content": f.content, "attachments": f.attachments,
                       "status": f.status, "action": f.action, "reply": f.reply, "handled_by": f.handled_by, "created_at": f.created_at} for f, m in rows],
            "total": total}


@router.post("/feedback/{feedback_id}/handle")
def handle_feedback(feedback_id: int, body: FeedbackHandleIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    f = db.get(MerchantFeedback, feedback_id)
    if not f:
        raise HTTPException(404)
    f.handled_by = admin.username
    if body.status:
        f.status = body.status
    if body.action:
        f.action = body.action
        if body.action == "add_reply" and f.evidence_id and body.reply:
            ev = db.get(Evidence, f.evidence_id)
            if ev:
                ev.merchant_reply = body.reply
    if body.reply:
        f.reply, f.replied_at = body.reply, datetime.now(timezone.utc)
        if f.status == "new":
            f.status = "replied"
    audit.log(db, admin.username, "handle_feedback", "merchant_feedback", f.id, after=body.model_dump())
    db.commit()
    return {"ok": True}


@router.get("/tips")
def admin_tips(status: str = "new", page: int = 1, page_size: int = 20, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows, total = _paginate(db, select(UserTip).where(UserTip.status == status).order_by(UserTip.id.desc()), page, page_size)
    return {"items": [{"id": t.id, "merchant_id": t.merchant_id, "merchant_name_raw": t.merchant_name_raw, "url": t.url, "text": t.text,
                       "images": t.images, "status": t.status, "created_at": t.created_at} for t in rows], "total": total}


@router.post("/tips/{tip_id}/{action}")
def handle_tip(tip_id: int, action: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    """accept：把线索链接推入素材池并跑管道；reject：标记拒绝。"""
    t = db.get(UserTip, tip_id)
    if not t:
        raise HTTPException(404)
    pipeline = None
    if action == "accept":
        t.status = "accepted"
        if t.url:
            src = tasks.ingest_source(db, url=t.url, title=(t.text or t.url)[:200], source_level="D", summary=t.text, origin="user_tip")
            db.commit()
            if src:
                pipeline = tasks.process_source_task.delay(src.id).get()
    elif action == "reject":
        t.status = "rejected"
    else:
        raise HTTPException(422)
    t.handled_by = admin.username
    db.commit()
    return {"ok": True, "pipeline": pipeline}


# ------------------------------------------------------------ 热点监控
@router.get("/watchlist")
def list_watchlist(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = db.execute(select(HotWatchlist).options(selectinload(HotWatchlist.merchant)).order_by(HotWatchlist.priority, HotWatchlist.id)).scalars()
    return {"items": [{"id": w.id, "merchant_id": w.merchant_id, "merchant_name": w.merchant.canonical_name, "keywords": w.keywords,
                       "rss_urls": w.rss_urls, "priority": w.priority, "enabled": w.enabled, "last_hit_at": w.last_hit_at} for w in rows]}


@router.post("/watchlist", status_code=201)
def create_watch(body: WatchlistUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    w = HotWatchlist(**body.model_dump())
    db.add(w)
    db.commit()
    return {"id": w.id}


@router.put("/watchlist/{watch_id}")
def update_watch(watch_id: int, body: WatchlistUpsertIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    w = db.get(HotWatchlist, watch_id)
    if not w:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(w, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/watchlist/{watch_id}")
def delete_watch(watch_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    w = db.get(HotWatchlist, watch_id)
    if w:
        db.delete(w)
        db.commit()
    return {"ok": True}


@router.post("/watchlist/run")
def run_watchlist(priority: str = Query(default="P0"), admin: AdminUser = Depends(get_current_admin)):
    return tasks.monitor_watchlist.delay(priority).get()
