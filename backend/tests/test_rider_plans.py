"""**اشتراكاتُ الركّاب** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣).

مطفأً لا خطّةَ تُرى ولا تُباع · الشراءُ يقتطع الثمنَ من المحفظة مرّةً ويرفض الثاني والاشتراكُ سارٍ · الخصمُ عند الإنهاء: TAXO تتحمّله ⇐
صفُّ `promo` والأجرةُ كما هي، الكبتنُ يتحمّله ⇐ الأجرةُ تنقص بسطرها · حدُّ الرحلة · وخانات العملة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import FeatureKey, PaymentMethod
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.rider_plan import RiderPlanUse
from tests.helpers import NEAR_PICKUP, approved_driver, bring_online, completed_ride, enable_features, rider_session, topup_wallet, wallet_of


async def _plan(client: AsyncClient, headers: dict, **extra) -> dict:
    body = {"name": "شهريّ", "days": 30, "price": "5.000", "discount_percent": "20", "per_ride_cap": "1.000",
            "monthly_cap": "10.000", "bearer": "taxo", **extra}
    answer = await client.post("/admin/rider-plans", params={"country_code": "JO"}, json=body, headers=headers)
    assert answer.status_code == 201, answer.text
    return answer.json()


async def test_off_shows_and_sells_nothing(client: AsyncClient, admin_headers: dict) -> None:
    plan = await _plan(client, admin_headers)
    rider = await rider_session(client)
    mine = (await client.get("/rider-plans", headers=rider["headers"])).json()
    assert mine["enabled"] is False and mine["plans"] == [] and mine["current"] is None
    bought = await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])
    assert bought.status_code in (403, 409, 422), bought.text


async def test_buying_takes_the_price_once(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    plan = await _plan(client, admin_headers)
    await enable_features(session_factory, FeatureKey.RIDER_PLANS_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "8.000")
    bought = await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])
    assert bought.status_code == 201, bought.text
    assert bought.json()["current"]["plan_name"] == "شهريّ"
    assert Decimal((await wallet_of(client, rider["headers"]))["balance"]) == Decimal("3.000")
    again = await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])
    assert again.status_code == 409, again.text


async def test_taxo_bears_the_discount_as_a_promo_row(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    plan = await _plan(client, admin_headers)
    await enable_features(session_factory, FeatureKey.RIDER_PLANS_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    ride, rider, _driver = await _ride_with_plan(client, session_factory, admin_headers, plan)
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        promo = await session.scalar(select(Payment).where(Payment.ride_id == row.id, Payment.method == PaymentMethod.PROMO))
        use = await session.scalar(select(RiderPlanUse).where(RiderPlanUse.ride_id == row.id))
        assert use is not None and promo is not None and promo.amount == use.amount
        assert use.amount == min((row.final_fare * Decimal("0.2")).quantize(Decimal("0.001")), Decimal("1.000"))
        assert not any(line["kind"] == "plan_discount" for line in (row.fare_lines or []))


async def test_the_captain_bears_it_as_a_smaller_fare(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    plan = await _plan(client, admin_headers, bearer="captain")
    await enable_features(session_factory, FeatureKey.RIDER_PLANS_ENABLED.value, FeatureKey.WALLET_ENABLED.value)
    ride, rider, _driver = await _ride_with_plan(client, session_factory, admin_headers, plan)
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        use = await session.scalar(select(RiderPlanUse).where(RiderPlanUse.ride_id == row.id))
        assert use is not None
        assert await session.scalar(
            select(Payment).where(Payment.ride_id == row.id, Payment.method == PaymentMethod.PROMO)
        ) is None
        lines = [line for line in row.fare_lines if line["kind"] == "plan_discount"]
        assert lines and Decimal(lines[0]["amount"]) == -use.amount
        assert sum(Decimal(line["amount"]) for line in row.fare_lines) == row.final_fare


async def _ride_with_plan(client, session_factory, admin_headers, plan):
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "10.000")
    bought = await client.post(f"/rider-plans/{plan['id']}/subscribe", headers=rider["headers"])
    assert bought.status_code == 201, bought.text
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    done = await completed_ride(client, rider["headers"], driver)
    return done, rider, driver


async def test_amounts_follow_the_currency(client: AsyncClient, admin_headers: dict) -> None:
    answer = await client.post(
        "/admin/rider-plans",
        params={"country_code": "DZ"},
        json={"name": "شهريّ", "days": 30, "price": "500.5", "discount_percent": "10", "per_ride_cap": "100",
              "monthly_cap": "1000", "bearer": "taxo"},
        headers=admin_headers,
    )
    assert answer.status_code == 422, answer.text
