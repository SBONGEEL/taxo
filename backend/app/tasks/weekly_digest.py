"""**ملخّصُ الأسبوع للكباتن** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٧) — إشعارٌ كلَّ سبتٍ صباحاً لمن أكمل رحلةً في الأسبوع.

**مرّةً لكلِّ كبتنٍ في الأسبوع** بمفتاحٍ في Redis — beat يُعاد مع كلِّ رفع، والإشعارُ لا يتكرّر لذلك.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import notifications, weekly_digest
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

SENT_TTL = 60 * 60 * 24 * 8


async def _send() -> int:
    redis = get_redis_client()
    now = datetime.now(UTC)
    week = now.strftime("%G-W%V")
    sent = 0
    async with SessionLocal() as session:
        for user_id, _country in await weekly_digest.recipients(session, now=now):
            if not await redis.set(f"digest:weekly:{week}:{user_id}", "1", ex=SENT_TTL, nx=True):
                continue
            await notifications.publish_weekly_digest(session, redis, user_id=user_id)
            await session.commit()
            sent += 1
    return sent


@celery_app.task(name="app.tasks.weekly_digest.send_weekly_digest")
def send_weekly_digest() -> int:
    sent = run_async(_send())
    logger.info("ملخّصُ الأسبوع: %s إشعاراً", sent)
    return sent
