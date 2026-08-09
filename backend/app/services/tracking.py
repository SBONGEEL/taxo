"""مراقبة اتصال الكبتن أثناء الرحلة (SPEC القسم 5).

> «انقطاع اتصال الكبتن > 60 ثانية أثناء `in_progress` → تنبيه للطرفين + عدم
> إنهاء الرحلة آلياً.»

الشطر الثاني قيدٌ لا ميزة: لا يوجد في هذا الملف أي مسار يغيّر حالة رحلة.
إنهاء الرحلة فعل بشري بيد الكبتن مهما طال الانقطاع.

«انقطاع 60 ثانية» و«اختفاء مفتاح الحضور» شيء واحد: عمر المفتاح في
`services/geo.py` هو `PRESENCE_TTL_SECONDS` نفسه، فوجوده كافٍ للحكم بلا عدّاد
مستقل يمكن أن يفترق عنه.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.enums import RideStatus
from app.services import geo
from app.ws import events

logger = logging.getLogger(__name__)

# كل خمس ثوانٍ نسأل: أما الحكم نفسه فعمر الحضور (60 ثانية)
CHECK_INTERVAL_SECONDS = 5.0

_tasks: dict[uuid.UUID, asyncio.Task] = {}


async def _run(ride_id: uuid.UUID) -> None:
    from app.services import rides as rides_service

    redis = get_redis_client()
    reported_lost = False

    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

        async with SessionLocal() as session:
            ride = await rides_service.get_ride(session, ride_id)
            if ride.status != RideStatus.IN_PROGRESS or ride.driver_id is None:
                return  # انتهت الرحلة — لا شيء يُراقَب

            present = bool(await redis.exists(geo.presence_key(ride.driver_id)))
            if present == (not reported_lost):
                continue  # لا جديد

            reported_lost = not present
            event = (
                events.RideEvent.DRIVER_CONNECTION_LOST
                if reported_lost
                else events.RideEvent.DRIVER_RECONNECTED
            )
            await events.publish_ride_event(redis, ride, event)


async def _guarded(ride_id: uuid.UUID) -> None:
    try:
        await _run(ride_id)
    except asyncio.CancelledError:
        raise
    except Exception:  # pragma: no cover - المراقبة لا تُسقط شيئاً بسقوطها
        logger.exception("فشل مراقبة اتصال الرحلة %s", ride_id)
    finally:
        _tasks.pop(ride_id, None)


def start(ride_id: uuid.UUID) -> None:
    """تبدأ مع `in_progress` — قبلها الكبتن في الطريق ولا رحلة قائمة تتأثر."""
    if ride_id in _tasks:
        return
    _tasks[ride_id] = asyncio.create_task(_guarded(ride_id), name=f"tracking:{ride_id}")


async def stop(ride_id: uuid.UUID) -> None:
    task = _tasks.pop(ride_id, None)
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def shutdown() -> None:
    for ride_id in list(_tasks):
        await stop(ride_id)
