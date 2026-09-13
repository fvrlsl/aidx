"""小程序端接口 /api/v1"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    CASE_TYPES,
    DIMENSIONS,
    FEEDBACK_TYPES,
    IDENTITY_CLAIMS,
    OVERALL_LEVELS,
    RATING_RULES_TEXT,
    USER_LEVELS,
)
from app.db import get_db
from app.models import (
    CaseArticle,
    Evidence,
    Merchant,
    MerchantFeedback,
    ProductBarcode,
    RatingSnapshot,
    User,
    UserRating,
    UserTip,
)
from app.schemas import (
    FeedbackIn,
    LoginIn,
    MerchantCreateIn,
    RatingIn,
    TipIn,
    serialize_case,
    serialize_evidence,
    serialize_merchant_brief,
    serialize_merchant_detail,
)
from app.services import anti_spam, entity_match, wechat
from app.services.rating_engine import public_level
from app.services.security import client_ip_hash, create_token, get_current_user, get_optional_user, sha256
from app.services.sharecard import render_merchant_card
from app.services.storage import storage

router = APIRouter(prefix="/api/v1", tags=["miniprogram"])


def _latest_snap(db: Session, merchant_id: int) -> RatingSnapshot | None:
    return db.execute(
        select(RatingSnapshot).where(RatingSnapshot.merchant_id == merchant_id, RatingSnapshot.is_latest.is_(True))
    ).scalar_one_or_none()


def _published_merchant(db: Session, merchant_id: int) -> Merchant:
    m = db.get(Merchant, merchant_id, options=[selectinload(Merchant.aliases)])
    if not m:
        raise HTTPException(404, "商家不存在")
    if m.status == "merged" and m.merged_into_id:
        raise HTTPException(status_code=301, detail={"merged_into": m.merged_into_id})
    return m


# ------------------------------------------------------------ 元数据
@router.get("/meta")
def meta():
    return {
        "dimensions": DIMENSIONS,
        "overall_levels": OVERALL_LEVELS,
        "user_levels": USER_LEVELS,
        "identity_claims": IDENTITY_CLAIMS,
        "feedback_types": FEEDBACK_TYPES,
        "case_types": CASE_TYPES,
    }


@router.get("/rating-rules")
def rating_rules():
    return {"markdown": RATING_RULES_TEXT.strip()}


# ------------------------------------------------------------ 登录
@router.post("/auth/login")
async def login(body: LoginIn, db: Session = Depends(get_db)):
    try:
        session = await wechat.code2session(body.code)
    except wechat.WeChatError as e:
        raise HTTPException(400, f"微信登录失败：{e}") from e
    user = db.execute(select(User).where(User.openid == session["openid"])).scalar_one_or_none()
    if not user:
        user = User(openid=session["openid"], unionid=session.get("unionid"), nickname=body.nickname, avatar=body.avatar)
        db.add(user)
        db.flush()
    else:
        user.last_active_at = datetime.now(timezone.utc)
        if body.nickname:
            user.nickname = body.nickname
    db.commit()
    return {"token": create_token(str(user.id), "user"), "user": {"id": user.id, "nickname": user.nickname}}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rated = db.execute(select(func.count()).select_from(UserRating).where(UserRating.user_id == user.id)).scalar_one()
    tips = db.execute(select(func.count()).select_from(UserTip).where(UserTip.user_id == user.id)).scalar_one()
    return {"id": user.id, "nickname": user.nickname, "avatar": user.avatar, "rating_count": rated, "tip_count": tips}


# ------------------------------------------------------------ 商家
@router.get("/merchants/search")
def search_merchants(q: str = Query(min_length=1, max_length=50), db: Session = Depends(get_db)):
    hits = entity_match.search(db, q, limit=10)
    if not hits:
        return {"items": [], "suggest_create": True}
    ids = [h["merchant_id"] for h in hits]
    merchants = {m.id: m for m in db.execute(select(Merchant).where(Merchant.id.in_(ids))).scalars()}
    items = [
        serialize_merchant_brief(merchants[h["merchant_id"]], extra={"score": h["score"], "matched_alias": h["matched_alias"]})
        for h in hits
        if h["merchant_id"] in merchants
    ]
    return {"items": items, "suggest_create": hits[0]["score"] < 80}


@router.get("/merchants/by-barcode/{barcode}")
def by_barcode(barcode: str, db: Session = Depends(get_db)):
    row = db.get(ProductBarcode, barcode)
    if not row or not row.merchant_id:
        raise HTTPException(404, "暂未收录该条码，可手动搜索品牌")
    m = _published_merchant(db, row.merchant_id)
    return {"product_name": row.product_name, "merchant": serialize_merchant_brief(m)}


@router.get("/merchants/{merchant_id}")
def merchant_detail(merchant_id: int, db: Session = Depends(get_db)):
    m = _published_merchant(db, merchant_id)
    return serialize_merchant_detail(m, _latest_snap(db, m.id))


@router.get("/merchants/{merchant_id}/evidence")
def merchant_evidence(
    merchant_id: int,
    dimension: str | None = None,
    page: int = 1,
    page_size: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
):
    stmt = select(Evidence).where(Evidence.merchant_id == merchant_id, Evidence.status == "approved")
    if dimension:
        stmt = stmt.where(Evidence.dimension == dimension)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.options(selectinload(Evidence.raw_source))
        .order_by(Evidence.event_date.desc().nullslast(), Evidence.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    return {"items": [serialize_evidence(e) for e in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/merchants/{merchant_id}/ratings/summary")
def ratings_summary(merchant_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    base = select(UserRating).where(UserRating.merchant_id == merchant_id)
    dist_rows = db.execute(
        select(UserRating.level, func.sum(UserRating.weight)).where(UserRating.merchant_id == merchant_id).group_by(UserRating.level)
    ).all()
    dist = {lvl: 0.0 for lvl in USER_LEVELS}
    for lvl, w in dist_rows:
        dist[lvl] = round(float(w or 0), 1)
    total_w = sum(dist.values())

    identity_rows = db.execute(
        select(UserRating.identity_claim, func.count()).where(UserRating.merchant_id == merchant_id).group_by(UserRating.identity_claim)
    ).all()
    identity = {k: 0 for k in IDENTITY_CLAIMS}
    for k, n in identity_rows:
        identity[k] = n

    comments = db.execute(
        base.where(UserRating.comment_status == "approved", UserRating.comment.isnot(None))
        .options(selectinload(UserRating.user))
        .order_by(UserRating.updated_at.desc())
        .limit(5)
    ).scalars()

    mine = None
    if user:
        r = db.execute(base.where(UserRating.user_id == user.id)).scalar_one_or_none()
        if r:
            mine = {"level": r.level, "identity_claim": r.identity_claim, "comment": r.comment, "comment_status": r.comment_status}

    return {
        "total": int(sum(n for _, n in identity_rows)),
        "distribution": [
            {"level": lvl, "label": USER_LEVELS[lvl], "weight": dist[lvl], "percent": round(dist[lvl] / total_w * 100) if total_w else 0}
            for lvl in sorted(USER_LEVELS, reverse=True)
        ],
        "identity": [{"key": k, "label": IDENTITY_CLAIMS[k], "count": identity[k]} for k in IDENTITY_CLAIMS],
        "comments": [
            {
                "level": c.level,
                "level_label": USER_LEVELS[c.level],
                "identity_label": IDENTITY_CLAIMS.get(c.identity_claim, ""),
                "comment": c.comment,
                "nickname": (c.user.nickname or "微信用户") if c.user else "微信用户",
                "created_at": c.updated_at,
            }
            for c in comments
        ],
        "mine": mine,
        "disclaimer": "用户评价未经核实，不参与平台评级计算",
    }


@router.post("/merchants", status_code=201)
def create_merchant(body: MerchantCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户补充商家：先做一次模糊匹配提示；确认已有商家则挂 pending 别名，否则建 pending 实体。"""
    if body.confirm_merchant_id:
        m = _published_merchant(db, body.confirm_merchant_id)
        entity_match.add_alias(db, m.id, body.name, source="user", status="pending")
        db.commit()
        return {"action": "alias_added", "merchant": serialize_merchant_brief(m)}

    candidates = entity_match.search(db, body.name, limit=3)
    if candidates and candidates[0]["score"] >= 80:
        ms = {m.id: m for m in db.execute(select(Merchant).where(Merchant.id.in_([c["merchant_id"] for c in candidates]))).scalars()}
        return {
            "action": "confirm_needed",
            "candidates": [serialize_merchant_brief(ms[c["merchant_id"]], extra={"score": c["score"]}) for c in candidates if c["merchant_id"] in ms],
        }

    m = Merchant(canonical_name=body.name.strip(), industry=body.industry, status="pending", created_by="user", creator_user_id=user.id)
    db.add(m)
    db.flush()
    entity_match.add_alias(db, m.id, body.name, source="user", status="active")
    db.commit()
    return {"action": "created_pending", "merchant": {"id": m.id, "name": m.canonical_name, "status": m.status}}


# ------------------------------------------------------------ 打分
@router.put("/ratings/{merchant_id}")
async def rate_merchant(
    merchant_id: int,
    body: RatingIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        body.validate_claim()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    m = db.get(Merchant, merchant_id)
    if not m or m.status not in ("published", "pending"):
        raise HTTPException(404, "商家不存在")

    ip_hash = client_ip_hash(request)
    device_hash = sha256(body.device_hash) if body.device_hash else None
    try:
        weight = anti_spam.check_rating_allowed(db, user, merchant_id, device_hash, ip_hash)
    except anti_spam.RateLimited as e:
        raise HTTPException(429, e.message) from e

    comment = (body.comment or "").strip() or None
    comment_status = "pending"
    if comment and not await wechat.msg_sec_check(comment, user.openid):
        raise HTTPException(422, "评论包含不适宜内容，请修改后再提交")

    row = db.execute(
        select(UserRating).where(UserRating.user_id == user.id, UserRating.merchant_id == merchant_id)
    ).scalar_one_or_none()
    if row:
        row.history = (row.history or []) + [{"level": row.level, "at": datetime.now(timezone.utc).isoformat()}]
        row.level, row.identity_claim, row.comment = body.level, body.identity_claim, comment
        row.comment_status = comment_status if comment else "pending"
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = UserRating(
            user_id=user.id,
            merchant_id=merchant_id,
            level=body.level,
            identity_claim=body.identity_claim,
            comment=comment,
            comment_status=comment_status,
            device_hash=device_hash,
            ip_hash=ip_hash,
            weight=weight,
        )
        db.add(row)
    db.commit()
    burst = anti_spam.burst_detected(db, merchant_id)
    return {
        "ok": True,
        "message": "已收到，评分立即计入统计，文字审核后展示" if comment else "已收到你的评分",
        "observing": burst,
    }


# ------------------------------------------------------------ 案例 / 榜单
@router.get("/cases")
def list_cases(type: str | None = None, page: int = 1, page_size: int = Query(default=10, le=30), db: Session = Depends(get_db)):
    stmt = select(CaseArticle).where(CaseArticle.status == "published")
    if type:
        stmt = stmt.where(CaseArticle.type == type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(CaseArticle.published_at.desc()).offset((page - 1) * page_size).limit(page_size)).scalars()
    return {"items": [serialize_case(c) for c in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/cases/{case_id}")
def case_detail(case_id: int, db: Session = Depends(get_db)):
    c = db.get(CaseArticle, case_id)
    if not c or c.status != "published":
        raise HTTPException(404, "案例不存在")
    c.view_count += 1
    merchants = []
    if c.merchant_ids:
        for m in db.execute(select(Merchant).where(Merchant.id.in_(c.merchant_ids))).scalars():
            merchants.append(serialize_merchant_brief(m, _latest_snap(db, m.id)))
    db.commit()
    return serialize_case(c, merchants, with_body=True)


@router.get("/rankings")
def rankings(type: str = "benchmark", industry: str | None = None, limit: int = Query(default=20, le=50), db: Session = Depends(get_db)):
    """type: benchmark（标杆榜，按分数降序）| disputed（争议榜，按分数升序）"""
    stmt = (
        select(Merchant, RatingSnapshot)
        .join(RatingSnapshot, (RatingSnapshot.merchant_id == Merchant.id) & RatingSnapshot.is_latest.is_(True))
        .where(Merchant.status == "published", RatingSnapshot.overall_level != "insufficient")
    )
    if industry:
        stmt = stmt.where(Merchant.industry == industry)
    if type == "disputed":
        stmt = stmt.where(RatingSnapshot.overall_level.in_(["disputed", "severe"])).order_by(RatingSnapshot.overall_score.asc())
    else:
        stmt = stmt.where(RatingSnapshot.overall_level.in_(["benchmark", "good"])).order_by(RatingSnapshot.overall_score.desc())
    rows = db.execute(stmt.limit(limit)).all()
    industries = [r[0] for r in db.execute(select(Merchant.industry).where(Merchant.industry.isnot(None)).distinct()).all()]
    return {
        "type": type,
        "items": [serialize_merchant_brief(m, s, extra={"score": s.overall_score, "rank": i + 1}) for i, (m, s) in enumerate(rows)],
        "industries": industries,
    }


# ------------------------------------------------------------ 线索 / 反馈 / 上传
@router.post("/tips", status_code=201)
async def create_tip(body: TipIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (body.url or body.text or body.images):
        raise HTTPException(422, "请至少提供链接、文字或图片之一")
    if body.text and not await wechat.msg_sec_check(body.text, user.openid):
        raise HTTPException(422, "内容包含不适宜信息")
    tip = UserTip(user_id=user.id, **body.model_dump())
    db.add(tip)
    db.commit()
    return {"id": tip.id, "message": "线索已提交，采纳后会在商家页展示"}


@router.get("/tips/mine")
def my_tips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(UserTip).where(UserTip.user_id == user.id).order_by(UserTip.id.desc()).limit(50)).scalars()
    return {"items": [{"id": t.id, "merchant_name_raw": t.merchant_name_raw, "url": t.url, "text": t.text, "status": t.status, "created_at": t.created_at} for t in rows]}


@router.post("/feedback", status_code=201)
def create_feedback(body: FeedbackIn, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    if body.type not in FEEDBACK_TYPES:
        raise HTTPException(422, "反馈类型无效")
    if not db.get(Merchant, body.merchant_id):
        raise HTTPException(404, "商家不存在")
    ticket_no = f"FB{datetime.now(timezone.utc):%Y%m%d}{uuid.uuid4().hex[:6].upper()}"
    fb = MerchantFeedback(user_id=user.id if user else None, ticket_no=ticket_no, **body.model_dump())
    db.add(fb)
    db.commit()
    return {"ticket_no": ticket_no, "message": "已收到，我们将在 3 个工作日内首次响应"}


@router.get("/feedback/{ticket_no}")
def feedback_status(ticket_no: str, phone: str, db: Session = Depends(get_db)):
    fb = db.execute(select(MerchantFeedback).where(MerchantFeedback.ticket_no == ticket_no)).scalar_one_or_none()
    if not fb or fb.contact_phone != phone:
        raise HTTPException(404, "工单不存在或手机号不匹配")
    return {"ticket_no": fb.ticket_no, "status": fb.status, "type": fb.type, "reply": fb.reply, "replied_at": fb.replied_at, "created_at": fb.created_at}


@router.get("/feedback/mine/list")
def my_feedback(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(MerchantFeedback).where(MerchantFeedback.user_id == user.id).order_by(MerchantFeedback.id.desc())).scalars()
    return {"items": [{"ticket_no": f.ticket_no, "status": f.status, "type": FEEDBACK_TYPES.get(f.type, f.type), "reply": f.reply, "created_at": f.created_at} for f in rows]}


@router.post("/uploads/presign")
def presign(ext: str = "jpg", content_type: str = "image/jpeg", user: User = Depends(get_current_user)):
    return storage.presign_upload(ext, prefix="uploads", content_type=content_type)


@router.post("/uploads")
async def upload(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 5MB")
    ext = (file.filename or "bin").rsplit(".", 1)[-1].lower()
    url = storage.put_bytes(data, ext, prefix="uploads", content_type=file.content_type or "application/octet-stream")
    return {"file_url": url}


# ------------------------------------------------------------ 分享卡片
@router.get("/share-card/merchant/{merchant_id}")
def merchant_share_card(merchant_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    m = _published_merchant(db, merchant_id)
    snap = _latest_snap(db, m.id)
    cache_key = f"card:{m.id}:{snap.id if snap else 0}"
    cached = anti_spam.counter._redis.get(cache_key) if anti_spam.counter._redis and not refresh else None
    if cached:
        return {"url": cached}
    facts = [
        e.summary
        for e in db.execute(
            select(Evidence).where(Evidence.merchant_id == m.id, Evidence.status == "approved", Evidence.source_level.in_(["A", "B"]))
            .order_by(Evidence.impact.desc(), Evidence.event_date.desc().nullslast())
            .limit(3)
        ).scalars()
    ]
    updated = (snap.computed_at if snap else m.updated_at).strftime("%Y-%m-%d")
    url = render_merchant_card(m.canonical_name, public_level(snap), facts, updated)
    if anti_spam.counter._redis:
        anti_spam.counter._redis.set(cache_key, url, ex=86400 * 7)
    return {"url": url}
