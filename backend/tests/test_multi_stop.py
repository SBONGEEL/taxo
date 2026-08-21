"""تعدد الوجهات — المحطات الوسيطة (SPEC القسم 5.10، المرحلة 12-ب).

**كلُّ قاعدةٍ هنا مُتحقَّقٌ منها بالحذف**: تُحذف القاعدة من الكود فيسقط
اختبارُها. وأهمُّها ثلاث:

- **المفتاحُ يمنع الطلب الجديد ولا يقطع الجاري**: رحلةٌ بمحطاتٍ بدأت قبل
  الإطفاء تكمل، وطلبٌ جديد يُرفض.
- **المعدلاتُ مجمَّدةٌ على الرحلة**: تعديلُ التسعيرة بعد الطلب لا يحرّك
  عدّاداً يقرؤه راكبٌ واقفٌ الآن.
- **الزمنُ من ختم الخلفية**: لا رقمَ من الواجهة يدخل الحساب.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import FeatureKey, RideStatus
from app.models.pricing import PricingRule
from app.models.ride import Ride, RideStop
from app.services import pricing
from tests.helpers import (
    DRIVER,
    PICKUP,
    DROPOFF,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    started_ride,
)

STOP_A = {"lat": 31.9600, "lng": 35.9050, "address": "الصيدلية"}
STOP_B = {"lat": 31.9700, "lng": 35.9000, "address": "المخبز"}


async def set_stop_pricing(
    session_factory,
    *,
    fee: str = "0.500",
    free_minutes: int = 3,
    price_per_min: str = "0.100",
    max_wait: int = 20,
) -> None:
    """يضبط حقول المحطات في تسعيرة الأردن — كما يضبطها المشرف من اللوحة."""
    async with session_factory() as session:
        rules = (await session.scalars(select(PricingRule))).all()
        for rule in rules:
            rule.stop_fee = Decimal(fee)
            rule.stop_free_minutes = free_minutes
            rule.stop_price_per_min = Decimal(price_per_min)
            rule.stop_max_wait_minutes = max_wait
        await session.commit()


async def request_with_stops(
    client: AsyncClient, headers: dict, stops: list[dict]
) -> AsyncClient:
    return await client.post(
        "/rides",
        headers=headers,
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "pickup_address": "الانطلاق",
            "dropoff_address": "الوجهة",
            "vehicle_category": "economy",
            "stops": stops,
        },
    )


# --------------------------------------------------------------- المفتاح


async def test_stops_are_refused_while_the_flag_is_off(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**الفحصُ عند الإنشاء لا عند العرض**: واجهةٌ تخفي الزر لا تمنع طلباً بيد.

    ولا تُبتلع المحطات صامتةً: راكبٌ طلب ثلاث وجهاتٍ فسار الكبتن إلى واحدة
    أسوأ من طلبٍ يُرفض بسببه.
    """
    rider = await rider_session(client)
    response = await request_with_stops(client, rider["headers"], [STOP_A])

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "multi_stop_unavailable"


async def test_a_running_multi_stop_ride_survives_the_flag_being_turned_off(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """الإطفاءُ يمنع الطلبات الجديدة وحدها (SPEC القسم 4).

    مفتاحٌ يقطع رحلةً في منتصفها يترك راكباً بين محطتين — والمحطاتُ مجمَّدةٌ
    على الرحلة أصلاً فلا شيء يقرؤها من الإعدادات بعد الإنشاء.
    """
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory)

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    created = await request_with_stops(client, rider["headers"], [STOP_A])
    assert created.status_code == 201, created.text
    ride_id = created.json()["id"]

    # يُطفأ المفتاح والرحلة قائمة
    flipped = await client.put(
        "/admin/settings/feature-flags",
        headers=admin_headers,
        json={
            "country_code": "JO",
            "feature_key": FeatureKey.MULTI_STOP_ENABLED.value,
            "enabled": False,
        },
    )
    assert flipped.status_code == 200, flipped.text

    # الرحلةُ ما زالت تحمل محطتها ويمكن قراءتها
    read = await client.get(f"/rides/{ride_id}", headers=rider["headers"])
    assert read.status_code == 200, read.text
    assert len(read.json()["stops"]) == 1

    # والطلبُ الجديد يُرفض
    again = await request_with_stops(client, rider["headers"], [STOP_A])
    assert again.status_code in (409, 422)


# --------------------------------------------------------------- التسعير


async def test_stop_fee_enters_the_estimate_and_the_route_covers_every_leg(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رسمُ المحطة المقطوع يدخل التقدير، والمسافةُ مسافةُ الطريق كلِّه.

    ومسافةُ الخادم الوهمي تكبر بعدد السيقان (`conftest.stub_mapbox`)، فرحلةٌ
    بمحطةٍ تمر بساقين — وبغير ذلك مرّ تسعيرٌ لا يمر بالمحطات أصلاً.
    """
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory, fee="0.500")
    rider = await rider_session(client)

    direct = await client.post(
        "/rides/estimate",
        headers=rider["headers"],
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
    )
    with_stop = await client.post(
        "/rides/estimate",
        headers=rider["headers"],
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "stops": [STOP_A],
        },
    )
    assert direct.status_code == 200 and with_stop.status_code == 200

    plain = direct.json()
    staged = with_stop.json()
    # ساقان بدل واحدة
    assert Decimal(staged["distance_km"]) == Decimal(plain["distance_km"]) * 2
    # والفرقُ في الأجرة يشمل رسمَ المحطة المقطوع
    assert Decimal(staged["estimated_fare"]) > Decimal(plain["estimated_fare"])


async def test_more_than_two_intermediate_stops_are_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """ثلاثُ وجهاتٍ في الرحلة = محطتان وسيطتان + الأخيرة."""
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    rider = await rider_session(client)

    response = await request_with_stops(
        client, rider["headers"], [STOP_A, STOP_B, {"lat": 31.98, "lng": 35.88}]
    )
    assert response.status_code == 422, response.text


async def test_waiting_rates_are_frozen_on_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تعديلُ التسعيرة بعد الطلب لا يحرّك عدّاداً يقرؤه راكبٌ واقفٌ الآن.

    وبحذف التجميد (قراءةُ الإعداد لحظة الحساب) يسقط هذا الاختبار: الرسمُ
    يصير بالسعر الجديد.
    """
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory, price_per_min="0.100", free_minutes=3)

    rider = await rider_session(client)
    created = await request_with_stops(client, rider["headers"], [STOP_A])
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["stop_price_per_min"] == "0.100"
    assert body["stop_free_minutes"] == 3

    # المشرفُ يضاعف السعر بعد الطلب
    await set_stop_pricing(session_factory, price_per_min="9.000", free_minutes=0)

    read = await client.get(f"/rides/{body['id']}", headers=rider["headers"])
    assert read.json()["stop_price_per_min"] == "0.100"
    assert read.json()["stop_free_minutes"] == 3


# ---------------------------------------------------------- آلة الحالات


async def _ride_with_stop(client, session_factory, *, stops=(STOP_A,)):
    """رحلةٌ جارية بمحطةٍ وسيطة — الأساس لكل اختبار انتقال."""
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await started_ride(
        client, rider["headers"], driver, stops=[dict(stop) for stop in stops]
    )
    return rider, driver, ride


async def test_arrive_then_resume_moves_the_leg_and_closes_the_clock(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    arrived = await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )
    assert arrived.status_code == 200, arrived.text
    assert arrived.json()["status"] == "at_stop"
    assert arrived.json()["stops"][0]["arrived_at"] is not None
    assert arrived.json()["current_leg"] == 0

    resumed = await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/resume", headers=driver["headers"]
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "in_progress"
    assert resumed.json()["stops"][0]["resumed_at"] is not None
    # **الساقُ الثانية بدأت** — ومنها تُنسب نقاط المسار
    assert resumed.json()["current_leg"] == 1


async def test_a_stop_cannot_be_arrived_at_twice_or_resumed_before_arrival(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    early = await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/resume", headers=driver["headers"]
    )
    assert early.status_code == 409, early.text

    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )
    again = await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )
    assert again.status_code == 409, again.text


async def test_a_ride_at_a_stop_cannot_be_cancelled(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """لا إلغاء من `at_stop` كما لا إلغاء من `in_progress` — الراكب في السيارة."""
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )

    for headers in (rider["headers"], driver["headers"]):
        cancelled = await client.post(
            f"/rides/{ride['id']}/cancel", json={"reason": "بدا لي"}, headers=headers
        )
        assert cancelled.status_code == 409, cancelled.text


async def test_the_driver_may_end_the_ride_at_a_stop(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مخرجُ السقف: `at_stop → completed` بفعل الكبتن (SPEC القسم 5.10)."""
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )

    ended = await client.post(
        f"/rides/{ride['id']}/complete", headers=driver["headers"]
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "completed"


async def test_a_rider_at_a_stop_cannot_request_a_second_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """`at_stop` رحلةٌ جارية — والفهرسُ الجزئي هو الحارس الأخير."""
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )

    second = await request_with_stops(client, rider["headers"], [])
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "ride_already_active"


# ------------------------------------------------------------- الانتظار


async def test_waiting_charge_is_measured_from_the_backend_stamp(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الرسمُ يُحسب من `arrived_at` — و**المجانيةُ لكل محطة لا للرحلة**.

    الختمُ يُزاح في القاعدة بدل انتظارٍ حقيقي؛ وهذا بالضبط ما يجعل القياس
    من الخلفية قابلاً للاختبار أصلاً — مؤقتُ واجهةٍ لا يُزاح.
    """
    rider, driver, ride = await _ride_with_stop(
        client, session_factory, stops=(STOP_A, STOP_B)
    )
    assert len(ride["stops"]) == 2

    first = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{first}/arrive", headers=driver["headers"]
    )

    # ثماني دقائق وقوفاً: خمسٌ فوق المجانية الثلاث
    async with session_factory() as session:
        stop = await session.get(RideStop, first)
        stop.arrived_at = datetime.now(UTC) - timedelta(minutes=8)
        await session.commit()

    read = await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    body = read.json()
    assert Decimal(body["waiting_charge"]) == Decimal("0.500")  # ٥ × ٠.١٠٠
    assert Decimal(body["stops"][0]["waited_minutes"]) >= Decimal("8")


async def test_free_minutes_are_per_stop_not_per_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """من وقف دقيقتين عند محطتين لم ينتظر أحداً أربع دقائق.

    وبجمع المهل للرحلة كلِّها يصير الرسمُ غيرَ صفر هنا — فيسقط الاختبار.
    """
    rider, driver, ride = await _ride_with_stop(
        client, session_factory, stops=(STOP_A, STOP_B)
    )
    now = datetime.now(UTC)

    async with session_factory() as session:
        stops = (
            await session.scalars(
                select(RideStop)
                .where(RideStop.ride_id == ride["id"])
                .order_by(RideStop.sequence)
            )
        ).all()
        for stop in stops:
            stop.arrived_at = now - timedelta(minutes=2)
            stop.resumed_at = now
        await session.commit()

    read = await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    # دقيقتان عند كلٍّ منهما، والمجانيةُ ثلاثٌ لكل محطة ⇒ لا رسم
    assert Decimal(read.json()["waiting_charge"]) == Decimal("0.000")


async def test_waiting_is_added_to_the_final_fare(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رسمُ الانتظار يدخل `final_fare` — وهو ما يُحصَّل في شاشة الدفع."""
    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )

    async with session_factory() as session:
        stop = await session.get(RideStop, stop_id)
        stop.arrived_at = datetime.now(UTC) - timedelta(minutes=13)
        await session.commit()

    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/resume", headers=driver["headers"]
    )
    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text

    body = done.json()
    # عشرُ دقائق محتسَبة × ٠.١٠٠ = ١.٠٠٠ فوق أجرة الطريق
    assert Decimal(body["final_fare"]) == Decimal(body["estimated_fare"]) + Decimal(
        "1.000"
    )


async def test_the_wait_cap_notifies_both_parties_once_and_never_ends_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """المهمةُ تُخطر ولا تُنهي (SPEC القسم 5.10)، و`notified_at` يمنع التكرار."""
    from app.services import rides as rides_service

    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )

    async with session_factory() as session:
        stop = await session.get(RideStop, stop_id)
        stop.arrived_at = datetime.now(UTC) - timedelta(minutes=25)
        await session.commit()

    async with session_factory() as session:
        due = await rides_service.stops_over_max_wait(session)
    assert [str(pair[1]) for pair in due] == [stop_id]

    async with session_factory() as session:
        marked = await rides_service.mark_stop_notified(session, stop_id)
        assert marked is not None
        await session.commit()

    # الدورةُ الثانية لا تجد شيئاً — والرحلةُ ما زالت واقفة لا منتهية
    async with session_factory() as session:
        assert await rides_service.stops_over_max_wait(session) == []
        again = await rides_service.mark_stop_notified(session, stop_id)
        assert again is None

        row = await session.get(Ride, ride["id"])
        assert row.status is RideStatus.AT_STOP


async def test_zero_max_wait_means_no_cap_at_all(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """صفرٌ يعني «لا سقف» لا «سقفٌ مقداره صفر» — وإلا نبّه لحظةَ الوصول."""
    from app.services import rides as rides_service

    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory, max_wait=0)

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await started_ride(client, rider["headers"], driver, stops=[dict(STOP_A)])

    stop_id = ride["stops"][0]["id"]
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )
    async with session_factory() as session:
        stop = await session.get(RideStop, stop_id)
        stop.arrived_at = datetime.now(UTC) - timedelta(hours=3)
        await session.commit()

        assert await rides_service.stops_over_max_wait(session) == []


async def test_route_points_are_attributed_to_their_leg(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """نقاطُ ما بعد الاستئناف تُنسب إلى الساق التالية (SPEC القسم 5.10)."""
    from app.models.ride import RideRoutePoint
    from tests.helpers import broadcast_location

    rider, driver, ride = await _ride_with_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    await broadcast_location(client, driver, 31.9560, 35.9090)
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/arrive", headers=driver["headers"]
    )
    await client.post(
        f"/rides/{ride['id']}/stops/{stop_id}/resume", headers=driver["headers"]
    )

    # المهلةُ بين العيّنتين مفتاحُ Redis نفسه — يُمحى ليُلتقط ما بعد الاستئناف
    from app.core.redis_client import get_redis_client
    from app.services import route as route_service

    await get_redis_client().delete(route_service.sample_key(ride["id"]))
    await broadcast_location(client, driver, 31.9680, 35.9010)

    async with session_factory() as session:
        legs = (
            await session.scalars(
                select(RideRoutePoint.leg)
                .where(RideRoutePoint.ride_id == ride["id"])
                .order_by(RideRoutePoint.created_at)
            )
        ).all()
    assert legs == [0, 1], legs

# ------------------------------------------------- تفصيلُ ما وُقف لأجله


async def test_the_stops_charge_is_published_summed_and_quantized(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**المجموعُ يُنشر لا الوحدةُ وحدَها** — فالشاشةُ لا تضرب مالاً (§14).

    وبحذف `stops_charge` من `RideOut` يسقط هذا الاختبار: يبقى `stop_fee`
    وحدَه، فتضطرّ الشاشةُ إلى ضربه في العدد — وهو ما يجعلها طرفاً في تحديد
    ما يُدفع.

    **والشكلُ يُقاس كما تُقاس القيمة** (الشكلُ السابع): مبلغٌ يُسلسَل `"1"`
    بدل `"1.000"` يُقرأ على شاشةٍ كلُّ أرقامها بثلاث خانات.
    """
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory, fee="0.500")

    rider = await rider_session(client)
    created = await request_with_stops(client, rider["headers"], [STOP_A, STOP_B])
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["stop_fee"] == "0.500"
    assert body["stops_charge"] == "1.000"
    assert body["waiting_charge"] == "0.000"
    assert body["pause_charge"] == "0.000"


async def test_a_ride_with_no_stops_publishes_zeroes_for_the_screen_to_hide(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**صفرٌ يُنشر ولا يُخفى في الخلفية**: الإخفاءُ قرارُ شاشة.

    ولو ردّت الخلفيةُ `null` لاضطرّت كلُّ شاشةٍ إلى تمييز «لا محطات» عن «لم
    يصل الحقل» — وهو تمييزٌ لا معنى له، ومن ينساه يرسم `undefined`.
    """
    rider = await rider_session(client)
    created = await request_with_stops(client, rider["headers"], [])
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["stops_charge"] == "0.000"
    assert body["waiting_charge"] == "0.000"
    assert body["pause_charge"] == "0.000"


async def test_the_panel_reads_the_same_numbers_the_two_apps_read(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    admin_headers: dict[str, str],
) -> None:
    """**بابان ينشران الشيءَ نفسَه** (الشكلُ الثامن) — فيُقارَنان لا يُفترضان.

    وقعت الحاجةُ إليه لأن المشرفَ يقرأ رقماً ليفصل في نزاع: رقمٌ في اللوحة
    يخالف ما رآه الراكبُ على شاشة الدفع **يجعل الفصلَ نفسَه خطأً**.
    """
    rider, driver, ride = await _ride_with_stop(
        client, session_factory, stops=(STOP_A, STOP_B)
    )
    seen = await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    app_view = seen.json()

    panel = await client.get(f"/admin/rides/{ride['id']}", headers=admin_headers)
    assert panel.status_code == 200, panel.text
    panel_view = panel.json()

    # **`assert` قبل المقارنة**: قائمتان فارغتان تتطابقان ولا تحرسان شيئاً
    assert app_view["stops_charge"] != "0.000"
    for field in ("stop_fee", "stops_charge", "waiting_charge", "pause_charge"):
        assert panel_view[field] == app_view[field], field
    assert panel_view["stops_count"] == len(app_view["stops"])


async def test_the_estimate_carries_the_waiting_terms_before_the_ride_exists(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«الشاشةُ تقول سعرَه قبل الطلب»** (§5.10) — ولا شاشةَ تقوله بلا رقم.

    ومحلُّه التقديرُ لا `GET /config`: الأربعةُ لكلِّ (دولة × فئة)، والتقديرُ
    هو الطلبُ الوحيد الذي عُرفت فيه الفئةُ المختارة قبل إنشاء الرحلة.

    وبحذف الحقول من `RideEstimateOut` يسقط: يعود التطبيقُ إلى جملةٍ تقول إن
    للانتظار سعراً ولا تقوله.
    """
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(
        session_factory, fee="0.500", free_minutes=2, price_per_min="0.100"
    )
    rider = await rider_session(client)

    quoted = await client.post(
        "/rides/estimate",
        headers=rider["headers"],
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()

    assert body["stop_fee"] == "0.500"
    assert body["stop_free_minutes"] == 2
    assert body["stop_price_per_min"] == "0.100"

    # **وما يُقال قبل الطلب هو ما يُجمَّد عليه** — ولولا هذا لكان الوعدُ
    # صادقاً في شاشةٍ وكاذباً في فاتورة
    created = await request_with_stops(client, rider["headers"], [STOP_A])
    assert created.status_code == 201, created.text
    ride = created.json()
    assert ride["stop_fee"] == body["stop_fee"]
    assert ride["stop_free_minutes"] == body["stop_free_minutes"]
    assert ride["stop_price_per_min"] == body["stop_price_per_min"]
