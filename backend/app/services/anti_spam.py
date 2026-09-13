"""防刷：有 Redis 用 Redis 计数，否则退化为进程内字典（仅供本地极简模式）。"""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRating

NEW_USER_HOURS = 24
NEW_USER_DAILY_LIMIT = 3
USER_DAILY_LIMIT = 20
SAME_DEVICE_MERCHANT_LIMIT = 5
DOWNWEIGHT = 0.2


class _Counter:
    def __init__(self) -> None:
        self._redis = None
        self._mem: dict[str, tuple[int, float]] = {}
        if settings.redis_url:
            import redis

            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)

    def incr(self, key: str, ttl: int) -> int:
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
            return int(pipe.execute()[0])
        now = time.time()
        count, expires = self._mem.get(key, (0, now + ttl))
        if expires < now:
            count, expires = 0, now + ttl
        count += 1
        self._mem[key] = (count, expires)
        return count

    def get(self, key: str) -> int:
        if self._redis:
            return int(self._redis.get(key) or 0)
        count, expires = self._mem.get(key, (0, 0))
        return count if expires > time.time() else 0


counter = _Counter()


class RateLimited(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def check_rating_allowed(db: Session, user: User, merchant_id: int, device_hash: str | None, ip_hash: str | None) -> float:
    """检查是否允许打分；返回本次评分权重（1.0 或降权）。已存在的评分修改不计入次数。"""
    existing = db.execute(
        select(UserRating.id).where(UserRating.user_id == user.id, UserRating.merchant_id == merchant_id)
    ).scalar_one_or_none()
    if existing:
        return 1.0

    created = user.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    is_new = created and created > datetime.now(timezone.utc) - timedelta(hours=NEW_USER_HOURS)
    day_key = f"rate:user:{user.id}:{datetime.now(timezone.utc):%Y%m%d}"
    used = counter.get(day_key)
    limit = NEW_USER_DAILY_LIMIT if is_new else USER_DAILY_LIMIT
    if used >= limit:
        raise RateLimited("今日评分次数已达上限，明天再来吧")
    counter.incr(day_key, 86400)

    weight = 1.0
    for kind, value in (("device", device_hash), ("ip", ip_hash)):
        if not value:
            continue
        n = counter.incr(f"rate:{kind}:{value}:m{merchant_id}", 86400)
        if n >= SAME_DEVICE_MERCHANT_LIMIT:
            weight = DOWNWEIGHT
    return weight


def burst_detected(db: Session, merchant_id: int) -> bool:
    """单商家 1 小时评分量超过近 7 日小时均值 10 倍。"""
    now = datetime.now(timezone.utc)
    since_hour = now - timedelta(hours=1)
    since_week = now - timedelta(days=7)
    if settings.is_sqlite:
        since_hour = since_hour.replace(tzinfo=None)
        since_week = since_week.replace(tzinfo=None)
    hour_count = db.execute(
        select(func.count()).select_from(UserRating).where(
            UserRating.merchant_id == merchant_id, UserRating.created_at >= since_hour
        )
    ).scalar_one()
    week_count = db.execute(
        select(func.count()).select_from(UserRating).where(
            UserRating.merchant_id == merchant_id, UserRating.created_at >= since_week
        )
    ).scalar_one()
    hourly_avg = max(week_count / (7 * 24), 0.5)
    return hour_count > hourly_avg * 10 and hour_count >= 10
