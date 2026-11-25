"""**عروضُ الركّاب** (§١١٤-د، أمرُ المالك ٢٠٢٦-١١-٢٤ السادس) — عرضٌ بلا رمز، ومن يتحمّل خصمَه.

* **«أوّلُ رحلة» يُطبَّق بلا رمز** على رحلة الراكب الأولى، **ولا يُطبَّق على حساب تجربة**.
* **وفي فترة الكبتن المجّانية يتحمّل الكبتنُ الخصم**: تنقص الأجرةُ نفسُها ويُكتب سطرُ «خصم العرض»، **ولا صفَّ `promo`**
  تدفعه الشركة — نقيضُ `test_promo.test_the_company_bears_it_so_the_driver_is_untouched` بعينه.
* **وخارجها تتحمّله الشركةُ كما قرّر العرض** (`bearer_after_free`) — والأجرةُ كاملةٌ وصفُّ `promo` قائم.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, PaymentMethod, PromoDiscountType
from app.models.payment import Payment
from app.models.promo import PromoCode
from app.models.ride import Ride
from tests.helpers import DRIVER, DROPOFF, PICKUP, approved_driver, bring_online, enable_features, rider_session, wait_for_offer


async def _first_ride_offer(session_factory, *, bearer: str = "company") -> None:
    async with session_factory() as session:
        session.add(
            PromoCode(
                code="FIRST-RIDE-AUTO",
                country_code=CountryCode.JO,
                kind="first_ride",
                is_public=False,
                bearer_after_free=bearer,
                discount_type=PromoDiscountType.FIXED,
                discount_value=Decimal("0.500"),
                max_discount=None,
                budget_total=Decimal("100.000"),
                per_user_limit=1,
            )
        )
        await session.commit()


async def _ride(client: AsyncClient, rider_headers: dict, driver: dict) -> dict:
    response = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}, headers=rider_headers
    )
    assert response.status_code == 201, response.text
    ride_id = response.json()["id"]
    await wait_for_offer(ride_id, driver["driver_id"])
    for step in ("accept", "arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    return done.json()


async def _promo_payment(session_factory, ride_id: str) -> Payment | None:
    async with session_factory() as session:
        return await session.scalar(
            select(Payment).where(Payment.ride_id == ride_id, Payment.method == PaymentMethod.PROMO)
        )


async def test_after_the_free_period_the_company_bears_the_first_ride_discount(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, "promo_codes_enabled")
    await _first_ride_offer(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _ride(client, rider["headers"], driver)
    async with session_factory() as session:
        row = await session.get(Ride, ride["id"])
        assert row.promo_code_id is not None and row.discount_bearer == "company"
    payment = await _promo_payment(session_factory, ride["id"])
    assert payment is not None and payment.amount == Decimal("0.500")
    assert all(line["kind"] != "offer_discount" for line in ride["fare_lines"])


async def test_in_the_free_period_the_captain_bears_it_and_the_fare_itself_drops(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    # **والقاعدةُ بمفتاحها** (أمرُ المالك الحادي عشر ٢٠٢٦-١١-٢٥) — منفصلةٌ عن إشعال الحملة
    await enable_features(session_factory, "promo_codes_enabled", "launch_captain_bears_discounts")
    await _first_ride_offer(session_factory)
    # **قبل الإطلاق والكبتنُ معتمَد** ⇐ في فترته المجّانية
    campaign = await client.patch(
        "/admin/launch-campaign",
        params={"country_code": "JO"},
        json={"is_enabled": True, "launch_date": (date.today() + timedelta(days=30)).isoformat()},
        headers=admin_headers,
    )
    assert campaign.status_code == 200, campaign.text
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _ride(client, rider["headers"], driver)
    async with session_factory() as session:
        row = await session.get(Ride, ride["id"])
        assert row.discount_bearer == "captain"
    lines = {line["kind"]: Decimal(line["amount"]) for line in ride["fare_lines"]}
    assert lines.get("offer_discount") == Decimal("-0.500")
    assert await _promo_payment(session_factory, ride["id"]) is None

    month = (await client.get("/drivers/me/offer-discounts", headers=driver["headers"])).json()
    assert Decimal(month["total"]) == Decimal("0.500") and len(month["rides"]) == 1


async def test_a_second_ride_gets_no_first_ride_offer(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    await enable_features(session_factory, "promo_codes_enabled")
    await _first_ride_offer(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await _ride(client, rider["headers"], driver)
    await bring_online(client, driver)
    second = await _ride(client, rider["headers"], driver)
    async with session_factory() as session:
        row = await session.get(Ride, second["id"])
        assert row.promo_code_id is None


async def test_the_campaign_on_and_the_captain_rule_off_leaves_the_discount_on_the_company(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """**أمرُ المالك الحادي عشر (٢٠٢٦-١١-٢٥)**: الحملةُ تُشعَل **وقاعدةُ «يتحمّل الكبتنُ الخصم» مطفأةٌ حتى ينشر الشروط** — فإشعالُ الحملة
    وحدَه لا يُحمِّل كبتناً في فترته المجّانية خصماً: الدافعُ ما اختاره العرض، والأجرةُ لا سطرَ «خصم عرض» فيها."""
    await enable_features(session_factory, "promo_codes_enabled")
    await _first_ride_offer(session_factory)
    campaign = await client.patch(
        "/admin/launch-campaign",
        params={"country_code": "JO"},
        json={"is_enabled": True, "launch_date": (date.today() + timedelta(days=30)).isoformat()},
        headers=admin_headers,
    )
    assert campaign.status_code == 200, campaign.text
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _ride(client, rider["headers"], driver)
    async with session_factory() as session:
        row = await session.get(Ride, ride["id"])
        assert row.discount_bearer == "company"
    assert all(line["kind"] != "offer_discount" for line in ride["fare_lines"])
    mine = (await client.get("/drivers/me/launch-campaign", headers=driver["headers"])).json()
    assert mine["enabled"] is True and mine["status"] == "pre_launch"
    assert mine["ack_required"] is False and mine["partner_notice"] == ""
