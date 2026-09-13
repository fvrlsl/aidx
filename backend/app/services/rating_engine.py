"""评级引擎 v1：把已发布依据汇总成维度分与总评快照。规则见 constants.RATING_RULES_TEXT。"""

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants import DIMENSIONS, LEVEL_ORDER, SOURCE_WEIGHTS
from app.models import Evidence, RatingSnapshot

RULE_VERSION = "v1"
MIN_AB_EVIDENCE = 3

DIM_THRESHOLDS = [(3.0, "benchmark"), (1.0, "good"), (-1.0, "neutral"), (-3.0, "disputed")]
OVERALL_THRESHOLDS = [(6.0, "benchmark"), (2.0, "good"), (-2.0, "neutral"), (-5.0, "disputed")]


def time_decay(event_date: date | None, today: date | None = None) -> float:
    if not event_date:
        return 0.6
    today = today or datetime.now(timezone.utc).date()
    days = (today - event_date).days
    if days <= 365:
        return 1.0
    if days <= 365 * 3:
        return 0.6
    return 0.3


def _level(score: float, thresholds: list[tuple[float, str]], floor: str) -> str:
    for th, lvl in thresholds:
        if score >= th:
            return lvl
    return floor


def contribution(ev: Evidence) -> float:
    return ev.impact * SOURCE_WEIGHTS.get(ev.source_level, 0) * time_decay(ev.event_date)


def compute(evidences: list[Evidence]) -> dict:
    dim_scores = {d: 0.0 for d in DIMENSIONS}
    count_ab = 0
    negative_ab = 0
    negative_c_only = False
    for ev in evidences:
        if ev.dimension not in dim_scores:
            continue
        dim_scores[ev.dimension] += contribution(ev)
        if ev.source_level in ("A", "B"):
            count_ab += 1
            if ev.polarity < 0:
                negative_ab += 1
        elif ev.polarity < 0:
            negative_c_only = True

    dim_levels = {d: _level(s, DIM_THRESHOLDS, "severe") for d, s in dim_scores.items()}
    overall_score = round(sum(dim_scores.values()), 2)
    overall = _level(overall_score, OVERALL_THRESHOLDS, "severe")
    tags: list[str] = []

    # 硬约束 1：无 A/B 级负面依据，不得低于"一般"
    if negative_ab == 0 and LEVEL_ORDER.index(overall) < LEVEL_ORDER.index("neutral"):
        overall = "neutral"
        tags.append("negative_clamped")
    # 硬约束 2：仅 C 级负面只加标签
    if negative_ab == 0 and negative_c_only:
        tags.append("disputed_signal")
    # 硬约束 3：A/B 依据不足
    if count_ab < MIN_AB_EVIDENCE:
        overall = "insufficient"

    return {
        "dim_scores": {d: round(s, 2) for d, s in dim_scores.items()},
        "dim_levels": dim_levels,
        "overall_score": overall_score,
        "overall_level": overall,
        "tags": tags,
        "evidence_count_ab": count_ab,
        "evidence_count": len(evidences),
    }


def recompute_merchant(db: Session, merchant_id: int, operator: str | None = None) -> RatingSnapshot:
    evidences = db.execute(
        select(Evidence).where(Evidence.merchant_id == merchant_id, Evidence.status == "approved")
    ).scalars().all()
    result = compute(list(evidences))

    latest = db.execute(
        select(RatingSnapshot).where(RatingSnapshot.merchant_id == merchant_id, RatingSnapshot.is_latest.is_(True))
    ).scalar_one_or_none()

    prev_level = latest.overall_level if latest else None
    crossed = bool(prev_level and prev_level != result["overall_level"] and prev_level != "insufficient")
    # 跨档变化需人工确认；人工触发的重算直接生效
    needs_confirm = crossed and operator is None

    if latest:
        db.execute(
            update(RatingSnapshot).where(RatingSnapshot.id == latest.id).values(is_latest=False)
        )
    snap = RatingSnapshot(
        merchant_id=merchant_id,
        rule_version=RULE_VERSION,
        is_latest=True,
        needs_confirm=needs_confirm,
        previous_level=prev_level,
        confirmed_by=operator,
        **result,
    )
    db.add(snap)
    db.flush()
    return snap


def public_level(snap: RatingSnapshot | None) -> str:
    """对外展示的总评：待确认的跨档变化仍显示旧档。"""
    if not snap:
        return "insufficient"
    if snap.needs_confirm and snap.previous_level:
        return snap.previous_level
    return snap.overall_level
