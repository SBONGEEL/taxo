"""إشعاراتُ المالك (SPEC §٨١) — **العاملُ يقرأ ما التقطته الأبوابُ ويكتبه ويرسله**، كلَّ خمس ثوانٍ.

**ولمَ دورةٌ لا مهمّةٌ لكلِّ حدث**: إرسالُ مهمّةٍ من بابِ الدفع نداءٌ إلى الوسيط **في طريق الدفع نفسِه** — وما يُبقي الدفعَ بعيداً عن
الإشعار أن الدفعَ يرمي حدثَه في قائمةٍ ويمضي (`services/alert_capture.py`). **والدورةُ الفارغةُ قراءةُ طولِ قائمةٍ لا غير.**
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import admin_alerts, alert_capture
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _drain() -> int:
    redis = get_redis_client()
    if not await redis.llen(alert_capture.QUEUE_KEY):
        return 0
    async with SessionLocal() as session:
        return await admin_alerts.drain(session, redis)


@celery_app.task(name="app.tasks.admin_alerts.drain_admin_alerts", ignore_result=True)
def drain_admin_alerts() -> int:
    written = run_async(_drain())
    if written:
        logger.info("admin alerts written: %s", written)
    return written


async def _trim() -> int:
    async with SessionLocal() as session:
        removed = await admin_alerts.trim(session)
        await session.commit()
    return removed


@celery_app.task(name="app.tasks.admin_alerts.trim_admin_alerts")
def trim_admin_alerts() -> int:
    return run_async(_trim())
