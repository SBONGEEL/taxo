"""الرحلات المجدولة (SPEC القسم 5.11، المرحلة 12-ط).

قرارُ المالك يُختبر حرفياً: **الحجزُ ليس رحلة**. فمن هو في رحلةٍ الآن يحجز لغد،
ولا صفَّ رحلةٍ يُنشأ قبل التنفيذ، والسعرُ يُحسب عند التنفيذ لا عند الحجز،
والإلغاءُ قبل التسليم مجانيٌّ بلا رسم.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.booking import RideBooking
from app.models.enums import BookingStatus, RideStatus
from app.models.ride import Ride
from app.services import bookings as bookings_service
from tests.helpers import (
    DROPOFF,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    request_ride,
    rider_session,
    wait_for_status,
)


def _soon(minutes: int = 60) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


async def _book(
    client: AsyncClient, headers: dict, *, minutes: int = 60, **overrides
) -> tuple[int, dict]:
    body = {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "scheduled_at": _soon(minutes),
        "vehicle_category": "economy",
    } | overrides
    response = await client.post("/me/bookings", json=body, headers=headers)
    return response.status_code, response.json()


async def _due_now(session_factory, booking_id: str) -> None:
    """يُقرّب الموعدَ حتى يصير مستحقاً — الساعةُ مدخلُ هذه الميزة فتُزوَّر."""
    async with session_factory() as session:
        await session.execute(
            update(RideBooking)
            .where(RideBooking.id == uuid.UUID(booking_id))
            .values(scheduled_at=datetime.now(UTC) + timedelta(minutes=1))
        )
        await session.commit()


# ------------------------------------------------------------------ المفتاح


async def test_the_feature_is_refused_where_the_flag_is_off(
    client: AsyncClient, session_factory, jordan_settings
):
    """مفتاحٌ مطفأٌ يرفض **ما يُرسل** لا يخفي زرّاً فقط."""
    rider = await rider_session(client)
    status, body = await _book(client, rider["headers"])
    assert status == 403, body
    assert body["code"] == "scheduled_rides_unavailable"


# ------------------------------------------------------------------ الحجز


async def test_a_booking_creates_no_ride_row(
    client: AsyncClient, session_factory, jordan_settings
):
    """**القرارُ المحوريّ**: لا صفَّ رحلةٍ قبل التنفيذ.

    ولو أُنشئت رحلةٌ بحالة `scheduled` لكسرت `uq_rides_active_rider` ولجمّدت
    عمولةً قبل أسبوع ولدخلت كلَّ قائمةِ حالاتٍ نشطة.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    status, booking = await _book(client, rider["headers"])
    assert status == 201, booking
    assert booking["status"] == "pending"
    assert booking["ride_id"] is None

    async with session_factory() as session:
        rides = await session.scalar(select(func.count()).select_from(Ride))
    assert rides == 0


async def test_a_rider_in_a_ride_can_still_book_for_tomorrow(
    client: AsyncClient, session_factory, jordan_settings
):
    """نصفُ سببِ الجدول المستقل: «رحلةٌ نشطةٌ واحدة» لا محلَّ له على حجز."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await request_ride(client, rider["headers"])

    status, booking = await _book(client, rider["headers"], minutes=24 * 60)
    assert status == 201, booking


async def test_the_estimate_is_stored_as_an_estimate_not_a_fare(
    client: AsyncClient, session_factory, jordan_settings
):
    """يُخزَّن تقديرٌ للعرض — والأجرةُ تُحسب عند التنفيذ (القسم 5.11)."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    assert Decimal(booking["estimated_fare_at_booking"]) > 0
    # ولا حقلَ اسمُه `fare` في المخرَج أصلاً — الاسمُ نفسُه جزءٌ من القاعدة
    assert "fare" not in booking


async def test_a_booking_too_soon_is_refused_with_a_reason(
    client: AsyncClient, session_factory, jordan_settings
):
    """حجزٌ بعد خمسِ دقائق طلبٌ فوريٌّ بطريقٍ أطول — ويُربك صاحبَه."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    status, body = await _book(client, rider["headers"], minutes=5)
    assert status == 422, body
    assert "دقيقة" in body["detail"]


async def test_a_booking_beyond_the_horizon_is_refused(
    client: AsyncClient, session_factory, jordan_settings
):
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    status, body = await _book(client, rider["headers"], minutes=60 * 24 * 45)
    assert status == 422, body


async def test_open_bookings_are_capped_per_rider(
    client: AsyncClient, session_factory, jordan_settings
):
    """حارسٌ ضد ملءِ الجدول بوعودٍ لا تُنفَّذ."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    for index in range(bookings_service.MAX_OPEN_PER_RIDER):
        status, body = await _book(client, rider["headers"], minutes=60 + index)
        assert status == 201, body

    status, body = await _book(client, rider["headers"], minutes=200)
    assert status == 409, body
    assert body["code"] == "booking_not_allowed"


async def test_a_gendered_booking_is_refused_where_the_service_is_off(
    client: AsyncClient, session_factory, jordan_settings
):
    """**الرفضُ عند الحجز لا عند التنفيذ**: وعدٌ بكبتنةٍ في سوقٍ بلا خدمةٍ يُخلف
    بعد أسبوع، والرفضُ الآن مفهومٌ ويترك لصاحبته خياراً.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    status, body = await _book(
        client, rider["headers"], gender_preference="female"
    )
    assert status == 409, body
    assert body["code"] == "women_service_unavailable"


# ------------------------------------------------------------------ الإلغاء


async def test_cancelling_before_dispatch_is_free_and_leaves_no_ride(
    client: AsyncClient, session_factory, jordan_settings
):
    """مجاناً بلا استثناء: الرسمُ تعويضُ كبتنٍ تحرّك، ولا كبتنَ بعد."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])

    response = await client.delete(
        f"/me/bookings/{booking['id']}", headers=rider["headers"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    async with session_factory() as session:
        rides = await session.scalar(select(func.count()).select_from(Ride))
    assert rides == 0


async def test_a_cancelled_booking_is_not_executed(
    client: AsyncClient, session_factory, jordan_settings
):
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await client.delete(f"/me/bookings/{booking['id']}", headers=rider["headers"])
    await _due_now(session_factory, booking["id"])

    async with session_factory() as session:
        assert await bookings_service.due_ids(session) == []


async def test_another_rider_cannot_cancel_my_booking(
    client: AsyncClient, session_factory, jordan_settings
):
    """الملكيةُ تُفحص على كل مسار (القسم 14) — ولا IDOR."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    from tests.helpers import OTHER_RIDER

    mine = await rider_session(client)
    _status, booking = await _book(client, mine["headers"])
    other = await rider_session(client, OTHER_RIDER)

    response = await client.delete(
        f"/me/bookings/{booking['id']}", headers=other["headers"]
    )
    assert response.status_code == 404, response.text


# ------------------------------------------------------------------ التنفيذ


async def test_execution_creates_the_ride_through_the_one_door(
    client: AsyncClient, session_factory, jordan_settings
):
    """التنفيذُ يستدعي `rides.request_ride` — فتُجمَّد العمولةُ ويُحسب السعر."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await _due_now(session_factory, booking["id"])

    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        due = await bookings_service.due_ids(session)
        assert [str(item) for item in due] == [booking["id"]]
        ride = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()

    assert ride is not None
    assert ride.commission_percent_at_ride is not None
    assert Decimal(ride.estimated_fare) > 0

    read = await client.get(f"/me/bookings", headers=rider["headers"])
    row = read.json()[0]
    assert row["status"] == "dispatched"
    assert row["ride_id"] == str(ride.id)
    # **حالُ الرحلة مقروءةٌ من الرحلة** لا من عمودٍ على الحجز
    assert row["ride_status"] in {"requested", "searching"}


async def test_the_booked_time_is_frozen_on_the_ride_and_reaches_the_offer(
    client: AsyncClient, session_factory, jordan_settings
):
    """**الشارةُ تُقرأ من الرحلة**: `scheduled_for` مجمَّدٌ عليها لا مقروءٌ من الحجز.

    و**حقلٌ يقرؤه التطبيق ولا يرسله أحد شارةٌ لا تظهر أبداً** — وهي بصمةُ عطبٍ
    شحنت في هذا المشروع (`gender_preference` في إطار العرض). فيُفحص الحقلُ في
    الصفِّ وفي مخرَج المسار معاً.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await _due_now(session_factory, booking["id"])

    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        ride = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()
    assert ride is not None

    # في الصف: مجمَّدٌ بموعد الحجز نفسه
    async with session_factory() as session:
        row = await session.get(Ride, ride.id)
        stored = row.scheduled_for
        booked = await session.get(RideBooking, uuid.UUID(booking["id"]))
    assert stored is not None
    assert stored == booked.scheduled_at

    # وفي المخرَج الذي يقرؤه التطبيقان (وهو نفسُه إطارُ العرض)
    read = await client.get(f"/rides/{ride.id}", headers=rider["headers"])
    assert read.json()["scheduled_for"] is not None

    # **ورحلةٌ فوريةٌ تبقى `null`** — لا افتراضَ سخيّ
    await client.post(f"/rides/{ride.id}/cancel", json={}, headers=rider["headers"])
    instant = await request_ride(client, rider["headers"])
    assert instant["scheduled_for"] is None


async def test_a_second_cycle_does_not_execute_the_same_booking_twice(
    client: AsyncClient, session_factory, jordan_settings
):
    """الحالةُ هي الأثر: `dispatched` لا تُنفَّذ ثانيةً."""
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await _due_now(session_factory, booking["id"])

    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        first = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()
        second = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()

    assert first is not None
    assert second is None
    async with session_factory() as session:
        rides = await session.scalar(select(func.count()).select_from(Ride))
    assert rides == 1


async def test_a_rider_already_riding_at_execution_time_is_told_not_dropped(
    client: AsyncClient, session_factory, jordan_settings
):
    """**`missed` بإشعارٍ لا حذفٌ صامت**: الفهرسُ يمنع رحلةً ثانية، والصمتُ يجعله
    يظنّ أن سيارةً في الطريق.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await request_ride(client, rider["headers"])  # رحلةٌ جارية الآن
    await _due_now(session_factory, booking["id"])

    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        result = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
    assert result is None

    read = await client.get("/me/bookings", headers=rider["headers"])
    assert read.json()[0]["status"] == "missed"

    inbox = await client.get("/me/notifications", headers=rider["headers"])
    kinds = [row["kind"] for row in inbox.json()]
    assert "booking_missed" in kinds


async def test_a_booking_whose_dispatch_found_nobody_is_reported_once(
    client: AsyncClient, session_factory, jordan_settings
):
    """**من حجز ونام يستحق أن يُوقَظ** — ونصُّ الرحلة الفورية لا يقول أيُّ حجز.

    و`notified_at` يمنع التكرار: دورةٌ كلَّ دقيقة تعني ألفَ إشعارٍ في يوم.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])
    await _due_now(session_factory, booking["id"])

    from app.core.redis_client import get_redis_client

    # لا كبتنَ متاحٌ أصلاً، فالتوزيعُ ينتهي `no_driver_found`
    async with session_factory() as session:
        ride = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()
    assert ride is not None

    from app.services import dispatch

    dispatch.start(ride.id)
    await wait_for_status(
        client, rider["headers"], str(ride.id), RideStatus.NO_DRIVER_FOUND.value
    )

    async with session_factory() as session:
        told = await bookings_service.report_failures(session, get_redis_client())
        assert told == 1
        again = await bookings_service.report_failures(session, get_redis_client())
        assert again == 0

    inbox = await client.get("/me/notifications", headers=rider["headers"])
    kinds = [row["kind"] for row in inbox.json()]
    assert "booking_no_driver" in kinds


async def test_turning_the_flag_off_does_not_break_a_standing_promise(
    client: AsyncClient, session_factory, jordan_settings
):
    """**الإطفاءُ يمنع الجديدَ ولا يخلف وعداً قائماً** — قاعدةُ المحطات نفسُها.

    من رتّب موعدَه على حجزٍ قائم يُنفَّذ حجزُه؛ وإلا صار المفتاحُ أداةً تُلغي
    وعوداً بلا أن يعرف صاحبُها.
    """
    await enable_features(session_factory, "scheduled_rides_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    _status, booking = await _book(client, rider["headers"])

    # يُطفأ المفتاحُ بعد الحجز
    from app.models.enums import CountryCode, FeatureKey
    from app.services import settings_service

    async with session_factory() as session:
        await settings_service.set_flag(
            session,
            country_code=CountryCode.JO,
            feature_key=FeatureKey.SCHEDULED_RIDES_ENABLED,
            enabled=False,
        )
        await session.commit()

    await _due_now(session_factory, booking["id"])
    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        ride = await bookings_service.execute(
            session, get_redis_client(), uuid.UUID(booking["id"])
        )
        await session.commit()
    assert ride is not None

    # ولا حجزَ جديدٌ يُقبل بعد الإطفاء
    status, _body = await _book(client, rider["headers"], minutes=300)
    assert status == 403
