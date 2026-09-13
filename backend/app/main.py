import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import admin_v1, v1
from app.config import settings
from app.db import SessionLocal, init_db
from app.models import AdminUser
from app.services.security import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def ensure_default_admin() -> None:
    with SessionLocal() as db:
        if not db.execute(select(AdminUser.id)).first():
            db.add(AdminUser(username=settings.admin_default_username, password_hash=hash_password(settings.admin_default_password), role="admin"))
            db.commit()
            log.info("created default admin user: %s", settings.admin_default_username)


def start_inprocess_scheduler():
    """极简模式（无 Redis / 无独立 worker）下，在 API 进程内跑定时任务。"""
    from apscheduler.schedulers.background import BackgroundScheduler

    from app.pipeline import tasks

    sched = BackgroundScheduler(timezone="Asia/Shanghai")
    sched.add_job(lambda: tasks.monitor_watchlist.delay("P0"), "cron", minute=5, id="p0")
    sched.add_job(lambda: tasks.monitor_watchlist.delay("P1"), "cron", hour=6, minute=30, id="p1")
    sched.add_job(lambda: tasks.monitor_watchlist.delay("P2"), "cron", day_of_week="mon", hour=7, id="p2")
    sched.add_job(lambda: tasks.recompute_all_ratings.delay(), "cron", hour=3, id="recompute")
    sched.add_job(lambda: tasks.retry_failed_sources.delay(), "cron", minute=30, id="retry")
    sched.start()
    log.info("in-process scheduler started")
    return sched


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_admin()
    sched = start_inprocess_scheduler() if settings.scheduler_inprocess else None
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title=f"{settings.app_name} API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(v1.router)
app.include_router(admin_v1.router)

os.makedirs(settings.media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/healthz")
def healthz():
    return {"ok": True, "env": settings.env, "db": "sqlite" if settings.is_sqlite else "postgres", "redis": bool(settings.redis_url)}
