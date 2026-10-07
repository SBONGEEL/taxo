"""ساعاتُ العمل (SPEC §٦٢-ج/٣٧) — غلافان رقيقان: **دقيقةٌ كلَّ دقيقة**، **وجمعٌ شهريٌّ كلَّ يوم** لما جاوز ثلاثةَ عشرَ شهراً."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import activity
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _tick() -> int:
    async with SessionLocal() as session:
        counted = await activity.tick(session, get_redis_client())
        await session.commit()
        return counted


async def _roll_up() -> int:
    async with SessionLocal() as session:
        removed = await activity.roll_up(session, today=datetime.now(UTC).date())
        await session.commit()
        return removed


@celery_app.task(name="app.tasks.activity.record_activity_minute")
def record_activity_minute() -> dict[str, int]:
    return {"counted": run_async(_tick())}


@celery_app.task(name="app.tasks.activity.roll_up_activity")
def roll_up_activity() -> dict[str, int]:
    removed = run_async(_roll_up())
    if removed:
        logger.info("ساعاتُ العمل: جُمع %s يوماً قديماً شهرياً", removed)
    return {"removed": removed}
