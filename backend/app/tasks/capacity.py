"""دورةُ إنذار السعة (SPEC §٧٦/٢) — كلَّ دقيقة: يُعدّ المتّصلون، وتُنذَر الإدارةُ إن بلغوا العتبة (مرّةً كلَّ نصف ساعة).

والمنطقُ في `services/capacity.py` وهذه غلافٌ رقيق — كـ`tasks/broadcast.py`.
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.services import capacity
from app.tasks.celery_app import celery_app, run_async


async def _check() -> dict[str, int | bool]:
    async with SessionLocal() as session:
        snap = await capacity.check(session, get_redis_client())
        await session.commit()
    return {"captains": snap.captains, "riders": snap.riders, "alerting": snap.alerting}


@celery_app.task(name="app.tasks.capacity.check")
def check() -> dict[str, int | bool]:
    return run_async(_check())
