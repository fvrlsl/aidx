"""实体消歧 / 别名模糊匹配。

一期数据量小，直接把 active 别名全部载入内存做 rapidfuzz 匹配；
Postgres 环境已建 pg_trgm 索引，后续可替换为 SQL 端 similarity() 预筛。
"""

import re
import unicodedata

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Merchant, MerchantAlias

_PUNCT_RE = re.compile(r"[\s\-_·•・()（）\[\]【】《》\"'“”‘’,，.。:：;；!！?？/\\|]+")
_SUFFIX_RE = re.compile(r"(有限公司|股份公司|集团公司|集团|公司|商贸|连锁|门店|旗舰店)$")


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "").lower()
    s = _PUNCT_RE.sub("", s)
    return _SUFFIX_RE.sub("", s) or s


def _alias_index(db: Session) -> list[tuple[str, int, str]]:
    rows = db.execute(
        select(MerchantAlias.alias_normalized, MerchantAlias.merchant_id, MerchantAlias.alias)
        .join(Merchant, Merchant.id == MerchantAlias.merchant_id)
        .where(MerchantAlias.status == "active", Merchant.status == "published")
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]


def search(db: Session, query: str, limit: int = 10, min_score: int | None = None) -> list[dict]:
    """返回 [{merchant_id, score, matched_alias}]，按分数倒序，每个商家只保留最高分。"""
    q = normalize(query)
    if not q:
        return []
    index = _alias_index(db)
    if not index:
        return []
    choices = {i: row[0] for i, row in enumerate(index)}
    threshold = settings.entity_candidate_threshold if min_score is None else min_score

    results = process.extract(q, choices, scorer=fuzz.WRatio, limit=limit * 3, score_cutoff=threshold)
    best: dict[int, dict] = {}
    for _, score, idx in results:
        alias_norm, merchant_id, alias = index[idx]
        # 子串命中额外加权，避免 "蜜雪" 匹配不到 "蜜雪冰城"
        if q in alias_norm or alias_norm in q:
            score = max(score, 92)
        if merchant_id not in best or best[merchant_id]["score"] < score:
            best[merchant_id] = {"merchant_id": merchant_id, "score": round(score, 1), "matched_alias": alias}
    return sorted(best.values(), key=lambda x: -x["score"])[:limit]


def resolve(db: Session, name: str) -> tuple[int | None, list[dict]]:
    """管道用：置信度达阈值直接返回 merchant_id，否则返回候选列表。"""
    candidates = search(db, name, limit=5)
    if candidates and candidates[0]["score"] >= settings.entity_auto_attach_threshold:
        return candidates[0]["merchant_id"], candidates
    return None, candidates


def add_alias(db: Session, merchant_id: int, alias: str, source: str = "editor", status: str = "active") -> MerchantAlias | None:
    norm = normalize(alias)
    if not norm:
        return None
    db.flush()
    exists = db.execute(
        select(MerchantAlias).where(MerchantAlias.merchant_id == merchant_id, MerchantAlias.alias_normalized == norm)
    ).scalar_one_or_none()
    if exists:
        return exists
    row = MerchantAlias(merchant_id=merchant_id, alias=alias.strip(), alias_normalized=norm, source=source, status=status)
    db.add(row)
    return row
