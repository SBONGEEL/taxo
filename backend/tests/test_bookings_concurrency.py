"""تزامنُ تنفيذ الحجوزات (المرحلة 12-ط).

قاعدةُ المشروع: «مرحلةٌ تمسّ المال أو انتقالَ حالةٍ ليست منتهيةً بلا اختبار
تزامن»، **واختبِرِ الثابتَ الذي يملكه القفلُ نفسُه**.

**والثابتُ الذي يملكه `bookings._locked` هو أن حجزاً واحداً لا يُنفَّذ مرتين.**
ولو حُذف القفلُ لقرأت دورتان متزامنتان `pending` كلتاهما، فتُنشئ الأولى رحلةً
وتُنشئ الثانيةُ **رحلةً ثانيةً** لنفس الحجز — أو تصطدم بـ`uq_rides_active_rider`
فترفع استثناءً يُسقط بقيةَ الدورة. وكلا الوجهين عطبٌ ظاهر: رحلتان لراكبٍ واحدٍ
في موعدٍ واحد، أو حجوزٌ بعده لا تُنفَّذ أبداً.

**ولا يكفي أن يُقاس بعددِ الرحلات وحده**: الفهرسُ الجزئيُّ في القاعدة يمنع
الرحلةَ الثانية على كل حال، فاختبارٌ يعدّ الرحلاتَ **يمرّ ولو حُذف القفل**. فما
يُقاس هنا حالُ الصفِّ نفسِه.

**والتحقق بالحذف أعطى لكلِّ اختبارٍ قفلَه، وما وقع أسوأُ من استثناء:**

- بحذف `_locked` (قفلِ التنفيذ) يخرج الحجزُ **`missed` ورحلتُه موجودة**: قرأت
  الدورتان `pending`، فأنشأت الأولى الرحلةَ واصطدمت الثانيةُ بـ
  `uq_rides_active_rider` فوسمت الحجزَ «لم يُنفَّذ» فوق نجاحٍ وقع. فيصل صاحبَه
  إشعارٌ يقول «لم نطلب لك سيارة» **وسيارةٌ في الطريق إليه**.
- وبحذف قفلِ `cancel` يخرج `['created', 'cancelled']`: رحلةٌ أُنشئت وحجزٌ وُسم
  ملغياً — فيجد نفسَه **في رحلةٍ ألغاها**، وإن ألغاها من شاشتها بعد القبول دفع
  رسمَها.

وكلاهما لا يرفع خطأً ولا يُسجّل شيئاً: صفٌّ يكذب على صاحبه، وهو ما لا يراه إلا
اختبارٌ يقرأ الصفَّ بعد السباق.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.redis_client import get_redis_client
from app.models.booking import RideBooking
from app.models.enums import BookingStatus
from app.models.ride import Ride
from app.models.user import User
from app.services import bookings as bookings_service
from tests.helpers import (
    DROPOFF,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
)

DEADLOCK_TIMEOUT = 20


async def _ready(client: AsyncClient, session_factory) -> uuid.UUID:
    """حجزٌ حلَّ موعدُه وكبتنٌ متاح — يبقى تنفيذُه فقط."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)

    response = await client.post(
        "/me/bookings",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "scheduled_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "vehicle_category": "economy",
        },
        headers=rider["headers"],
    )
    assert response.status_code == 201, response.text
    booking_id = uuid.UUID(response.json()["id"])

    async with session_factory() as session:
        await session.execute(
            update(RideBooking)
            .where(RideBooking.id == booking_id)
            .values(scheduled_at=datetime.now(UTC) + timedelta(minutes=1))
        )
        await session.commit()
    return booking_id


async def test_two_cycles_at_once_execute_one_booking_once(
    client: AsyncClient, session_factory, jordan_settings
):
    """دورتان متزامنتان: رحلةٌ واحدةٌ وجوابٌ هادئٌ للثانية.

    **والتداخلُ بمهلٍ صريحة** لا بأحداث (درسُ 12-ح): الحدثُ يوقظ الأولى فتُثبت
    في لحظةِ بدءِ الثانية، فتقرأ الثانيةُ صفّاً مثبتاً — ويمرّ الاختبارُ ولو حُذف
    القفل. فالمقصودُ أن تقع قراءةُ الثانية **داخل** معاملةِ الأولى المفتوحة.
    """
    booking_id = await _ready(client, session_factory)
    redis = get_redis_client()

    async def first() -> str:
        async with session_factory() as session:
            ride = await bookings_service.execute(session, redis, booking_id)
            await asyncio.sleep(0.4)  # المعاملةُ مفتوحةٌ بينما تقرأ الثانية
            await session.commit()
            return "created" if ride is not None else "skipped"

    async def second() -> str:
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            ride = await bookings_service.execute(session, redis, booking_id)
            await session.commit()
            return "created" if ride is not None else "skipped"

    outcomes = await asyncio.wait_for(
        asyncio.gather(first(), second()), timeout=DEADLOCK_TIMEOUT
    )
    assert sorted(outcomes) == ["created", "skipped"], outcomes

    async with session_factory() as session:
        rides = await session.scalar(select(func.count()).select_from(Ride))
        booking = await session.get(RideBooking, booking_id)
    assert rides == 1
    assert booking.status is BookingStatus.DISPATCHED
    assert booking.ride_id is not None


async def test_cancelling_while_a_cycle_executes_leaves_one_outcome(
    client: AsyncClient, session_factory, jordan_settings
):
    """إلغاءٌ يقع في لحظة التنفيذ: أحدُهما يفوز والآخرُ يُرفض بجوابٍ مفهوم.

    وهذا هو السباقُ الحقيقيُّ في الميزة: صاحبُ الحجز يضغط «ألغِ» في اللحظة التي
    تقرأ فيها الدورةُ صفَّه. وبغير القفل يُلغى الحجزُ **وتُنشأ رحلتُه** — فيجد
    نفسَه في رحلةٍ ألغاها، وتُخصم منه رسومُ إلغائها إن ألغاها ثانيةً بعد قبولها.
    """
    booking_id = await _ready(client, session_factory)
    redis = get_redis_client()

    async def executing() -> str:
        async with session_factory() as session:
            ride = await bookings_service.execute(session, redis, booking_id)
            await asyncio.sleep(0.4)
            await session.commit()
            return "created" if ride is not None else "skipped"

    async def cancelling() -> str:
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            booking = await session.get(RideBooking, booking_id)
            rider = await session.get(User, booking.rider_id)
            try:
                await bookings_service.cancel(session, booking=booking, actor=rider)
                await session.commit()
                return "cancelled"
            except bookings_service.BookingNotAllowed:
                await session.rollback()
                return "refused"

    outcomes = await asyncio.wait_for(
        asyncio.gather(executing(), cancelling()), timeout=DEADLOCK_TIMEOUT
    )
    assert outcomes[0] == "created", outcomes
    assert outcomes[1] == "refused", outcomes

    async with session_factory() as session:
        booking = await session.get(RideBooking, booking_id)
        rides = await session.scalar(select(func.count()).select_from(Ride))
    # الحجزُ نُفِّذ ولم يُلغَ، ورحلتُه واحدة — ومن أراد إلغاءها يُلغيها من شاشتها
    assert booking.status is BookingStatus.DISPATCHED
    assert booking.cancelled_at is None
    assert rides == 1
