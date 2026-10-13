"""مراقبة اتصال الكبتن أثناء الرحلة (SPEC القسم 5).

> «انقطاع اتصال الكبتن > 60 ثانية أثناء `in_progress` → تنبيه للطرفين + عدم
> إنهاء الرحلة آلياً.»

الشطر الثاني قيدٌ لا ميزة: لا يوجد في هذا الملف أي مسار يغيّر حالة رحلة.
إنهاء الرحلة فعل بشري بيد الكبتن مهما طال الانقطاع.

«انقطاع 60 ثانية» كان «اختفاء مفتاح الحضور» نفسَه: عمر المفتاح كان ستين.
**وصار العمرُ من سياسة البثّ** (§٧٥-ج، النبضةُ وأطولُ فاصلٍ وهامش — نحو دقيقتين)،
**فالحكمُ هنا بختم `seen`** (آخرُ اتّصال) **لا بوجود المفتاح وحدَه** — فيبقى
«ستون ثانية» كما نصّ القسم 5، **ودفعاتُ الرحلة كلَّ خمسَ عشرةَ ثانيةً تجدّده**.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.enums import RideStatus
from app.services import geo
from app.ws import events

logger = logging.getLogger(__name__)

# كل خمس ثوانٍ نسأل: أما الحكم نفسه فستون ثانيةً بلا اتّصال (SPEC القسم 5)
CHECK_INTERVAL_SECONDS = 5.0
LOST_AFTER_SECONDS = 60
#: **والرحلةُ نفسُها تُقرأ من القاعدة كلَّ دقيقة** لا كلَّ خمس ثوانٍ (§٧٥-د/٢)
RECHECK_SECONDS = 60.0

_tasks: dict[uuid.UUID, asyncio.Task] = {}


async def _present(redis, driver_id) -> bool:
    # و`at` لحضورٍ كتبته شيفرةٌ أقدمُ بلا `seen` — فلا يُعلَن انقطاعٌ لحظةَ الرفع
    seen, at = await redis.hmget(geo.presence_key(driver_id), ["seen", "at"])
    seen = seen or at
    seen = seen.decode() if isinstance(seen, bytes) else seen
    return bool(seen) and str(seen).isdigit() and time.time() - int(seen) < LOST_AFTER_SECONDS


async def _run(ride_id: uuid.UUID) -> None:
    """**Redis كلَّ خمس ثوانٍ، والقاعدةُ حين يتغيّر الحالُ أو كلَّ `RECHECK_SECONDS`** (§٧٥-د/٢، قِيس في المرحلة ١: كانت القاعدةُ تُقرأ
    كلَّ خمس ثوانٍ لكلِّ رحلةٍ جارية — ٦٠ استعلاماً في الثانية عند ٣٠٠ رحلة). **والرحلةُ تُقرأ قبل كلِّ إعلانٍ** فلا يُعلَن انقطاعٌ لرحلةٍ
    انتهت، **وكلَّ دقيقةٍ** لتنتهي المهمّةُ إن انتهت الرحلةُ في عاملٍ آخر (فـ`stop` هناك لا يبلغها).
    """
    from app.services import rides as rides_service

    redis = get_redis_client()
    reported_lost = False
    driver_id = None
    checked_at = 0.0

    while True:
        if driver_id is None or time.monotonic() - checked_at >= RECHECK_SECONDS:
            async with SessionLocal() as session:
                ride = await rides_service.get_ride(session, ride_id)
            if ride.status != RideStatus.IN_PROGRESS or ride.driver_id is None:
                return  # انتهت الرحلة — لا شيء يُراقَب
            driver_id = ride.driver_id
            checked_at = time.monotonic()

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

        present = await _present(redis, driver_id)
        if present == (not reported_lost):
            continue  # لا جديد

        async with SessionLocal() as session:
            ride = await rides_service.get_ride(session, ride_id)
        if ride.status != RideStatus.IN_PROGRESS or ride.driver_id is None:
            return
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
