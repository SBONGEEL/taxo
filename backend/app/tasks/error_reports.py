"""كنسُ تقارير الأعطال — **غلافٌ رقيقٌ على الخدمة** (2026-09-20).

**مرّةً في اليوم لا كلَّ دقيقة**: العتبةُ ثلاثون يوماً، ودورةٌ أسرعُ تسأل
القاعدةَ ألفَ مرّةٍ عن سؤالٍ جوابُه يتغيّر مرّة.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import error_reports
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> tuple[int, int]:
    async with SessionLocal() as session:
        return await error_reports.sweep_retention(session)


@celery_app.task(name="app.tasks.error_reports.sweep_error_reports")
def sweep_error_reports() -> int:
    events, groups = run_async(_sweep())
    if events or groups:
        logger.info("error reports swept: events=%s groups=%s", events, groups)
    return events + groups
