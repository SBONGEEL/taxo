"""دورةُ الطور الآليّ لبثّ الموقع (SPEC §٧٥-ج) — كلَّ `broadcast.TICK_SECONDS`: يُعدّ المتّصلون ويُقرَّر فاصلُ المتاحين.

والمنطقُ في `services/broadcast.py` وهذه غلافٌ رقيق، فالاختبارات تستدعي الخدمةَ مباشرةً ولا تحتاج عاملاً يعمل. **وفي الطور اليدويّ
تمرّ الدورةُ كذلك**: تكتب القيمةَ اليدويّةَ في الحال إن غابت عنها (Redis أُعيد تشغيلُه) — فلا يبقى الكباتنُ على سياسةٍ ضاعت.
"""

from __future__ import annotations

import logging

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import broadcast
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _tick() -> int:
    async with SessionLocal() as session:
        policy = await broadcast.apply(session, get_redis_client())
        await session.commit()
    return policy.available_seconds


@celery_app.task(name="app.tasks.broadcast.tick")
def tick() -> dict[str, int]:
    seconds = run_async(_tick())
    return {"available_seconds": seconds}
