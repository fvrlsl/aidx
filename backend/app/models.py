from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- 实体与别名
class Merchant(TimestampMixin, Base):
    __tablename__ = "merchant"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(200), index=True)
    type: Mapped[str] = mapped_column(String(20), default="brand")  # brand / group
    industry: Mapped[str | None] = mapped_column(String(50))
    region: Mapped[str | None] = mapped_column(String(50))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    unified_social_credit_code: Mapped[str | None] = mapped_column(String(30), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("merchant.id"))
    intro: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)  # draft/pending/published/merged
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("merchant.id"))
    created_by: Mapped[str] = mapped_column(String(20), default="editor")  # editor / user
    creator_user_id: Mapped[int | None] = mapped_column(Integer)

    aliases: Mapped[list["MerchantAlias"]] = relationship(back_populates="merchant", cascade="all, delete-orphan")
    latest_rating: Mapped["RatingSnapshot | None"] = relationship(
        primaryjoin="and_(Merchant.id==RatingSnapshot.merchant_id, RatingSnapshot.is_latest==True)",
        viewonly=True,
        uselist=False,
    )


class MerchantAlias(TimestampMixin, Base):
    __tablename__ = "merchant_alias"
    __table_args__ = (UniqueConstraint("merchant_id", "alias_normalized", name="uq_alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(200))
    alias_normalized: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(String(20), default="editor")  # editor/user/system
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/pending

    merchant: Mapped[Merchant] = relationship(back_populates="aliases")


class ProductBarcode(TimestampMixin, Base):
    __tablename__ = "product_barcode"

    barcode: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_name: Mapped[str | None] = mapped_column(String(200))
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchant.id"))
    source: Mapped[str] = mapped_column(String(20), default="editor")
    status: Mapped[str] = mapped_column(String(20), default="active")


# ---------------------------------------------------------------- 素材、依据、评级
class RawSource(TimestampMixin, Base):
    __tablename__ = "raw_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(100))
    source_level: Mapped[str] = mapped_column(String(1), default="C", index=True)  # A/B/C/D
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    summary: Mapped[str | None] = mapped_column(Text)
    screenshot_url: Mapped[str | None] = mapped_column(String(500))
    event_group_id: Mapped[int | None] = mapped_column(Integer, index=True)
    origin: Mapped[str] = mapped_column(String(30), default="manual")  # manual/rss/import/user_tip
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new/processing/used/discarded/failed
    extraction: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id"), index=True)
    raw_source_id: Mapped[int | None] = mapped_column(ForeignKey("raw_source.id"))
    dimension: Mapped[str] = mapped_column(String(20))  # pay/hours/dignity/disputes
    polarity: Mapped[int] = mapped_column(Integer)  # +1 / -1
    impact: Mapped[int] = mapped_column(Integer)  # -2..2
    summary: Mapped[str] = mapped_column(String(300))
    event_date: Mapped[date | None] = mapped_column(Date)
    source_level: Mapped[str] = mapped_column(String(1), default="C")
    source_name: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft/approved/rejected/archived
    reviewed_by: Mapped[str | None] = mapped_column(String(50))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merchant_reply: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    merchant: Mapped[Merchant] = relationship()
    raw_source: Mapped[RawSource | None] = relationship()


class RatingSnapshot(Base):
    __tablename__ = "rating_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id"), index=True)
    dim_scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    dim_levels: Mapped[dict] = mapped_column(JSONType, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, default=0)
    overall_level: Mapped[str] = mapped_column(String(20))  # benchmark/good/neutral/disputed/severe/insufficient
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    evidence_count_ab: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_version: Mapped[str] = mapped_column(String(10), default="v1")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    needs_confirm: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    previous_level: Mapped[str | None] = mapped_column(String(20))
    confirmed_by: Mapped[str | None] = mapped_column(String(50))


# ---------------------------------------------------------------- 案例
class CaseArticle(TimestampMixin, Base):
    __tablename__ = "case_article"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str | None] = mapped_column(String(300))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, default="")
    timeline: Mapped[list] = mapped_column(JSONType, default=list)  # [{date, text, source_url}]
    merchant_ids: Mapped[list] = mapped_column(JSONType, default=list)
    type: Mapped[str] = mapped_column(String(20), default="benchmark")  # benchmark/reversal/warning
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    share_card_url: Mapped[str | None] = mapped_column(String(500))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------- 用户侧
class User(TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    unionid: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(50))
    avatar: Mapped[str | None] = mapped_column(String(500))
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserRating(TimestampMixin, Base):
    __tablename__ = "user_rating"
    __table_args__ = (UniqueConstraint("user_id", "merchant_id", name="uq_user_merchant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)  # 1..5，5=很好
    identity_claim: Mapped[str] = mapped_column(String(20), default="customer")  # customer/current_staff/former_staff/hearsay
    comment: Mapped[str | None] = mapped_column(String(500))
    comment_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/hidden
    device_hash: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    history: Mapped[list] = mapped_column(JSONType, default=list)

    user: Mapped[User] = relationship()


class UserTip(TimestampMixin, Base):
    __tablename__ = "user_tip"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchant.id"))
    merchant_name_raw: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(1000))
    text: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new/accepted/rejected
    handled_by: Mapped[str | None] = mapped_column(String(50))


class MerchantFeedback(TimestampMixin, Base):
    __tablename__ = "merchant_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id"), index=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    type: Mapped[str] = mapped_column(String(30))  # info_error/appeal_rating/add_positive/request_remove/other
    contact_name: Mapped[str] = mapped_column(String(50))
    contact_phone: Mapped[str] = mapped_column(String(30))
    company_name: Mapped[str | None] = mapped_column(String(200))
    proof_files: Mapped[list] = mapped_column(JSONType, default=list)
    content: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new/reviewing/replied/closed
    handled_by: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str | None] = mapped_column(String(30))  # reject/fix_evidence/add_evidence/add_reply
    reply: Mapped[str | None] = mapped_column(Text)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ticket_no: Mapped[str] = mapped_column(String(20), unique=True)


# ---------------------------------------------------------------- 运营与审计
class HotWatchlist(TimestampMixin, Base):
    __tablename__ = "hot_watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchant.id"), index=True)
    keywords: Mapped[list] = mapped_column(JSONType, default=list)
    rss_urls: Mapped[list] = mapped_column(JSONType, default=list)
    priority: Mapped[str] = mapped_column(String(2), default="P1")  # P0/P1/P2
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    merchant: Mapped[Merchant] = relationship()


class MergeLog(Base):
    __tablename__ = "merge_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int] = mapped_column(Integer)
    to_id: Mapped[int] = mapped_column(Integer)
    operator: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    operator: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int | None] = mapped_column(Integer)
    before: Mapped[dict | None] = mapped_column(JSONType)
    after: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="editor")  # admin/editor
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
