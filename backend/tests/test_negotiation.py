"""«تفاوض» على السعر، كبتنٌ واحدٌ في كلِّ مرّة (SPEC §٩٢، `design/NEGOTIATE.md`).

**كلُّ مسارٍ في §٩٢-هـ له اختبارٌ هنا**: قبول · رفضٌ ⇒ التالي · مقابلٌ ⇒ قبولُ الراكب · مقابلٌ ⇒ رفضُ الراكب ⇒ التالي · انقضاءُ المقابل ·
تعديلُ السعر أثناء البحث · عرضٌ تحت الحدّ · مطفأ. **والتزامنُ**: قبولُ الكبتن بسعر الراكب وقبولُ الراكب عرضَ الكبتن نفسِه في اللحظة
نفسِها لا يفوزان معاً — **وسعرُ الرحلة سعرُ الفائز وحدَه**.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.dispatch_setting import DispatchSetting
from app.models.enums import CountryCode, DispatchMode
from app.models.negotiation import NegotiationSetting, RideFareOffer
from app.models.ride import Ride
from app.services import dispatch, negotiation
from tests.helpers import (
    DRIVER,
    DROPOFF,
    FAR_PICKUP,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    register,
    wait_for_offer,
    wait_until,
)


@pytest.fixture
async def negotiation_on(session_factory, jordan_settings: None) -> None:
    async with session_factory() as session:
        session.add(
            NegotiationSetting(
                country_code=CountryCode.JO, enabled=True, min_percent=70, driver_timeout_seconds=20,
                rider_timeout_seconds=20, categories=[],
            )
        )
        await session.commit()


async def _driver(client, session_factory, payload=DRIVER, *, plate: str, location=NEAR_PICKUP) -> dict:
    driver = await approved_driver(client, session_factory, payload, plate_number=plate, category="economy")
    await bring_online(client, driver, location)
    return driver


async def _estimate(client: AsyncClient, headers: dict) -> dict:
    body = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}
    response = await client.post("/rides/estimate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _negotiate(client: AsyncClient, headers: dict, offer: str):
    body = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "negotiation": {"offer": offer}}
    return await client.post("/rides", json=body, headers=headers)


async def _kinds(session_factory, ride_id: str) -> list[str]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(RideFareOffer.kind).where(RideFareOffer.ride_id == uuid.UUID(ride_id)).order_by(RideFareOffer.created_at)
        )
        return list(rows)


async def _ride(session_factory, ride_id: str) -> Ride:
    async with session_factory() as session:
        return await session.get(Ride, uuid.UUID(ride_id))


# ------------------------------------------------------------- الحدُّ والإطفاء


async def test_estimate_carries_the_floor_only_when_enabled(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مطفأٌ ⇒ لا حقلَ تفاوض** في التقدير ولا طلب؛ **مشتعلٌ ⇒ الحدُّ ونسبتُه من الخلفية** (§٩٢-ب)."""
    rider = auth(await register(client, RIDER))
    assert (await _estimate(client, rider))["negotiation_minimum"] is None
    refused = await _negotiate(client, rider, "1.500")
    assert refused.status_code == 422 and refused.json()["field"] == "negotiation"

    async with session_factory() as session:
        session.add(NegotiationSetting(country_code=CountryCode.JO, enabled=True, min_percent=70, categories=[]))
        await session.commit()
    estimate = await _estimate(client, rider)
    fare = Decimal(estimate["estimated_fare"])
    assert Decimal(estimate["negotiation_minimum"]) == (fare * Decimal("0.7")).quantize(Decimal("0.001"))
    assert estimate["negotiation_min_percent"] == 70


async def test_an_offer_under_the_floor_is_refused_with_its_minimum(
    client: AsyncClient, negotiation_on: None
) -> None:
    rider = auth(await register(client, RIDER))
    minimum = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    response = await _negotiate(client, rider, str(minimum - Decimal("0.100")))
    assert response.status_code == 422
    assert Decimal(response.json()["minimum"]) == minimum


async def test_the_floor_is_the_same_from_the_rounded_or_the_raw_estimate(
    session_factory, jordan_settings: None
) -> None:
    """**الحدُّ واحدٌ في كلِّ باب** (٢٠٢٦-١١-٠٦) — التقديرُ يمرّر المقرَّب، والطلبُ وتعديلُ السعر يمرّران `estimated_fare` الخام.

    قِيس على مكدّس التطوير في الجزائر: تقديرٌ ٣٤٤ خاماً يُعرض ٣٤٠، **والحدُّ المعروضُ ٢٤٠ والطلبُ يردّه طالباً ٢٥٠**. فالراكبُ يكتب
    ما قيل له إنه الأدنى فيُرفض. **وبعد الإصلاح**: الخامُ والمقرَّبُ يعطيان الحدَّ نفسَه.
    """
    from app.models.payment_setting import PaymentSetting

    async with session_factory() as session:
        row = await session.scalar(select(PaymentSetting).where(PaymentSetting.country_code == CountryCode.JO))
        if row is None:
            row = PaymentSetting(country_code=CountryCode.JO)
            session.add(row)
        row.rounding_enabled, row.rounding_unit, row.rounding_mode = True, Decimal("10"), "nearest"
        await session.commit()
        rules = negotiation.NegotiationRules(
            enabled=True, min_percent=70, min_amount=None, driver_timeout_seconds=20, rider_timeout_seconds=20,
            max_counter_percent=None, max_drivers=None, categories=(),
        )
        from_raw = await negotiation.floor_for(session, CountryCode.JO, rules, Decimal("344"))
        from_rounded = await negotiation.floor_for(session, CountryCode.JO, rules, Decimal("340"))
    assert from_raw.minimum == from_rounded.minimum == Decimal("240")


# ------------------------------------------------------------------ المسارات


async def test_driver_accepts_the_riders_price(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**قبولٌ ⇒ مؤكَّدةٌ بسعر الراكب** (§٩٢-أ/٣) — ويحلّ محلَّ التقدير بسطرٍ واحد."""
    driver = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    assert Decimal(ride["negotiation_offer"]) == offer

    await wait_for_offer(ride["id"], driver["driver_id"])
    accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert Decimal(body["negotiated_fare"]) == offer and Decimal(body["estimated_fare"]) == offer
    assert [line["kind"] for line in body["fare_lines"]] == ["negotiated"]
    assert await _kinds(session_factory, ride["id"]) == ["rider_offer", "driver_accept"]


async def test_counter_then_rider_accepts_at_the_drivers_price(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], driver["driver_id"])

    # **ما يساوي عرضَ الراكب قبولٌ لا عرضٌ مقابل**
    same = await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(offer)}, headers=driver["headers"])
    assert same.status_code == 422
    higher = offer + Decimal("1.000")
    countered = await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(higher)}, headers=driver["headers"])
    assert countered.status_code == 200, countered.text
    assert Decimal(countered.json()["amount"]) == higher and countered.json()["expires_in_seconds"] == 20

    state = (await client.get(f"/rides/{ride['id']}/negotiation", headers=rider)).json()
    assert Decimal(state["counter"]["amount"]) == higher and state["counter"]["expires_in_seconds"] > 0

    accepted = await client.post(f"/rides/{ride['id']}/counter/accept", headers=rider)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["driver"] is not None
    row = await _ride(session_factory, ride["id"])
    assert row.negotiated_fare == higher and row.driver_id == driver["driver_id"]
    assert await _kinds(session_factory, ride["id"]) == ["rider_offer", "counter", "rider_accept"]


async def test_counter_rejected_moves_on_at_the_riders_original_price(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**رفضُ الراكب ⇒ إلى الكبتن التالي بسعره الأصليّ** (§٩٢-أ/٤)، ولا أخذَ وردَّ بعده."""
    near = await _driver(client, session_factory, plate="AMM-1")
    far = await _driver(client, session_factory, SECOND_DRIVER, plate="AMM-7", location=FAR_PICKUP)
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], near["driver_id"])
    await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(offer + 1)}, headers=near["headers"])

    assert (await client.post(f"/rides/{ride['id']}/counter/reject", headers=rider)).status_code == 204
    assert await wait_for_offer(ride["id"], far["driver_id"]) == far["driver_id"]
    assert (await _ride(session_factory, ride["id"])).negotiation_offer == offer
    accepted = await client.post(f"/rides/{ride['id']}/accept", headers=far["headers"])
    assert Decimal(accepted.json()["negotiated_fare"]) == offer
    assert await _kinds(session_factory, ride["id"]) == ["rider_offer", "counter", "rider_reject", "driver_accept"]


async def test_a_driver_who_declines_after_countering_withdraws_the_counter(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**من سحب نفسَه سحب عرضَه** — فلا يقبل الراكبُ سعرَ كبتنٍ طُويت بطاقتُه."""
    driver = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], driver["driver_id"])
    await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(offer + 1)}, headers=driver["headers"])
    assert (await client.post(f"/rides/{ride['id']}/decline", headers=driver["headers"])).status_code == 204
    assert (await client.get(f"/rides/{ride['id']}/negotiation", headers=rider)).json()["counter"] is None
    assert (await client.post(f"/rides/{ride['id']}/counter/accept", headers=rider)).status_code == 409


async def test_driver_decline_moves_on_and_is_recorded(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    near = await _driver(client, session_factory, plate="AMM-1")
    far = await _driver(client, session_factory, SECOND_DRIVER, plate="AMM-7", location=FAR_PICKUP)
    rider = auth(await register(client, RIDER))
    offer = (await _estimate(client, rider))["negotiation_minimum"]
    ride = (await _negotiate(client, rider, offer)).json()
    await wait_for_offer(ride["id"], near["driver_id"])
    assert (await client.post(f"/rides/{ride['id']}/decline", headers=near["headers"])).status_code == 204
    assert await wait_for_offer(ride["id"], far["driver_id"]) == far["driver_id"]
    assert await _kinds(session_factory, ride["id"]) == ["rider_offer", "driver_decline"]


async def test_an_unanswered_counter_expires_and_the_search_goes_on(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مهلةُ الراكب على المقابل** (§٩٢-أ/٦) — انقضاؤها رفضٌ ويمضي الطلب، ويُسجَّل «انقضاء»."""
    async with session_factory() as session:
        session.add(NegotiationSetting(country_code=CountryCode.JO, enabled=True, rider_timeout_seconds=5, categories=[]))
        await session.commit()
    near = await _driver(client, session_factory, plate="AMM-1")
    far = await _driver(client, session_factory, SECOND_DRIVER, plate="AMM-7", location=FAR_PICKUP)
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], near["driver_id"])
    await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(offer + 1)}, headers=near["headers"])

    assert await wait_for_offer(ride["id"], far["driver_id"]) == far["driver_id"]
    assert (await client.post(f"/rides/{ride['id']}/counter/accept", headers=rider)).status_code == 409
    assert "expired" in await _kinds(session_factory, ride["id"])


async def test_changing_the_price_restarts_the_search(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**التعديلُ يبدأ البحثَ من جديد** (§٩٢-أ/٥) — ومن رفض السعرَ القديم يُعرض عليه الجديد (التبريدُ يُمسح)."""
    near = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], near["driver_id"])
    await client.post(f"/rides/{ride['id']}/decline", headers=near["headers"])

    raised = offer + Decimal("1.000")
    changed = await client.post(f"/rides/{ride['id']}/offer", json={"amount": str(raised)}, headers=rider)
    assert changed.status_code == 200, changed.text
    assert await wait_for_offer(ride["id"], near["driver_id"]) == near["driver_id"]
    accepted = await client.post(f"/rides/{ride['id']}/accept", headers=near["headers"])
    assert Decimal(accepted.json()["negotiated_fare"]) == raised


async def test_negotiation_is_sequential_even_in_a_broadcast_market(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**كبتنٌ واحدٌ في كلِّ مرّة** (§٩٢-أ/٣) — والسوقُ في نمط البثّ لا يجعلها مزاداً."""
    async with session_factory() as session:
        session.add(DispatchSetting(country_code=CountryCode.JO, mode=DispatchMode.BROADCAST, broadcast_batch_size=4))
        await session.commit()
    first = await _driver(client, session_factory, plate="AMM-1")
    second = await _driver(client, session_factory, SECOND_DRIVER, plate="AMM-7")
    rider = auth(await register(client, RIDER))
    offer = (await _estimate(client, rider))["negotiation_minimum"]
    ride = (await _negotiate(client, rider, offer)).json()
    offered = await wait_for_offer(ride["id"])
    redis = get_redis_client()
    assert await dispatch.broadcast_members(redis, uuid.UUID(ride["id"])) == set()
    other = second["driver_id"] if offered == first["driver_id"] else first["driver_id"]
    # **الآخرُ غيرُ محجوز** — لا عرضَ عليه ولا حجز
    assert await redis.get(dispatch.driver_offer_key(other)) is None


async def test_negotiation_refuses_promo_and_share(client: AsyncClient, negotiation_on: None) -> None:
    rider = auth(await register(client, RIDER))
    offer = (await _estimate(client, rider))["negotiation_minimum"]
    body = {
        "pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "negotiation": {"offer": offer}, "share": True,
    }
    response = await client.post("/rides", json=body, headers=rider)
    assert response.status_code == 422 and response.json()["field"] == "negotiation"


# ------------------------------------------------------------------- اللوحة


async def test_admin_turns_it_on_and_unknown_categories_are_refused(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    """**الغيابُ مطفأ** ولا يُخترع صفّ، والتشغيلُ يكتب صفّاً، **والفئةُ بمفتاحها في السوق** لا قائمةٌ ثانية (§٩٢-ب)."""
    assert (await client.get("/admin/settings/negotiation", headers=admin_headers)).json() == []
    on = await client.patch(
        "/admin/settings/negotiation/JO", json={"enabled": True, "min_percent": 80, "categories": ["economy"]},
        headers=admin_headers,
    )
    assert on.status_code == 200, on.text
    assert on.json()["enabled"] is True and on.json()["min_percent"] == 80 and on.json()["categories"] == ["economy"]

    unknown = await client.patch("/admin/settings/negotiation/JO", json={"categories": ["spaceship"]}, headers=admin_headers)
    assert unknown.status_code == 422 and unknown.json()["field"] == "categories"
    emptied = await client.patch("/admin/settings/negotiation/JO", json={"min_percent": None}, headers=admin_headers)
    assert emptied.status_code == 422
    low = await client.patch("/admin/settings/negotiation/JO", json={"min_percent": 5}, headers=admin_headers)
    assert low.status_code == 422

    rider = auth(await register(client, RIDER))
    estimate = await _estimate(client, rider)
    assert estimate["negotiation_min_percent"] == 80


# ------------------------------------------------------------------- التزامن


async def test_driver_accept_and_counter_accept_at_once_leave_one_price(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    """**قبولان في اللحظة نفسِها لا يفوزان معاً** — الكبتنُ يقبل بسعر الراكب والراكبُ يقبل عرضَه المقابل.

    يحرسه قفلُ صفِّ الرحلة في `rides._take`: الخاسرُ يُردّ بحالٍ لا بمهلة، **وسعرُ الرحلة سعرُ الفائز وحدَه**، وسطرُ قبولٍ واحدٌ في السجلّ.
    """
    driver = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], driver["driver_id"])
    higher = offer + Decimal("1.000")
    await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(higher)}, headers=driver["headers"])

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"]),
            client.post(f"/rides/{ride['id']}/counter/accept", headers=rider),
        ),
        timeout=20,
    )
    codes = Counter(response.status_code for response in responses)
    assert codes[200] == 1, [response.text for response in responses]
    row = await _ride(session_factory, ride["id"])
    winner = next(response for response in responses if response.status_code == 200)
    assert row.negotiated_fare == Decimal(winner.json()["negotiated_fare"])
    kinds = await _kinds(session_factory, ride["id"])
    assert kinds.count("driver_accept") + kinds.count("rider_accept") == 1


async def test_two_counter_accepts_at_once_take_it_once(
    client: AsyncClient, negotiation_on: None, session_factory
) -> None:
    driver = await _driver(client, session_factory, plate="AMM-1")
    rider = auth(await register(client, RIDER))
    offer = Decimal((await _estimate(client, rider))["negotiation_minimum"])
    ride = (await _negotiate(client, rider, str(offer))).json()
    await wait_for_offer(ride["id"], driver["driver_id"])
    await client.post(f"/rides/{ride['id']}/counter", json={"amount": str(offer + 1)}, headers=driver["headers"])

    responses = await asyncio.wait_for(
        asyncio.gather(*[client.post(f"/rides/{ride['id']}/counter/accept", headers=rider) for _ in range(3)]),
        timeout=20,
    )
    codes = Counter(response.status_code for response in responses)
    assert codes == Counter({200: 1, 409: 2}), [response.text for response in responses]
    assert (await _kinds(session_factory, ride["id"])).count("rider_accept") == 1
