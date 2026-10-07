"""كنسُ بيانات الراكب الفعليّ (SPEC §٦٣-ج/١) — غلافٌ رقيقٌ على `services/ride_for_other.purge_passengers`.

**«يُحذفان بعد ٣٠ يوماً» قرارُ المالك ووعدُ سياسة الخصوصية** — فالكنسُ يوميٌّ لا أسبوعيّ: اسمٌ ورقمٌ يبقيان ستّةَ أيامٍ بعد
موعدهما وعدٌ مكسورٌ ستّةَ أيام. **ويعمل والمفتاحُ مطفأ**: الإطفاءُ يمنع الطلبَ الجديدَ ولا يُبقي بياناتِ ما طُلب قبله.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import ride_for_other
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _purge() -> int:
    async with SessionLocal() as session:
        erased = await ride_for_other.purge_passengers(session)
        await session.commit()
    return erased


@celery_app.task(name="app.tasks.ride_for_other.purge_passengers")
def purge_passengers() -> dict[str, int]:
    erased = run_async(_purge())
    if erased:
        logger.info("محوُ الراكب الفعليّ: %s رحلة", erased)
    return {"erased": erased}
