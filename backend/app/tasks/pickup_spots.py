"""**خلايا الالتقاط** (البند ١١) — تُبنى كلَّ ليلةٍ من الرحلات المكتملة آخرَ ٩٠ يوماً، مجمَّعةً بلا خليةٍ دون ثلاثة ركّاب."""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import pickup_spots
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> dict[str, int]:
    async with SessionLocal() as session:
        return await pickup_spots.rebuild(session, get_redis_client())


@celery_app.task(name="app.tasks.pickup_spots.rebuild")
def rebuild() -> dict[str, int]:
    counts = run_async(_run())
    logger.info("خلايا الالتقاط: %s", counts)
    return counts
