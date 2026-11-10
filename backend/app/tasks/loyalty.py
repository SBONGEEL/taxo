"""**كنسُ نقاط الولاء** (البند ١٤) — كلَّ عشر دقائق: المكتملةُ تكسب، حيث المفتاحُ مشتعلٌ وقاعدةٌ موضوعة."""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import loyalty
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> int:
    async with SessionLocal() as session:
        return await loyalty.sweep(session)


@celery_app.task(name="app.tasks.loyalty.sweep")
def sweep() -> int:
    earned = run_async(_run())
    logger.info("نقاطُ الولاء: %s رحلةً كسبت", earned)
    return earned
