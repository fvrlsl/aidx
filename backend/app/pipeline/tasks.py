"""管道任务：raw_source 入库 → 去重 → 抽取 → 实体匹配 → 依据草稿 → 自动发布 → 评级重算 → 卡片。"""

import logging
from datetime import date, datetime, timezone

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Evidence, HotWatchlist, Merchant, MerchantAlias, RawSource
from app.pipeline import crawlers
from app.pipeline.celery_app import celery
from app.services import entity_match, llm
from app.services.rating_engine import recompute_merchant

log = logging.getLogger("pipeline")


# ------------------------------------------------------------ 入库
def ingest_source(db: Session, *, url: str, title: str, source_level: str, publisher: str | None = None,
                  summary: str | None = None, published_at: datetime | None = None, origin: str = "manual") -> RawSource | None:
    """幂等入库：同 URL 已存在返回 None。"""
    h = crawlers.url_hash(url)
    if db.execute(select(RawSource.id).where(RawSource.url_hash == h)).scalar_one_or_none():
        return None
    row = RawSource(
        url=url, url_hash=h, title=title[:500], publisher=publisher, source_level=source_level,
        summary=summary, published_at=published_at, origin=origin, status="new",
    )
    db.add(row)
    db.flush()
    return row


# ------------------------------------------------------------ 主流程
def _dedup(db: Session, src: RawSource) -> None:
    """标题相似度 ≥ 85 的最近素材归入同一事件组。"""
    recent = db.execute(
        select(RawSource).where(RawSource.id != src.id, RawSource.event_group_id.isnot(None)).order_by(RawSource.id.desc()).limit(500)
    ).scalars().all()
    for other in recent:
        if fuzz.token_set_ratio(src.title, other.title) >= 85:
            src.event_group_id = other.event_group_id
            return
    src.event_group_id = src.id


def _should_auto_publish(polarity: int, source_level: str) -> bool:
    policy = settings.auto_publish_policy
    if policy == "all":
        return True
    if policy == "none":
        return False
    return polarity > 0 or source_level == "A"


def process_source(db: Session, src: RawSource) -> dict:
    src.status = "processing"
    db.flush()

    _dedup(db, src)

    known_names = [r[0] for r in db.execute(select(MerchantAlias.alias).where(MerchantAlias.status == "active")).all()]
    result = llm.extract(src.title, src.summary, src.publisher, known_names)
    src.extraction = result

    if result.get("dimension") in (None, "none") or not result.get("polarity"):
        src.status = "discarded"
        src.error = "与员工待遇无关或无法判断维度"
        return {"status": "discarded"}

    matched: list[int] = []
    pending: list[dict] = []
    for name in result.get("merchants") or []:
        merchant_id, candidates = entity_match.resolve(db, name)
        if merchant_id:
            matched.append(merchant_id)
        else:
            pending.append({"name": name, "candidates": candidates})
    matched = list(dict.fromkeys(matched))

    if not matched:
        src.status = "used" if pending else "discarded"
        src.error = "未能自动归属到已收录商家" if pending else "未识别到企业主体"
        src.extraction = {**result, "pending_entities": pending}
        return {"status": src.status, "pending": pending}

    event_date = None
    if result.get("event_date"):
        try:
            event_date = date.fromisoformat(result["event_date"])
        except ValueError:
            event_date = None
    if not event_date and src.published_at:
        event_date = src.published_at.date()

    polarity = 1 if int(result["polarity"]) > 0 else -1
    impact = max(1, min(2, abs(int(result.get("impact") or 1)))) * polarity
    auto = _should_auto_publish(polarity, src.source_level)
    created = []
    for mid in matched:
        ev = Evidence(
            merchant_id=mid, raw_source_id=src.id, dimension=result["dimension"], polarity=polarity, impact=impact,
            summary=(result.get("summary") or src.title)[:300], event_date=event_date, source_level=src.source_level,
            source_name=src.publisher, source_url=src.url, confidence=result.get("confidence"),
            status="approved" if auto else "draft", reviewed_by="auto" if auto else None,
            reviewed_at=datetime.now(timezone.utc) if auto else None,
        )
        db.add(ev)
        created.append(ev)
    db.flush()
    src.status = "used"
    src.extraction = {**result, "matched_merchant_ids": matched, "pending_entities": pending, "auto_published": auto}

    if auto:
        for mid in matched:
            recompute_merchant(db, mid)
    return {"status": "used", "evidence_ids": [e.id for e in created], "auto_published": auto}


@celery.task(name="pipeline.process_source", bind=True, max_retries=3, default_retry_delay=60)
def process_source_task(self, source_id: int) -> dict:
    db = SessionLocal()
    try:
        src = db.get(RawSource, source_id)
        if not src:
            return {"status": "missing"}
        try:
            result = process_source(db, src)
            db.commit()
            return result
        except Exception as e:  # noqa: BLE001
            db.rollback()
            src = db.get(RawSource, source_id)
            src.status = "failed"
            src.error = str(e)[:1000]
            db.commit()
            log.exception("process_source failed: %s", source_id)
            if self.request.is_eager:
                return {"status": "failed", "error": str(e)}
            raise self.retry(exc=e)
    finally:
        db.close()


# ------------------------------------------------------------ 监控与调度任务
@celery.task(name="pipeline.monitor_watchlist")
def monitor_watchlist(priority: str = "P1") -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(select(HotWatchlist).where(HotWatchlist.enabled.is_(True), HotWatchlist.priority == priority)).scalars().all()
        new_ids: list[int] = []
        for w in rows:
            for url in crawlers.rss_urls_for(w.keywords, w.rss_urls):
                try:
                    items = crawlers.fetch_rss(url)
                except Exception as e:  # noqa: BLE001
                    log.warning("rss failed %s: %s", url, e)
                    continue
                for it in items:
                    src = ingest_source(db, source_level="B", origin="rss", **it)
                    if src:
                        new_ids.append(src.id)
                if items:
                    w.last_hit_at = datetime.now(timezone.utc)
        db.commit()
        for sid in new_ids:
            process_source_task.delay(sid)
        return {"priority": priority, "watchlist": len(rows), "new_sources": len(new_ids)}
    finally:
        db.close()


@celery.task(name="pipeline.recompute_all_ratings")
def recompute_all_ratings() -> dict:
    db = SessionLocal()
    try:
        ids = [r[0] for r in db.execute(select(Merchant.id).where(Merchant.status == "published")).all()]
        for mid in ids:
            recompute_merchant(db, mid)
        db.commit()
        return {"recomputed": len(ids)}
    finally:
        db.close()


@celery.task(name="pipeline.retry_failed_sources")
def retry_failed_sources() -> dict:
    db = SessionLocal()
    try:
        ids = [r[0] for r in db.execute(select(RawSource.id).where(RawSource.status.in_(["new", "failed"])).limit(100)).all()]
    finally:
        db.close()
    for sid in ids:
        process_source_task.delay(sid)
    return {"requeued": len(ids)}
