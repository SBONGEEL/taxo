"""كنسُ أرقام «أعلمني فور الإطلاق» بعد ١٢ شهراً — **غلافٌ رقيقٌ على الخدمة** (أمرُ المالك ٢٠٢٦-١١-١٨ السادس).

**وُعد به في سياسة الخصوصيّة المنشورة** قبل أن يُبنى، فبُني لئلّا يكذب النصّ — **ويوميّاً بساعةٍ ثابتة** كأخواته.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.services import signup_countries
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> int:
    async with SessionLocal() as session:
        return await signup_countries.sweep_interests(session)


@celery_app.task(name="app.tasks.signup_countries.sweep_launch_interests")
def sweep_launch_interests() -> int:
    removed = run_async(_sweep())
    if removed:
        logger.info("launch interests swept: %s", removed)
    return removed
