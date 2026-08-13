"""المهمة الدورية للرحلات المجدولة (SPEC القسم 5.11، المرحلة 12-ط).

**الحجزُ ينتظر ساعةً لا زرّاً**، فلا بدَّ من مهمةٍ تقرأ الساعة. ودورتُها كلَّ
دقيقة لأن الموعدَ بالدقيقة: دورةٌ كلَّ خمسٍ تجعل «حجزُ السابعة» يعني «بين السابعة
والسابعة وخمس دقائق»، ومن حجز موعدَ طائرةٍ لا يقبل ذلك.

والمنطقُ في `services/bookings.py` وهذه غلافٌ رقيق — والاختباراتُ تستدعي الخدمةَ
مباشرةً ولا تحتاج عاملاً يعمل.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import bookings
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> dict[str, int]:
    async with SessionLocal() as session:
        # `run_due` تُنهي معاملةَ كلِّ حجزٍ بنفسها وتُطلق التوزيعَ بعد الـcommit
        return await bookings.run_due(session, get_redis_client())


@celery_app.task(name="app.tasks.bookings.run_due_bookings")
def run_due_bookings() -> dict[str, int]:
    tally = run_async(_run())
    if any(count for key, count in tally.items() if key != "missed") or tally["missed"]:
        logger.info("bookings cycle: %s", tally)
    return tally
