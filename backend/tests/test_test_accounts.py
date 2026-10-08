"""حسابا التجربة على الإنتاج (SPEC §٦٥-ج) — **عزلٌ في الاتجاهين، وخارجَ كلِّ عدّ، ولا مالَ حقيقيّ**.

ما يحرسه هذا الملف، **وكلُّ قاعدةٍ فيه تسقط بحذف سطرها**:

- **العزل**: طلبٌ حقيقيٌّ لا يُعرض على كبتن تجربةٍ ولو كان أقرب، وطلبُ راكبِ التجربة لا يبلغ إلا كبتنَ التجربة ولو كان
  الحقيقيُّ أقرب، **ولا يأخذه حقيقيٌّ بالباب المحجوز** (`rides._take`). وخريطةُ الراكب وخريطةُ الكبتن تريان العالمَ نفسَه.
  **والأسواقُ خارج التوزيع** — المشوارُ الثابت والحجزُ المضمون وبين المدن — لا تعرض عالماً على الآخر.
- **خارجَ العدّ**: النظرةُ العامّة (الرحلات · الإيراد · المتصلون · الاشتراكاتُ السارية) والتقاريرُ (أفضلُ الكباتن ·
  النشطون · المباع) وتوزيعُ المستويات وجمهورُ الحملات.
- **لا مالَ حقيقيّ**: كلُّ بابٍ يُدخل مالاً حقيقيّاً أو يُخرجه يردّ `test_account_no_real_money`؛ والمكافآتُ التي يدفعها
  TAXO (الإحالة · الاسترداد · حافزُ المشوار · عروضُ الاشتراك) تُتخطّى صامتة؛ **وبابُ «تصحيح التجربة» وحدَه يعطي رصيداً**.
- **سكربتُ الإنشاء**: يُنشئ الحسابين من أبوابهما، **ولا يطبع كلمةَ مرور**، ويكتبها في ملفٍّ بإذن 600 لا يُكتب فوقه،
  **وإعادتُه لا تغيّر شيئاً**.

**والوسمُ يُكتب في القاعدة مباشرةً** — وهو بابُه الوحيد مع سكربت الإنشاء: لا حقلَ له في أيِّ مخطَّط طلب.
"""

from __future__ import annotations

import asyncio
import os
import stat
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.exceptions import NoRealMoneyOnTestAccount, NotFound
from app.core.redis_client import get_redis_client
from app.models.booking import RideBooking
from app.models.cancellation import RideCancellationCharge
from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CampaignAudience,
    CancellationChargeStatus,
    CountryCode,
    DriverStatus,
    FeatureKey,
    Gender,
    PaymentMethod,
    ProviderOrderStatus,
    UnpaidCancellationOutcome,
    VehicleCategory,
    WalletTransactionType,
)
from app.models.provider_order import ProviderOrder
from app.models.notification import NotificationCampaign
from app.models.cashback import CashbackStreak
from app.models.ride import Ride
from app.models.rider_subscription import RiderSubscription
from app.models.service_setting import ServiceSetting
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.subscription_offer import AUDIENCE_ALL, DISCOUNT_MONEY_PERCENT, SubscriptionOffer
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import WalletTransaction
from app.services import (
    bookings,
    card_payments,
    cashback,
    commute,
    dispatch,
    missions,
    offers,
    referrals as referrals_service,
    rides as rides_service,
    test_accounts,
)
from app.services.campaigns import _audience_filters
from app.services.stats import country_today
from scripts import provision_test_accounts
from tests.helpers import (
    DRIVER,
    DROPOFF,
    FAR_PICKUP,
    NEAR_PICKUP,
    OTHER_RIDER,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    enable_features,
    ensure_plan,
    pay_ride,
    register,
    request_ride,
    rider_session,
    set_commission,
    topup_wallet,
    wait_for_offer,
    wait_for_status,
    wallet_of,
)

# **أسماءٌ بعينها لا وحدةٌ كاملة** — استيرادُ الوحدة كلِّها يُدخل اختباراتِها هنا فيجمعها pytest مرّتين. والدَّينُ والرسمُ
# يُصنعان من أبوابهما هناك (رحلةٌ تُلغى · رحلةُ كاشٍ بعمولة) لا يُحقنان صفّاً
from tests.test_cancellation_collection import _charge, _entries, _owe, _policy
from tests.test_driver_debt_concurrency import _driver_with_debt, _outstanding

CODE = "test_account_no_real_money"


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    """**صفُّ الإعدادات كما تبذره الترحيلات** — والاختباراتُ تفرّغ الجداولَ قبل كلٍّ منها."""
    async with session_factory() as session:
        session.add_all(
            [
                ServiceSetting(
                    country_code="JO",
                    cashback_amount=Decimal("2.000"),
                    guarantee_fee=Decimal("1.000"),
                    commute_discount_percent=Decimal("10.00"),
                    commute_captain_incentive=Decimal("1.500"),
                ),
                ServiceSetting(country_code="LY"),
            ]
        )
        await session.commit()


async def _mark_test(session_factory, user_id: str | uuid.UUID) -> None:
    """**الوسمُ في القاعدة** — بابُه الوحيد مع سكربت الإنشاء (لا مخطَّطَ طلبٍ يحمله)."""
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == uuid.UUID(str(user_id))).values(is_test=True))
        await session.commit()


async def _unmark(session_factory, user_id: str | uuid.UUID) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == uuid.UUID(str(user_id))).values(is_test=False))
        await session.commit()


def _refused(response, status: int = 403) -> None:
    assert response.status_code == status, response.text
    assert response.json()["code"] == CODE, response.text


async def _ledger_count(session_factory, tx_type: WalletTransactionType) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(WalletTransaction).where(WalletTransaction.type == tx_type)
            )
        )


# ------------------------------------------------------------------------------- العزل


async def test_a_real_ride_skips_a_nearer_test_captain(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**أوّلُ عرضٍ للأقرب** — فلو لم يُعزل كبتنُ التجربة القريبُ لكان العرضُ الأوّلُ له."""
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, tester, NEAR_PICKUP)
    await bring_online(client, real, FAR_PICKUP)

    rider = await rider_session(client)
    ride = await request_ride(client, rider["headers"])

    first = await wait_for_offer(ride["id"])
    assert first == real["driver_id"]
    assert await get_redis_client().get(dispatch.driver_offer_key(tester["driver_id"])) is None


async def test_a_test_riders_ride_reaches_only_the_test_captain(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**والاتجاهُ الآخر**: الحقيقيُّ أقربُ إلى راكب التجربة، والعرضُ لكبتن التجربة البعيد."""
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, real, NEAR_PICKUP)
    await bring_online(client, tester, FAR_PICKUP)

    rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, rider["user"]["id"])
    ride = await request_ride(client, rider["headers"])

    first = await wait_for_offer(ride["id"])
    assert first == tester["driver_id"]
    assert await get_redis_client().get(dispatch.driver_offer_key(real["driver_id"])) is None


async def test_a_test_ride_is_never_offered_to_nor_taken_by_a_real_captain(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**لا كبتنَ تجربةٍ متصل** ⇒ الطلبُ ينتهي بلا كبتن ولا يُعرض على الحقيقيّ الواقف بجانبه.

    **والبابُ المحجوز يُسأل أيضاً** (`take_reserved`، طريقُ الحجز المضمون والمشوار): لا يأخذه الحقيقيُّ بلا عرض.
    """
    real = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, real, NEAR_PICKUP)
    rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, rider["user"]["id"])

    # **من عُرض عليه في أيِّ لحظة** — مفتاحُ العرض عمرُه ثانيتان في الاختبار، فقراءةٌ واحدةٌ في الآخر لا تشهد بشيء
    seen: set[uuid.UUID] = set()

    async def _watch(ride_id: uuid.UUID) -> None:
        redis = get_redis_client()
        while True:
            offered = await dispatch.current_offer(redis, ride_id)
            if offered is not None:
                seen.add(offered)
            seen.update(await dispatch.broadcast_members(redis, ride_id))
            await asyncio.sleep(0.05)

    ride = await request_ride(client, rider["headers"])
    watcher = asyncio.create_task(_watch(uuid.UUID(ride["id"])))
    try:
        async with session_factory() as session:
            driver = await session.get(Driver, real["driver_id"])
            with pytest.raises(NotFound):
                await rides_service.take_reserved(session, uuid.UUID(ride["id"]), driver)
            await session.rollback()

        await wait_for_status(client, rider["headers"], ride["id"], "no_driver_found")
    finally:
        watcher.cancel()
    assert seen == set()


async def test_the_maps_show_each_world_only_its_own_captains(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """خريطةُ الراكب وخريطةُ الكبتن — **سيارتان متاحتان قربَ النقطة، وكلُّ عالمٍ يرى واحدةً**."""
    await enable_features(session_factory, FeatureKey.DRIVER_MAP_NEARBY_ENABLED.value)
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, real, NEAR_PICKUP)
    await bring_online(client, tester, NEAR_PICKUP)

    real_rider = await rider_session(client)
    test_rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, test_rider["user"]["id"])

    params = {"lat": PICKUP["lat"], "lng": PICKUP["lng"]}
    for path, headers in (
        ("/drivers/nearby", real_rider["headers"]),
        ("/drivers/nearby", test_rider["headers"]),
        ("/drivers/me/nearby", real["headers"]),
        ("/drivers/me/nearby", tester["headers"]),
    ):
        seen = await client.get(path, params=params, headers=headers)
        assert seen.status_code == 200, seen.text
        assert len(seen.json()) == 1, (path, seen.json())

    # **والضابط**: بلا الوسم يرى الراكبُ السيارتين — فالواحدةُ فوق أثرُ العزل لا قلّةُ الكباتن
    await _unmark(session_factory, tester["user_id"])
    both = await client.get("/drivers/nearby", params=params, headers=real_rider["headers"])
    assert len(both.json()) == 2


async def test_the_commute_market_keeps_the_worlds_apart_and_pays_no_incentive(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**المشوارُ الثابت سوقٌ خارج التوزيع**: مشوارُ راكبِ التجربة لا يراه كبتنٌ حقيقيٌّ ولا يعتمده، ويراه كبتنُ التجربة.

    **وحافزُ الكبتن من TAXO لا يصل كبتنَ التجربة** — والأجرةُ نفسُها (مالُ الراكب المحفوظ) تمضي.
    """
    await enable_features(
        session_factory,
        FeatureKey.RIDER_SUBSCRIPTION_ENABLED.value,
        FeatureKey.SCHEDULED_RIDES_ENABLED.value,
    )
    async with session_factory() as session:
        tomorrow = await country_today(session, CountryCode.JO) + timedelta(days=1)
    plan = {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "weekdays": 127,
        "go_time": "07:30:00",
        "return_time": None,
        "starts_on": tomorrow.isoformat(),
    }

    real_rider = await rider_session(client)
    await topup_wallet(client, admin_headers, real_rider["user"]["id"], "600.000")
    test_rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, test_rider["user"]["id"])
    # **رصيدُ راكب التجربة من «تصحيح التجربة» وحدَه** — الشحنُ مغلقٌ عليه
    granted = await client.post(
        f"/admin/wallets/{test_rider['user']['id']}/adjustments",
        json={"amount": "600.000", "reason": "رصيدُ مشوارِ تجربة", "wallet": "rider"},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text

    subs: dict[str, dict] = {}
    for key, rider in (("real", real_rider), ("test", test_rider)):
        bought = await client.post("/me/commutes", json=plan, headers=rider["headers"])
        assert bought.status_code == 201, bought.text
        subs[key] = bought.json()

    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, real, NEAR_PICKUP)
    await bring_online(client, tester, FAR_PICKUP)

    # ── كلُّ كبتنٍ يرى مشوارَ عالمه وحدَه، ولا يعتمد مشوارَ الآخر بمعرّفٍ مكتوبٍ بيد ──
    for key, driver, other in (("real", real, "test"), ("test", tester, "real")):
        offered = await client.get("/drivers/me/commute-offers", headers=driver["headers"])
        assert [row["id"] for row in offered.json()] == [subs[key]["id"]], key
        refused = await client.post(f"/drivers/me/commutes/{subs[other]['id']}/approve", headers=driver["headers"])
        assert refused.status_code == 404, refused.text
        approved = await client.post(f"/drivers/me/commutes/{subs[key]['id']}/approve", headers=driver["headers"])
        assert approved.status_code == 200, approved.text

    # ── يومُ المشوار للاثنين: الرحلةُ تُسنَد لمعتمدها وتُنهى ──
    async with session_factory() as session:
        for sub in subs.values():
            row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
            await commute.generate_for(session, row, date.fromisoformat(sub["starts_on"]))
            go = await session.scalar(
                select(RideBooking).where(RideBooking.commute_id == row.id).order_by(RideBooking.scheduled_at)
            )
            go.scheduled_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.commit()
    async with session_factory() as session:
        await bookings.run_due(session, get_redis_client())
    for key, driver in (("real", real), ("test", tester)):
        async with session_factory() as session:
            ride_id = await session.scalar(
                select(RideBooking.ride_id).where(
                    RideBooking.commute_id == uuid.UUID(subs[key]["id"]), RideBooking.ride_id.is_not(None)
                )
            )
        assert ride_id is not None, key
        for step in ("arrive", "start", "complete"):
            done = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
            assert done.status_code == 200, done.text

    # **حافزٌ واحدٌ لا اثنان — للكبتن الحقيقيّ وحدَه** (والضابطُ في الصفِّ نفسِه: لولا التخطّي لكانا اثنين)
    async with session_factory() as session:
        incentives = list(
            await session.scalars(
                select(WalletTransaction.owner_id).where(
                    WalletTransaction.type == WalletTransactionType.COMMUTE_INCENTIVE
                )
            )
        )
    assert incentives == [uuid.UUID(real["user_id"])]


async def test_guaranteed_bookings_and_intercity_trips_stay_in_their_world(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الحجزُ المضمون وبين المدن**: سوقان يلتقي فيهما الطرفان خارج التوزيع — والعزلُ في القائمة وفي الباب معاً."""
    await enable_features(
        session_factory,
        FeatureKey.GUARANTEED_BOOKING_ENABLED.value,
        FeatureKey.SCHEDULED_RIDES_ENABLED.value,
        FeatureKey.INTERCITY_ENABLED.value,
    )
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])

    # ── حجزٌ مضمونٌ لراكبٍ حقيقيّ: يراه الحقيقيُّ ولا يراه كبتنُ التجربة ولا يقبله ──
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    booked = await client.post(
        "/me/bookings",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "scheduled_at": (datetime.now(UTC) + timedelta(hours=3)).isoformat(),
            "guaranteed": True,
        },
        headers=rider["headers"],
    )
    assert booked.status_code == 201, booked.text
    booking_id = booked.json()["id"]
    real_offers = await client.get("/drivers/me/guarantee-offers", headers=real["headers"])
    assert [row["id"] for row in real_offers.json()] == [booking_id]
    assert (await client.get("/drivers/me/guarantee-offers", headers=tester["headers"])).json() == []
    taken = await client.post(f"/drivers/me/guarantees/{booking_id}/accept", headers=tester["headers"])
    assert taken.status_code == 404, taken.text

    # ── رحلةُ كبتن التجربة بين المدن: لا يراها راكبٌ حقيقيٌّ ولا يحجز فيها ──
    route = await client.post(
        "/admin/intercity/routes",
        json={
            "country_code": "JO",
            "from_city": "عمّان",
            "to_city": "إربد",
            "from_lat": 31.95,
            "from_lng": 35.91,
            "from_point": "مجمّع الشمال",
            "to_lat": 32.55,
            "to_lng": 35.85,
            "to_point": "مجمّع عمّان الجديد",
            "price_car": "22.000",
            "price_seat": "6.000",
        },
        headers=admin_headers,
    )
    assert route.status_code == 201, route.text
    async with session_factory() as session:
        vehicle_id = await session.scalar(select(Vehicle.id).where(Vehicle.driver_id == tester["driver_id"]))
    permit = await client.post(
        f"/admin/intercity/drivers/{tester['driver_id']}/permit",
        json={
            "vehicle_id": str(vehicle_id),
            "seats": 4,
            "insurance_expires_on": (date.today() + timedelta(days=200)).isoformat(),
        },
        headers=admin_headers,
    )
    assert permit.status_code == 201, permit.text
    trip = await client.post(
        "/drivers/me/intercity/trips",
        json={
            "route_id": route.json()["id"],
            "departs_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "seats": 4,
            "min_seats": 1,
        },
        headers=tester["headers"],
    )
    assert trip.status_code == 201, trip.text
    trip_id = trip.json()["id"]

    assert (await client.get("/intercity/trips", headers=rider["headers"])).json() == []
    seat = await client.post(
        "/intercity/bookings", json={"trip_id": trip_id, "whole_car": True}, headers=rider["headers"]
    )
    assert seat.status_code == 409, seat.text
    test_rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, test_rider["user"]["id"])
    listed = await client.get("/intercity/trips", headers=test_rider["headers"])
    assert [row["id"] for row in listed.json()] == [trip_id]


# --------------------------------------------------------------------------- خارجَ العدّ


async def test_stats_reports_levels_and_campaigns_leave_the_test_accounts_out(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """رحلةٌ حقيقيّةٌ ورحلةُ تجربة مكتملتان، وكبتنان متصلان مشتركان — **والأرقامُ كلُّها بواحد**."""
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, real, NEAR_PICKUP)
    await bring_online(client, tester, FAR_PICKUP)

    real_rider = await rider_session(client)
    test_rider = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, test_rider["user"]["id"])

    real_ride = await completed_ride(client, real_rider["headers"], real)
    test_ride = await completed_ride(client, test_rider["headers"], tester)

    overview = await client.get(
        "/admin/stats/overview", params={"country_code": "JO"}, headers=admin_headers
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["completed_rides"] == 1
    assert sum(body["rides_by_hour"]) == 1
    assert body["revenue"] in (real_ride["final_fare"], real_ride["estimated_fare"])
    assert body["online_drivers"] == 1
    assert body["active_subscriptions"] == 1

    reports = await client.get(
        "/admin/stats/reports", params={"country_code": "JO", "period": "month"}, headers=admin_headers
    )
    assert reports.status_code == 200, reports.text
    report = reports.json()
    assert [row["driver_id"] for row in report["top_drivers"]] == [str(real["driver_id"])]
    assert report["active_drivers"] == 1
    assert report["subscriptions_sold"] == 1

    async with session_factory() as session:
        assert sum((await missions.level_counts(session, CountryCode.JO)).values()) == 1
        campaign = NotificationCampaign(audience=CampaignAudience.ALL_RIDERS, country_code=CountryCode.JO)
        audience = set(await session.scalars(select(User.id).where(*_audience_filters(campaign))))
        assert audience == {uuid.UUID(real_rider["user"]["id"])}

        # **ودفعُ رحلة التجربة ببطاقةٍ يُردّ عند بابه** — قبل أن يُفتح طلبٌ عند المزوّد
        ride_row = await session.get(Ride, uuid.UUID(test_ride["id"]))
        payer = await session.get(User, uuid.UUID(test_rider["user"]["id"]))
        with pytest.raises(NoRealMoneyOnTestAccount):
            await card_payments.start_ride_payment(
                session, ride=ride_row, rider=payer, amount=Decimal("1.000"), idempotency_key="card-test-1"
            )
        await session.rollback()

    # **والضابط**: بلا الوسم تعود الأرقامُ اثنين — فالواحدُ فوق أثرُ الاستثناء لا قلّةُ الرحلات
    await _unmark(session_factory, test_rider["user"]["id"])
    await _unmark(session_factory, tester["user_id"])
    again = (
        await client.get("/admin/stats/overview", params={"country_code": "JO"}, headers=admin_headers)
    ).json()
    assert again["completed_rides"] == 2
    assert again["online_drivers"] == 2


# ------------------------------------------------------------------------- لا مالَ حقيقيّ


async def test_every_real_money_door_refuses_a_test_account_by_name(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FeatureKey.PROMO_CODES_ENABLED.value)
    test_rider = await rider_session(client, OTHER_RIDER)
    real_rider = await rider_session(client)
    await _mark_test(session_factory, test_rider["user"]["id"])
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    plan_id = await ensure_plan(session_factory)
    headers = test_rider["headers"]

    # الشحنُ بقنواته الحقيقيّة الأربع
    _refused(await client.post("/wallet/me/topups", json={"amount": "5.000", "reference": "TX-1"}, headers=headers))
    _refused(await client.post("/wallet/me/topups/card", json={"amount": "5.000"}, headers=headers))
    _refused(await client.post("/wallet/me/topups/cliq", json={"amount": "5.000"}, headers=headers))
    _refused(
        await client.post(
            f"/admin/wallets/{test_rider['user']['id']}/topups",
            json={"method": "cash", "amount": "5.000", "reference": "إيصال 1"},
            headers=admin_headers,
        )
    )
    # التحويلُ في الاتجاهين — رصيدُ التجربة لا يصير مالاً حقيقيّاً بضغطة
    _refused(
        await client.post(
            "/wallet/me/transfers",
            json={"recipient_phone": RIDER["phone"], "amount": "1.000", "idempotency_key": "transfer-key-01"},
            headers=headers,
        )
    )
    _refused(
        await client.post(
            "/wallet/me/transfers",
            json={"recipient_phone": OTHER_RIDER["phone"], "amount": "1.000", "idempotency_key": "transfer-key-02"},
            headers=real_rider["headers"],
        )
    )
    # الكوبونُ والمشاركة — خصمان يدفعهما TAXO
    _refused(
        await client.post(
            "/rides/promo/validate", json={"code": "WELCOME", "country_code": "JO", "fare": "8.000"}, headers=headers
        )
    )
    _refused(
        await client.post(
            "/rides",
            json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "share": True},
            headers=headers,
        )
    )
    # الكبتن: السحبُ والسلفةُ والاشتراكُ بقناةٍ حقيقيّة
    _refused(
        await client.post(
            "/wallet/me/withdrawals", json={"amount": "10.000", "method": "bank"}, headers=tester["headers"]
        )
    )
    _refused(await client.post("/drivers/me/advances", json={"amount": "3.000"}, headers=tester["headers"]))
    _refused(await client.post("/subscriptions/card", json={"plan_id": str(plan_id)}, headers=tester["headers"]))
    _refused(await client.post("/subscriptions/cliq", json={"plan_id": str(plan_id)}, headers=tester["headers"]))
    # **وسدادُ الدَّين بكليك** — مالٌ حقيقيٌّ يدخل حسابَ TAXO، والقاعدةُ في الاتجاهين. **ويُردّ باسمه لا بـ«لا مستحقّات عليك»**:
    # الحارسُ قبل سؤال الدَّين، وكبتنُ التجربة هنا بلا دَين
    _refused(await client.post("/drivers/me/debt/cliq", json={"amount": "1.000"}, headers=tester["headers"]))
    # **واشتراكٌ تسجّله اللوحةُ بمالٍ مقبوض** — بمبلغٍ صريح، وبالفارغ الذي يُقرأ سعرَ الخطة
    for amount in ({"amount_paid": "5.000"}, {}):
        _refused(
            await client.post(
                "/admin/subscriptions",
                json={"driver_id": str(tester["driver_id"]), "plan_id": str(plan_id), "method": "cash"} | amount,
                headers=admin_headers,
            )
        )

    # **ولم يُكتب صفٌّ واحد** — الردُّ عند الباب قبل أيِّ أثر: لا قيدَ في الدفتر ولا طلبَ عند مزوّدٍ ولا مطالبةَ تنتظر مشرفاً
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WalletTransaction)) == 0
        assert await session.scalar(select(func.count()).select_from(ProviderOrder)) == 0


async def test_a_withdrawal_written_before_the_mark_is_not_paid_out(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الحارسُ الثاني**: طلبُ سحبٍ كُتب قبل الوسم لا يُعلَّم مدفوعاً بعده — فلا يخرج مالٌ حقيقيّ."""
    driver = await approved_driver(client, session_factory, DRIVER)
    granted = await client.post(
        f"/admin/wallets/{driver['user_id']}/adjustments",
        json={"amount": "50.000", "reason": "أرباحٌ سابقة", "wallet": "driver"},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    requested = await client.post(
        "/wallet/me/withdrawals", json={"amount": "10.000", "method": "bank"}, headers=driver["headers"]
    )
    assert requested.status_code == 201, requested.text
    request_id = requested.json()["id"]
    approved = await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text

    await _mark_test(session_factory, driver["user_id"])
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid", json={"reference": "BANK-REF-1"}, headers=admin_headers
    )
    _refused(paid)
    assert await _ledger_count(session_factory, WalletTransactionType.WITHDRAWAL) == 0


async def test_a_debt_claim_opened_before_the_mark_is_not_applied_after_it(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الحارسُ الثاني لسداد الدَّين بكليك** — مطالبةٌ فُتحت قبل الوسم لا يُقيَّد بها مالٌ حقيقيٌّ بعده، والدَّينُ على حاله."""
    driver = await _driver_with_debt(client, session_factory)
    due = await _outstanding(session_factory, driver["driver_id"])
    assert due > 0
    claim = await client.post("/drivers/me/debt/cliq", json={"amount": str(due)}, headers=driver["headers"])
    assert claim.status_code == 201, claim.text
    assert claim.json()["driver_is_test"] is False

    await _mark_test(session_factory, driver["user_id"])
    # **والمطالبةُ المعلّقةُ تُرى في طابور اللوحة موسومةً** — فالمشرفُ يعرف لمَ يردّها التأكيدُ قبل أن يضغط
    pending = (await client.get("/admin/drivers/debts/claims", headers=admin_headers)).json()
    assert [(row["id"], row["driver_is_test"]) for row in pending] == [(claim.json()["id"], True)]
    confirmed = await client.post(
        f"/admin/drivers/debts/claims/{claim.json()['id']}/confirm",
        json={"credited": str(due)},
        headers=admin_headers,
    )
    _refused(confirmed)
    assert await _outstanding(session_factory, driver["driver_id"]) == due
    async with session_factory() as session:
        order = await session.get(ProviderOrder, uuid.UUID(claim.json()["id"]))
        assert order.status is ProviderOrderStatus.CREATED
        # **والضابط**: الدَّينُ نفسُه قائمٌ لم يُمسّ — فالردُّ ليس لأن لا شيءَ يُسدَّد
        rows = list(await session.scalars(select(DriverDebt).where(DriverDebt.driver_id == driver["driver_id"])))
        assert rows and all(row.collected == 0 for row in rows)


async def test_a_manual_subscription_for_the_test_captain_is_zero_or_nothing(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**بابُ اللوحة يسجّل اشتراكاً بمالٍ مقبوض** — لكبتن التجربة بصفرٍ وحدَه (طريقُ سكربت الإنشاء)، **وللحقيقيّ كما كان**."""
    plan_id = await ensure_plan(session_factory)
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002", subscribed=False)
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001", subscribed=False)
    await _mark_test(session_factory, tester["user_id"])

    def _body(driver: dict, amount: str) -> dict:
        return {"driver_id": str(driver["driver_id"]), "plan_id": str(plan_id), "method": "cash", "amount_paid": amount}

    _refused(await client.post("/admin/subscriptions", json=_body(tester, "5.000"), headers=admin_headers))
    zero = await client.post("/admin/subscriptions", json=_body(tester, "0.000"), headers=admin_headers)
    assert zero.status_code == 201, zero.text
    assert Decimal(zero.json()["amount_paid"]) == 0
    paid = await client.post("/admin/subscriptions", json=_body(real, "5.000"), headers=admin_headers)
    assert paid.status_code == 201, paid.text


async def test_the_company_never_bears_a_charge_a_test_account_touches(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**«تتحمّلها الشركة» دائنٌ بلا مدين — مالٌ يخلقه TAXO** (SPEC §٦٥-ج: «ما يُعطي مالاً حقيقيّاً لا يصلهما»).

    رسمٌ يمسّه حسابُ تجربةٍ من أيِّ طرفٍ يبقى معلّقاً لإعفاء المشرف — **والضابط**: بلا وسمٍ تتحمّله الشركةُ كما كانت.
    """
    from app.tasks.cancellation import _apply_unpaid_outcome

    setup = await _owe(client, admin_headers, session_factory)
    await _policy(session_factory, unpaid_after_days=1, unpaid_outcome=UnpaidCancellationOutcome.COMPANY_BEARS)
    # الصفُّ يُقدَّم في الزمن بدل الانتظار يوماً — الشرطُ عمرُه لا حالتُه (`test_cancellation_collection` نفسُه)
    async with session_factory() as session:
        row = await session.get(RideCancellationCharge, setup["charge"].id)
        row.created_at = row.created_at.replace(year=row.created_at.year - 1)
        await session.commit()
    ride_id = str(setup["charge"].ride_id)
    injured_id = setup["injured"]["user_id"]

    async def _marks() -> tuple[bool, bool]:
        rows = (await client.get("/admin/cancellation-charges", headers=admin_headers)).json()
        assert [row["ride_id"] for row in rows] == [ride_id]
        return rows[0]["payer_is_test"], rows[0]["beneficiary_is_test"]

    assert await _marks() == (False, False)
    for marked, expected in ((setup["rider"]["user"]["id"], (True, False)), (injured_id, (False, True))):
        await _mark_test(session_factory, marked)
        assert await _apply_unpaid_outcome() == 0
        assert (await _charge(session_factory, ride_id)).status is CancellationChargeStatus.PENDING
        assert await _entries(session_factory, injured_id) == {}
        # **ويبقى معلّقاً في اللوحة موسوماً بطرفه** — فمشرفٌ يُعفيه يعرف أنه تجربة (شارةٌ بجانب الاسم الصحيح لا كليهما)
        assert await _marks() == expected
        await _unmark(session_factory, marked)

    assert await _apply_unpaid_outcome() == 1
    row = await _charge(session_factory, ride_id)
    assert row.status is CancellationChargeStatus.SETTLED
    assert (await _entries(session_factory, injured_id))["cancellation_compensation"] == row.amount


async def test_the_test_adjustment_settles_a_test_charge_and_never_crosses_worlds(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**«تصحيحُ تجربة» يقوم مقامَ الشحن** — أبوابُ الشحن الثلاثة التي تسدّد الرسمَ المعلّق مغلقةٌ على حساب التجربة.

    وثلاثُ مراحلَ على رسمٍ واحد: **تصحيحٌ لحسابٍ حقيقيٍّ لا يسدّد** (كما كان: تصويبُ دفترٍ لا شحن)؛ **ورسمٌ بين عالمين لا يُحصَّل**
    (رصيدُ التجربة لا يصير مالاً يسحبه كبتنٌ حقيقيّ)؛ **ثمّ رسمٌ في عالم التجربة يُسدَّد بالتصحيح**.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider_id = setup["rider"]["user"]["id"]
    injured_id = setup["injured"]["user_id"]
    ride_id = str(setup["charge"].ride_id)

    async def _adjust(amount: str) -> None:
        done = await client.post(
            f"/admin/wallets/{rider_id}/adjustments",
            json={"amount": amount, "reason": "رصيدُ جولة", "wallet": "rider"},
            headers=admin_headers,
        )
        assert done.status_code == 200, done.text

    # ١) حسابان حقيقيّان — التصحيحُ لا يسدّد
    await _adjust("10.000")
    assert (await _charge(session_factory, ride_id)).status is CancellationChargeStatus.PENDING

    # ٢) الراكبُ تجربةٌ والكبتنُ حقيقيّ — رسمٌ بين عالمين لا يُحصَّل، ولا يصل الكبتنَ الحقيقيَّ شيء
    await _mark_test(session_factory, rider_id)
    await _adjust("1.000")
    assert (await _charge(session_factory, ride_id)).status is CancellationChargeStatus.PENDING
    assert await _entries(session_factory, injured_id) == {}

    # ٣) الطرفان تجربة — يُسدَّد كما يسدّده الشحن، بقيدَيه
    await _mark_test(session_factory, injured_id)
    await _adjust("1.000")
    row = await _charge(session_factory, ride_id)
    assert row.status is CancellationChargeStatus.SETTLED
    assert (await _entries(session_factory, injured_id))["cancellation_compensation"] == row.amount
    assert (await _entries(session_factory, rider_id))["cancellation_fee"] == -row.amount


async def test_the_panel_rows_carry_the_test_mark_beside_each_party(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**«وشارةُ «تجربة» عليهما في قوائم اللوحة»** (SPEC §٦٥-ج) — الرحلاتُ والمدفوعاتُ والمستحقّاتُ تحمل الوسمَ لكلِّ طرف.

    رحلتا كاشٍ بعمولة، **واحدةٌ في كلِّ عالم** — فالوسمُ يُقرأ صادقاً في الاتجاهين، لا ثابتاً يُكتب `true` أو `false`.
    """
    await set_commission(session_factory, "10")
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001")
    await _mark_test(session_factory, tester["user_id"])
    test_rider = await rider_session(client, OTHER_RIDER)
    real_rider = await rider_session(client)
    await _mark_test(session_factory, test_rider["user"]["id"])

    marked: dict[str, bool] = {}
    for rider, driver, key in ((test_rider, tester, "pay-key-tst1"), (real_rider, real, "pay-key-real")):
        await bring_online(client, driver)
        ride = await completed_ride(client, rider["headers"], driver)
        payment = (await pay_ride(client, rider["headers"], ride["id"], "cash", key=key)).json()["payments"][0]
        confirmed = await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])
        assert confirmed.status_code == 200, confirmed.text
        await client.post("/drivers/me/offline", headers=driver["headers"])
        is_test = rider is test_rider
        marked[ride["id"]] = is_test

    rides = (await client.get("/admin/rides", headers=admin_headers)).json()
    assert {row["id"]: (row["rider"]["is_test"], row["driver"]["is_test"]) for row in rides} == {
        ride_id: (flag, flag) for ride_id, flag in marked.items()
    }
    payments = (await client.get("/admin/payments", headers=admin_headers)).json()
    assert {row["ride_id"]: (row["rider"]["is_test"], row["driver"]["is_test"]) for row in payments} == {
        ride_id: (flag, flag) for ride_id, flag in marked.items()
    }
    debts = (await client.get("/admin/drivers/debts", headers=admin_headers)).json()
    assert {row["driver_id"]: row["driver_is_test"] for row in debts} == {
        str(tester["driver_id"]): True,
        str(real["driver_id"]): False,
    }


async def test_the_test_adjustment_is_the_one_door_and_it_is_marked(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**«تصحيحُ تجربة» يُضاف إلى سبب المشرف** — والحسابُ الحقيقيُّ يُكتب سببُه حرفاً.

    **ورصيدُه يُنفق في التطبيق كأيِّ رصيد** — اشتراكٌ من المحفظة بسعر الخطة كاملاً (لا عرضَ لكبتن التجربة).
    """
    await enable_features(session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value)
    plan_id = await ensure_plan(session_factory)
    async with session_factory() as session:
        session.add(
            SubscriptionOffer(
                country_code=CountryCode.JO,
                name="عرضُ الشهر",
                discount_type=DISCOUNT_MONEY_PERCENT,
                discount_value=Decimal("10"),
                audience=AUDIENCE_ALL,
                max_uses_per_driver=1,
                is_active=True,
            )
        )
        await session.commit()

    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002", subscribed=False)
    real = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-1001", subscribed=False)
    await _mark_test(session_factory, tester["user_id"])

    for driver, reason in ((tester, "رصيدُ جولة"), (real, "تسويةُ فرق")):
        done = await client.post(
            f"/admin/wallets/{driver['user_id']}/adjustments",
            json={"amount": "40.000", "reason": reason, "wallet": "driver"},
            headers=admin_headers,
        )
        assert done.status_code == 200, done.text
    async with session_factory() as session:
        references = dict(
            (await session.execute(select(WalletTransaction.owner_id, WalletTransaction.reference))).all()
        )
    assert references[uuid.UUID(tester["user_id"])] == f"{test_accounts.TEST_ADJUSTMENT_MARK} — رصيدُ جولة"
    assert references[uuid.UUID(real["user_id"])] == "تسويةُ فرق"
    assert Decimal((await wallet_of(client, tester["headers"]))["balance"]) == Decimal("40.000")

    async with session_factory() as session:
        plan = await session.get(SubscriptionPlan, plan_id)
        for driver, expected in ((tester, None), (real, Decimal("3.000"))):
            row = await session.get(Driver, driver["driver_id"])
            resolved = await offers.resolve(session, driver=row, plan=plan)
            assert (resolved.amount if resolved is not None else None) == expected

    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": uuid.uuid4().hex},
        headers=tester["headers"],
    )
    assert bought.status_code in (200, 201), bought.text
    async with session_factory() as session:
        row = await session.scalar(
            select(DriverSubscription).where(DriverSubscription.driver_id == tester["driver_id"])
        )
        assert row.amount_paid == Decimal("30.000") and row.offer_id is None


async def test_rewards_taxo_pays_are_skipped_silently(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الإحالةُ والاسترداد** — لا تُدفع حين يمسّها حسابُ تجربة، **وتُدفع بلا الوسم** (الضابط)."""
    await enable_features(
        session_factory,
        "driver_referrals_enabled",
        FeatureKey.WEEKLY_CASHBACK_ENABLED.value,
    )
    policy = await client.put(
        "/admin/referrals/settings?country_code=JO&referral_type=driver",
        json={"reward_amount": "4.000", "required_rides": 0},
        headers=admin_headers,
    )
    assert policy.status_code == 200, policy.text

    referrer = await register(client, DRIVER)
    code = (await client.get("/me/referrals", headers=auth(referrer))).json()["code"]
    referred = await approved_driver(
        client, session_factory, SECOND_DRIVER | {"referral_code": code}, plate_number="AMM-9002"
    )
    async with session_factory() as session:
        user = await session.scalar(select(User).join(Driver, Driver.user_id == User.id).where(Driver.id == referred["driver_id"]))
        user.gender = Gender.FEMALE
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()

    await _mark_test(session_factory, referred["user_id"])
    async with session_factory() as session:
        assert await referrals_service.pay_due(session) == []
    assert await _ledger_count(session_factory, WalletTransactionType.REFERRAL_BONUS) == 0

    # **ولا تظهر «تنتظر» في ملخّص اللوحة** — إحالةٌ لن تُدفع أبداً لا تُعدّ معلّقة
    summary = await client.get("/admin/referrals/summary", params={"country_code": "JO"}, headers=admin_headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["pending_count"] == 0

    await _unmark(session_factory, referred["user_id"])
    async with session_factory() as session:
        assert len(await referrals_service.pay_due(session)) == 1

    # ── الاستردادُ الأسبوعي: لا سلسلةَ ولا نارَ لراكب التجربة ──
    test_rider = await rider_session(client, OTHER_RIDER)
    real_rider = await rider_session(client)
    await _mark_test(session_factory, test_rider["user"]["id"])
    async with session_factory() as session:
        row = await cashback.settings_for(session, CountryCode.JO)
        assert row is not None
        # **سبتٌ معلوم** لا «اليوم»: الجمعةُ لا تبدأ سلسلةً أصلاً، فاختبارٌ يُشغَّل يومَ جمعةٍ كان سيسقط لسببٍ ليس موضوعَه
        saturday = date(2026, 10, 3)
        for rider in (test_rider, real_rider):
            user = await session.get(User, uuid.UUID(rider["user"]["id"]))
            await cashback.record_day(session, rider=user, day=saturday, row=row)
        await session.commit()
        owners = set(await session.scalars(select(CashbackStreak.rider_id)))
    assert owners == {uuid.UUID(real_rider["user"]["id"])}
    assert (await client.get("/me/cashback", headers=test_rider["headers"])).json()["enabled"] is False
    assert (await client.get("/me/cashback", headers=real_rider["headers"])).json()["enabled"] is True


# ------------------------------------------------------------------------- سكربتُ الإنشاء


@pytest.fixture
def _no_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    """**لا رسالةَ تخرج إلى الرقمين بحال** — أيُّ نداءٍ لمزوّد الرسائل يُسقط الاختبار."""
    from app.services import sms, whatsapp

    async def _forbidden(*_args, **_kwargs):
        raise AssertionError("السكربتُ نادى مزوّدَ رسائل — والرقمان لا يُراسَلان")

    monkeypatch.setattr(sms, "get_sms_provider", _forbidden)
    monkeypatch.setattr(whatsapp, "get_whatsapp_provider", _forbidden)
    monkeypatch.setattr(whatsapp, "get_provider_or_none", _forbidden)


@pytest.fixture
def _secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """**مجلّدُ الأسرار في الاختبار** — `tmp_path` تحت `/tmp` الذي يردّه السكربتُ (يُمحى بخروج الحاوية)، **فيُرفع `/tmp` من
    قائمة المردود هنا وحدَه**، ويقف `tmp_path` مكانَ `/home/taxo/secrets` المربوط. **والردُّ نفسُه يقيسه
    `test_the_script_refuses_a_secrets_path_in_the_repo_on_tmp_or_unmounted` بقائمته الحقيقيّة** — وبغير هذا كانت اختباراتُ
    الردِّ الأخرى (ملفٌّ قائم · حسابٌ غيرُ موسوم) ستمرّ خضراءَ بالسبب الخطأ."""
    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    return tmp_path


async def test_the_script_provisions_once_prints_no_password_and_writes_a_600_file(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    _secrets_dir: Path,
    capsys: pytest.CaptureFixture[str],
    _no_messages: None,
) -> None:
    await ensure_plan(session_factory)
    tmp_path = _secrets_dir
    secrets_file = tmp_path / "test-accounts.env"

    first = await provision_test_accounts.provision(secrets_file=secrets_file, session_factory=session_factory)
    printed = capsys.readouterr().out
    assert first.created is True

    # ── الملف: إذنُ 600 وكلمتان تعملان ──
    assert stat.S_IMODE(os.stat(secrets_file).st_mode) == 0o600
    values = dict(
        line.split("=", 1) for line in secrets_file.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#")
    )
    passwords = (values["TAXO_TEST_RIDER_PASSWORD"], values["TAXO_TEST_CAPTAIN_PASSWORD"])
    assert all(len(password) >= 24 for password in passwords)
    for password in passwords:
        assert password not in printed
    assert provision_test_accounts.RIDER_PHONE in printed and provision_test_accounts.CAPTAIN_PHONE in printed
    assert provision_test_accounts.WRITTEN in printed
    for phone, password in (
        (values["TAXO_TEST_RIDER_PHONE"], passwords[0]),
        (values["TAXO_TEST_CAPTAIN_PHONE"], passwords[1]),
    ):
        login = await client.post("/auth/login", json={"phone": phone, "password": password})
        assert login.status_code == 200, login.text
        assert login.json()["user"]["is_test"] is True

    # ── الحسابان: موسومان، مُثبتا الرقم، والكبتنُ معتمدٌ مشتركٌ بصفرٍ مكتوبٍ سببُه ──
    async with session_factory() as session:
        users = list(await session.scalars(select(User).where(User.is_test.is_(True))))
        assert {user.phone for user in users} == {
            provision_test_accounts.RIDER_PHONE,
            provision_test_accounts.CAPTAIN_PHONE,
        }
        assert all(user.phone_verified_at is not None for user in users)
        driver = await session.scalar(select(Driver).join(User, User.id == Driver.user_id).where(User.is_test.is_(True)))
        assert driver.status is DriverStatus.APPROVED
        subscription = await session.scalar(select(DriverSubscription).where(DriverSubscription.driver_id == driver.id))
        assert subscription.amount_paid == Decimal("0.000")
        assert subscription.payment_method is PaymentMethod.CASH
        assert subscription.reference == provision_test_accounts.SUBSCRIPTION_REFERENCE
        assert subscription.offer_id is None
        # **ولا مالَ في الدفتر** — لا شحنَ ولا خصم
        assert await session.scalar(select(func.count()).select_from(WalletTransaction)) == 0
        # **ويصله عرضٌ من عالمه**: مؤهَّلٌ للتوزيع بلا شرطٍ ناقص (معتمد · مشترك · مركبة) حين يتّصل
        driver.is_online = True
        await session.flush()
        assert await dispatch.eligible_driver_ids(session, [driver.id], VehicleCategory.ECONOMY, test=True) == {driver.id}
        assert await dispatch.eligible_driver_ids(session, [driver.id], VehicleCategory.ECONOMY) == set()
        await session.rollback()
        before = await session.scalar(select(func.count()).select_from(User))

    # ── إعادةُ التشغيل: «موجود» ولا شيءَ يتغيّر — لا ملفٌّ يُمسّ ولا صفٌّ يُكتب ──
    written = secrets_file.read_bytes()
    elsewhere = tmp_path / "again.env"
    second = await provision_test_accounts.provision(secrets_file=elsewhere, session_factory=session_factory)
    printed = capsys.readouterr().out
    assert second.created is False and (second.rider_id, second.captain_id) == (first.rider_id, first.captain_id)
    assert printed.count(provision_test_accounts.PRESENT) == 2
    assert not elsewhere.exists()
    assert secrets_file.read_bytes() == written
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == before


async def test_the_script_never_writes_over_an_existing_file_and_leaves_nothing_behind(
    jordan_settings: None, session_factory, _secrets_dir: Path, _no_messages: None
) -> None:
    """مسارٌ خاطئٌ يشير إلى ملفِّ أسرارٍ قائم ⇒ **يقف، ولا يُلتزم حسابٌ بكلمةٍ لا يعرفها أحد**."""
    await ensure_plan(session_factory)
    existing = _secrets_dir / "taxo.env"
    existing.write_text("WRITTEN_BEFORE=keep-me\n", encoding="utf-8")

    # **بسببه هو** لا بسببٍ يسبقه — النصُّ يُطابَق
    with pytest.raises(provision_test_accounts.ProvisionRefused, match="موجودٌ سلفاً"):
        await provision_test_accounts.provision(secrets_file=existing, session_factory=session_factory)

    assert existing.read_text(encoding="utf-8") == "WRITTEN_BEFORE=keep-me\n"
    async with session_factory() as session:
        phones = (provision_test_accounts.RIDER_PHONE, provision_test_accounts.CAPTAIN_PHONE)
        assert await session.scalar(select(func.count()).select_from(User).where(User.phone.in_(phones))) == 0


async def test_the_script_refuses_to_mark_an_account_it_did_not_create(
    client: AsyncClient, jordan_settings: None, session_factory, _secrets_dir: Path, _no_messages: None
) -> None:
    """حسابٌ غيرُ موسومٍ بأحد الرقمين ⇒ **يقف ولا يَسِمه** — الوسمُ لما أنشأه السكربتُ وحدَه."""
    await ensure_plan(session_factory)
    await register(
        client,
        {
            "phone": provision_test_accounts.RIDER_PHONE,
            "name": "حسابٌ عاديّ",
            "password": "SuperSecret123",
            "country_code": "JO",
            "role": "rider",
        },
    )
    with pytest.raises(provision_test_accounts.ProvisionRefused, match="غيرُ موسومٍ"):
        await provision_test_accounts.provision(secrets_file=_secrets_dir / "x.env", session_factory=session_factory)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User).where(User.is_test.is_(True))) == 0
    assert not (_secrets_dir / "x.env").exists()


async def test_the_script_refuses_a_secrets_path_in_the_repo_on_tmp_or_unmounted(
    jordan_settings: None, session_factory, _no_messages: None
) -> None:
    """**المسارُ يُردّ قبل أيِّ صفّ** — وكلُّ مردودٍ هو ما يخطر بعد أن يسقط الأمرُ الموثَّق: شجرةُ المستودع (`/app` في
    الحاوية = `./backend` على الخادم)، و`/tmp` الذي يُمحى بخروج الحاوية، ومجلّدٌ لم يُربط (`/out` بلا `-v`)."""
    await ensure_plan(session_factory)
    backend_root = Path(provision_test_accounts.__file__).resolve().parents[1]
    cases = (
        (backend_root / f"test-accounts-{uuid.uuid4().hex}.env", "شجرة المستودع"),
        (Path("/tmp") / f"test-accounts-{uuid.uuid4().hex}.env", "يُمحى"),
        (Path(f"/out-{uuid.uuid4().hex}") / "test-accounts.env", "غير موجود"),
    )
    for target, reason in cases:
        try:
            with pytest.raises(provision_test_accounts.ProvisionRefused, match=reason):
                await provision_test_accounts.provision(secrets_file=target, session_factory=session_factory)
            assert not target.exists()
        finally:
            # **وإن سقط الحارسُ لا يبقى ملفُّ أسرارٍ في الشجرة** — المجموعةُ تعمل على نسخة العمل نفسِها
            target.unlink(missing_ok=True)
    async with session_factory() as session:
        phones = (provision_test_accounts.RIDER_PHONE, provision_test_accounts.CAPTAIN_PHONE)
        assert await session.scalar(select(func.count()).select_from(User).where(User.phone.in_(phones))) == 0


async def test_no_request_schema_can_carry_the_mark() -> None:
    """**ولا بابَ في التطبيقات ولا اللوحة يكتب الوسم**: لا مخطَّطَ طلبٍ (`*In` · `*Create` · `*Update` · `*Request`) يحمل
    `is_test` — **وحقلٌ يُضاف إليه يوماً يُسقط هذا**."""
    import inspect

    from pydantic import BaseModel

    import app.schemas as schemas_pkg
    import pkgutil
    import importlib

    carriers: list[str] = []
    scanned = 0
    for module_info in pkgutil.iter_modules(schemas_pkg.__path__):
        module = importlib.import_module(f"app.schemas.{module_info.name}")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls, BaseModel) or cls.__module__ != module.__name__:
                continue
            if not name.endswith(("In", "Create", "Update", "Request", "Patch", "Purchase")):
                continue
            scanned += 1
            if "is_test" in cls.model_fields:
                carriers.append(f"{module.__name__}.{name}")
    # **إثباتُ الصمت** (قاعدةُ المِسبار ٥): مسحٌ لا يجد مخطَّطاً يمرّ أخضرَ أبداً
    assert scanned >= 30, f"لم يُقرأ إلا {scanned} مخطَّطَ طلب — المسحُ أعمى"
    assert carriers == []


async def test_the_decision_point_defaults_to_the_real_world() -> None:
    """**ونقطةُ القرار تفترض الطالبَ حقيقيّاً** — بابٌ ينسى تمريرَ الوسم لا يرى كبتنَ التجربة أبداً (الاتجاهُ الآمن للخطأ)."""
    import inspect

    for function in (dispatch._eligible_levels, dispatch.eligible_driver_ids):
        assert inspect.signature(function).parameters["test"].default is False
