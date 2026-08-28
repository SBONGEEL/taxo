"""سقفُ الوقفة — **يُنبَّه عنده الطرفان ولا تُنهى الرحلة** (§5.10-ب، الفرع أ).

وهو سلوكُ سقف المحطات نفسُه (`tasks/stops.py`)، ولنفس السبب: **الإنهاءُ فعلُ
الكبتن**، ومهمّةٌ دوريةٌ تُنهي رحلةً نيابةً عن إنسانٍ تفعل ما لم يراجعه أحد.

**والنصُّ يختلف بين الطرفين**: الراكبُ يُقال له إن العدّادَ تجاوز حدَّه، والكبتنُ
إن له مخرجاً — **وطرفان لا يُقال لهما الشيءُ نفسُه**.

**و`notified_at` يُختم تحت قفل الصف** فلا يُنبِّه عاملان مرتين.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.pause import RidePause
from app.models.ride import Ride
from app.services import notifications, pauses
from app.tasks.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _sweep() -> int:
    redis = get_redis_client()
    notified = 0

    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(RidePause).where(
                    RidePause.ended_at.is_(None),
                    RidePause.notified_at.is_(None),
                    RidePause.max_minutes_at_pause > 0,
                )
            )
        ).all()

        now = datetime.now(UTC)
        for row in rows:
            if pauses.minutes_of(row, now) <= row.max_minutes_at_pause:
                continue

            # **القفلُ قبل الفحص** كما في كل تغيير حالة: عاملان يقرآن
            # `notified_at IS NULL` معاً فيُنبِّهان مرتين
            locked = await session.scalar(
                select(RidePause)
                .where(RidePause.id == row.id, RidePause.notified_at.is_(None))
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if locked is None:
                continue

            ride = await session.get(Ride, locked.ride_id)
            if ride is None or ride.driver_id is None:  # pragma: no cover
                continue

            locked.notified_at = now
            minutes = str(pauses.minutes_of(locked, now))
            await session.commit()

            driver = await session.get(Driver, ride.driver_id)
            await notifications.publish_pause_limit_exceeded(
                session,
                redis,
                rider_id=ride.rider_id,
                driver_user_id=None if driver is None else driver.user_id,
                ride_id=ride.id,
                minutes=minutes,
            )
            notified += 1

    return notified


@celery_app.task(name="app.tasks.pauses.sweep_pause_limits")
def sweep_pause_limits() -> int:
    count = run_async(_sweep())
    if count:
        logger.info("pause limit notices: %s", count)
    return count
