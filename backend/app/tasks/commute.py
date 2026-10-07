"""دورةُ المشوار الثابت (SPEC §٦٣-ج/٦) — غلافٌ رقيقٌ على `services/commute.run_daily`.

**كلَّ ساعةٍ لا مرّةً في اليوم**: توليدُ حجوز الغد متكرّرٌ بلا ضرر (الفهرسُ الفريدُ على الاشتراك والموعد)، **ودورةٌ يوميّةٌ تفوتها
ساعةُ عطلٍ تُفوّت يوماً كاملاً على من دفع**. والتسويةُ مرّةً واحدةً لكلِّ اشتراك (`settled_at`).
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import commute
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _run() -> dict[str, int]:
    async with SessionLocal() as session:
        return await commute.run_daily(session)


@celery_app.task(name="app.tasks.commute.run_commutes")
def run_commutes() -> dict[str, int]:
    result = run_async(_run())
    if any(result.values()):
        logger.info("المشوارُ الثابت: %s", result)
    return result
