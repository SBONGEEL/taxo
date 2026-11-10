"""**درجةُ الجودة اليوميّة** (البند ٣) — لكلِّ كبتنٍ معتمد، وإنذارٌ بنصائح لمن دون العتبة **مرّةً في الأسبوع** حيث المفتاحُ مشتعل."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import DriverStatus
from app.models.user import User
from app.services import notifications, quality
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)
WARN_TTL = 7 * 86400


async def _run(now: datetime | None = None) -> tuple[int, int]:
    redis = get_redis_client()
    now = now or datetime.now(UTC)
    scored = warned = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Driver.id, Driver.user_id, User.country_code)
                .join(User, User.id == Driver.user_id)
                .where(Driver.status == DriverStatus.APPROVED)
            )
        ).all()
        for driver_id, user_id, country in rows:
            row = await quality.snapshot(session, redis, driver_id=driver_id, country=country, day=now.date(), now=now)
            await session.commit()
            scored += 1
            weights = await quality.settings_for(session, country)
            if weights.enabled and row.score < weights.warn_below:
                week = now.strftime("%G-W%V")
                if await redis.set(f"quality:warned:{week}:{driver_id}", "1", ex=WARN_TTL, nx=True):
                    tips = [quality.TIPS[name] for name in quality.weakest(row.components["parts"])]
                    await notifications.publish_quality_warning(session, redis, user_id=user_id, tips=tips)
                    await session.commit()
                    warned += 1
    return scored, warned


@celery_app.task(name="app.tasks.quality.score_drivers")
def score_drivers() -> tuple[int, int]:
    result = run_async(_run())
    logger.info("درجةُ الجودة: %s كبتناً، و%s إنذاراً", *result)
    return result
