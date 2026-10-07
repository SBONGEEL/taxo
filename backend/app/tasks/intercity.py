"""مهلةُ «بين المدن» (SPEC §٦٣-ج/٧) — غلافٌ رقيقٌ على `services/intercity.sweep`.

**كلَّ خمس دقائق**: المهلةُ بالساعات، ورحلةٌ لم تبلغ حدَّها تُلغى ويُردّ لركّابها قبل أن يخرجوا إلى نقطة التجمّع.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import intercity
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        return await intercity.sweep(session)


@celery_app.task(name="app.tasks.intercity.sweep_intercity")
def sweep_intercity() -> dict[str, int]:
    result = run_async(_sweep())
    if any(result.values()):
        logger.info("بين المدن: %s", result)
    return result
