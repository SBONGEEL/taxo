"""دورةُ الحجز المضمون (SPEC §٦٣-ج/٣) — غلافٌ رقيقٌ على `services/guarantees.sweep`.

**كلَّ دقيقة**: مهلةُ التأكيد عشرُ دقائق، ودورةٌ أبطأُ منها تُبقي حجزاً عند كبتنٍ لم يُجب أطولَ مما قرّره المالك. **ورخيصةٌ والخدمةُ
مطفأة**: الاستعلامان على حجوزٍ مضمونةٍ لا توجد.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import guarantees
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        return await guarantees.sweep(session, get_redis_client())


@celery_app.task(name="app.tasks.guarantees.sweep_guarantees")
def sweep_guarantees() -> dict[str, int]:
    result = run_async(_sweep())
    if any(result.values()):
        logger.info("الحجزُ المضمون: %s", result)
    return result
