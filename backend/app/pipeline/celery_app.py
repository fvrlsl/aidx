from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("goodmerchant")
celery.conf.update(
    broker_url=settings.redis_url or "memory://",
    result_backend=settings.redis_url or "cache+memory://",
    task_always_eager=settings.celery_eager or not settings.redis_url,
    task_eager_propagates=True,
    task_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "monitor-hot-p0-hourly": {"task": "pipeline.monitor_watchlist", "schedule": crontab(minute=5), "args": ("P0",)},
        "monitor-keywords-daily": {"task": "pipeline.monitor_watchlist", "schedule": crontab(hour=6, minute=30), "args": ("P1",)},
        "monitor-keywords-weekly": {"task": "pipeline.monitor_watchlist", "schedule": crontab(hour=7, minute=0, day_of_week=1), "args": ("P2",)},
        "recompute-ratings-daily": {"task": "pipeline.recompute_all_ratings", "schedule": crontab(hour=3, minute=0)},
        "retry-failed-sources": {"task": "pipeline.retry_failed_sources", "schedule": crontab(minute=30)},
    },
)
celery.autodiscover_tasks(["app.pipeline"])
