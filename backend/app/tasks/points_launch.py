"""**كنسُ نقاط الالتزام وحملة الإطلاق** (§١١٤) — كلَّ عشر دقائق. **مطفأً لا يكتب شيئاً** إلا لقطةَ القاعدة في Redis."""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import commitment, launch_campaign
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _commitment() -> dict[str, int]:
    async with SessionLocal() as session:
        done = await commitment.sweep(session, get_redis_client())
        await session.commit()
        return done


async def _campaign() -> dict[str, int]:
    async with SessionLocal() as session:
        done = await launch_campaign.sweep(session)
        await session.commit()
        return done


@celery_app.task(name="app.tasks.points_launch.commitment_sweep")
def commitment_sweep() -> dict[str, int]:
    result = run_async(_commitment())
    logger.info("نقاطُ الالتزام: أيّامٌ قُيّمت %s", result)
    return result


@celery_app.task(name="app.tasks.points_launch.campaign_sweep")
def campaign_sweep() -> dict[str, int]:
    result = run_async(_campaign())
    logger.info("حملةُ الإطلاق: منحٌ كُتبت %s", result)
    return result
