"""تذكيراتُ الاسترداد الأسبوعي (SPEC §٦٣-ج/٨) — غلافٌ رقيقٌ على `services/cashback.reminders`.

**كلَّ ربع ساعة**: الساعاتُ الثلاث بتوقيت كلِّ سوق، **ومفتاحٌ لكلِّ (سلسلة، يوم، نوع)** فلا يتكرّر تذكير.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import cashback
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _remind() -> int:
    async with SessionLocal() as session:
        return await cashback.reminders(session, get_redis_client())


@celery_app.task(name="app.tasks.cashback.remind_cashback")
def remind_cashback() -> dict[str, int]:
    sent = run_async(_remind())
    if sent:
        logger.info("تذكيراتُ الاسترداد: %s", sent)
    return {"sent": sent}
