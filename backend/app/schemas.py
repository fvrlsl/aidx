from datetime import date, datetime

from pydantic import BaseModel, Field

from app.constants import DIMENSIONS, IDENTITY_CLAIMS, OVERALL_LEVELS, USER_LEVELS
from app.models import CaseArticle, Evidence, Merchant, RatingSnapshot
from app.services.rating_engine import public_level


# ------------------------------------------------------------ 通用
class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------ 序列化
def serialize_rating(snap: RatingSnapshot | None) -> dict:
    level = public_level(snap)
    return {
        "overall_level": level,
        "overall_label": OVERALL_LEVELS.get(level, level),
        "dim_levels": snap.dim_levels if snap else {},
        "dim_labels": {k: OVERALL_LEVELS.get(v, v) for k, v in (snap.dim_levels if snap else {}).items()},
        "dim_scores": snap.dim_scores if snap else {},
        "tags": snap.tags if snap else [],
        "evidence_count": snap.evidence_count if snap else 0,
        "evidence_count_ab": snap.evidence_count_ab if snap else 0,
        "rule_version": snap.rule_version if snap else None,
        "computed_at": snap.computed_at if snap else None,
    }


def serialize_merchant_brief(m: Merchant, snap: RatingSnapshot | None = None, extra: dict | None = None) -> dict:
    snap = snap if snap is not None else m.latest_rating
    level = public_level(snap)
    data = {
        "id": m.id,
        "name": m.canonical_name,
        "industry": m.industry,
        "region": m.region,
        "logo_url": m.logo_url,
        "status": m.status,
        "overall_level": level,
        "overall_label": OVERALL_LEVELS.get(level, level),
        "tags": snap.tags if snap else [],
    }
    if extra:
        data.update(extra)
    return data


def serialize_merchant_detail(m: Merchant, snap: RatingSnapshot | None) -> dict:
    data = serialize_merchant_brief(m, snap)
    data.update(
        {
            "intro": m.intro,
            "type": m.type,
            "aliases": [a.alias for a in m.aliases if a.status == "active"],
            "rating": serialize_rating(snap),
            "dimensions": DIMENSIONS,
            "updated_at": snap.computed_at if snap else m.updated_at,
        }
    )
    return data


def serialize_evidence(ev: Evidence) -> dict:
    return {
        "id": ev.id,
        "merchant_id": ev.merchant_id,
        "dimension": ev.dimension,
        "dimension_label": DIMENSIONS.get(ev.dimension, ev.dimension),
        "polarity": ev.polarity,
        "impact": ev.impact,
        "summary": ev.summary,
        "event_date": ev.event_date,
        "source_level": ev.source_level,
        "source_name": ev.source_name,
        "source_url": ev.source_url,
        "screenshot_url": ev.raw_source.screenshot_url if ev.raw_source else None,
        "merchant_reply": ev.merchant_reply,
        "is_historical": bool(ev.event_date and (date.today() - ev.event_date).days > 365),
        "status": ev.status,
        "confidence": ev.confidence,
        "created_at": ev.created_at,
    }


def serialize_case(c: CaseArticle, merchants: list[dict] | None = None, with_body: bool = False) -> dict:
    data = {
        "id": c.id,
        "title": c.title,
        "subtitle": c.subtitle,
        "cover_url": c.cover_url,
        "type": c.type,
        "status": c.status,
        "published_at": c.published_at,
        "view_count": c.view_count,
        "share_count": c.share_count,
        "merchant_ids": c.merchant_ids,
        "share_card_url": c.share_card_url,
    }
    if with_body:
        data["body"] = c.body
        data["timeline"] = c.timeline
        data["merchants"] = merchants or []
    return data


# ------------------------------------------------------------ 小程序端请求体
class LoginIn(BaseModel):
    code: str
    nickname: str | None = None
    avatar: str | None = None


class RatingIn(BaseModel):
    level: int = Field(ge=1, le=5)
    identity_claim: str = "customer"
    comment: str | None = Field(default=None, max_length=200)
    device_hash: str | None = None

    def validate_claim(self) -> None:
        if self.identity_claim not in IDENTITY_CLAIMS:
            raise ValueError("身份类型无效")
        if self.level not in USER_LEVELS:
            raise ValueError("评分等级无效")


class MerchantCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    industry: str | None = None
    confirm_merchant_id: int | None = None  # 用户确认"你是指 XX 吗"时传入，挂别名


class TipIn(BaseModel):
    merchant_id: int | None = None
    merchant_name_raw: str | None = None
    url: str | None = None
    text: str | None = Field(default=None, max_length=1000)
    images: list[str] = []


class FeedbackIn(BaseModel):
    merchant_id: int
    evidence_id: int | None = None
    type: str
    contact_name: str = Field(max_length=50)
    contact_phone: str = Field(max_length=30)
    company_name: str | None = None
    proof_files: list[str] = []
    content: str = Field(max_length=1000)
    attachments: list[str] = Field(default_factory=list, max_length=5)


# ------------------------------------------------------------ 后台请求体
class AdminLoginIn(BaseModel):
    username: str
    password: str


class MerchantUpsertIn(BaseModel):
    canonical_name: str
    type: str = "brand"
    industry: str | None = None
    region: str | None = None
    logo_url: str | None = None
    unified_social_credit_code: str | None = None
    intro: str | None = None
    status: str = "published"
    aliases: list[str] = []


class MergeIn(BaseModel):
    from_id: int
    to_id: int
    reason: str | None = None


class EvidenceUpsertIn(BaseModel):
    merchant_id: int
    raw_source_id: int | None = None
    dimension: str
    polarity: int
    impact: int = Field(ge=-2, le=2)
    summary: str = Field(max_length=300)
    event_date: date | None = None
    source_level: str = "B"
    source_name: str | None = None
    source_url: str | None = None
    merchant_reply: str | None = None


class EvidenceReviewIn(BaseModel):
    action: str  # approve / reject / archive
    patch: EvidenceUpsertIn | None = None


class ClipIn(BaseModel):
    url: str
    source_level: str = "B"
    publisher: str | None = None
    title: str | None = None
    summary: str | None = None
    process_now: bool = True


class ImportRowIn(BaseModel):
    merchant_name: str
    dimension: str
    polarity: int
    impact: int = 2
    summary: str
    event_date: date | None = None
    source_level: str = "A"
    source_name: str
    source_url: str


class CaseUpsertIn(BaseModel):
    title: str
    subtitle: str | None = None
    cover_url: str | None = None
    body: str = ""
    timeline: list[dict] = []
    merchant_ids: list[int] = []
    type: str = "benchmark"
    status: str = "draft"


class FeedbackHandleIn(BaseModel):
    status: str | None = None
    action: str | None = None
    reply: str | None = None


class WatchlistUpsertIn(BaseModel):
    merchant_id: int
    keywords: list[str] = []
    rss_urls: list[str] = []
    priority: str = "P1"
    enabled: bool = True


class UserRatingReviewIn(BaseModel):
    comment_status: str  # approved / hidden
    weight: float | None = None


class SnapshotConfirmIn(BaseModel):
    accept: bool = True
