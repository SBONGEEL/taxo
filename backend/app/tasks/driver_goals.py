"""**كنسُ أهداف الكبتن** (البند ١٦) — كلَّ عشر دقائق: يصرف لمن بلغ ويُنبّه من اقترب، حيث المفتاحُ مشتعلٌ وحدَه."""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import driver_goals
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> tuple[int, int]:
    async with SessionLocal() as session:
        return await driver_goals.sweep(session, get_redis_client())


@celery_app.task(name="app.tasks.driver_goals.sweep")
def sweep() -> tuple[int, int]:
    result = run_async(_run())
    logger.info("أهدافُ الكبتن: %s مكافأة، و%s تنبيهاً", *result)
    return result
