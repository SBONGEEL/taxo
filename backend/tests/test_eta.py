"""زمنُ الوصول (§٦٢-ج/١٠) — **مطفأٌ لا نداءَ فيه، ومشتعلٌ نداءاتٌ تُحصى ولا تتكرّر**.

**ما يُسأل هنا**: مطفأً لا رقمَ ولا نداء؛ ومشتعلاً **يصير مسارُ العرض مسارَ الاقتراب عند القبول بلا نداءٍ ثانٍ** — وهو ما يجعل
الكلفةَ نداءً لكلِّ عرضٍ يُفتح لا نداءين؛ و«أقربُ كبتن» نداءٌ لكلِّ فئةٍ في الخليّة **ثمّ من المخزَّن**؛ والاقترابُ لطرفَي الرحلة وحدهما
والخطواتُ للكبتن؛ والعرضُ لمن عُرض عليه.
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.services.eta import calls_key
from tests.helpers import (
    OTHER_RIDER,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    enable_features,
    register,
    request_ride,
    wait_for_offer,
)


async def _calls() -> int:
    raw = await get_redis_client().get(calls_key(CountryCode.JO, datetime.now(UTC).strftime("%Y%m%d")))
    return int(raw or 0)


async def test_off_means_no_number_and_no_call(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))

    body = (await client.get("/rides/eta", params=PICKUP, headers=rider)).json()
    assert body == {"enabled": False, "categories": []}

    ride = await request_ride(client, rider)
    await wait_for_offer(ride["id"], driver["driver_id"])
    response = await client.get(f"/rides/{ride['id']}/offer-route", headers=driver["headers"])
    assert response.status_code == 404, response.text
    assert await _calls() == 0


async def test_the_offer_route_becomes_the_approach_without_a_second_call(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**نداءٌ لكلِّ عرضٍ يُفتح لا نداءان**: مسارُ العرض الطازجُ هو الاقترابُ عند القبول — وبغير ذلك يصير العددُ اثنين."""
    await enable_features(session_factory, "eta_enabled", "next_instruction_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))

    ride = await request_ride(client, rider)
    await wait_for_offer(ride["id"], driver["driver_id"])
    offered = await client.get(f"/rides/{ride['id']}/offer-route", headers=driver["headers"])
    assert offered.status_code == 200, offered.text
    route = offered.json()
    assert len(route["points"]) >= 2 and route["duration_min"] > 0 and route["steps"]
    assert await _calls() == 1

    # مخزَّنٌ — فتحُ البطاقة ثانيةً لا يدفع نداءً
    again = await client.get(f"/rides/{ride['id']}/offer-route", headers=driver["headers"])
    assert again.json() == route and await _calls() == 1

    accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
    assert accepted.status_code == 200, accepted.text
    assert await _calls() == 1, "القبولُ يجب أن يعيد استعمالَ مسار العرض"

    mine = (await client.get(f"/rides/{ride['id']}/approach", headers=driver["headers"])).json()
    theirs = (await client.get(f"/rides/{ride['id']}/approach", headers=rider)).json()
    assert mine["points"] == route["points"] and mine["steps"], "الكبتنُ يقرأ خطواتِه"
    assert theirs["points"] == route["points"] and theirs["steps"] == [], "والراكبُ لا يقود"
    assert await _calls() == 1


async def test_the_approach_is_for_the_two_parties_and_the_offer_for_its_holder(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, "eta_enabled")
    driver = await approved_driver(client, session_factory)
    other = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-5555")
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    stranger = auth(await register(client, OTHER_RIDER))

    ride = await request_ride(client, rider)
    holder = await wait_for_offer(ride["id"])
    outsider = other if holder == driver["driver_id"] else driver
    refused = await client.get(f"/rides/{ride['id']}/offer-route", headers=outsider["headers"])
    assert refused.status_code == 409, refused.text

    response = await client.get(f"/rides/{ride['id']}/approach", headers=stranger)
    assert response.status_code == 404, response.text


async def test_nearest_is_one_call_per_category_then_cached(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**أقربُ كبتنٍ لكلِّ فئة** — والمخزَّنُ دقيقةً للخليّة: سؤالان من الحيّ نفسِه نداءٌ واحد."""
    await enable_features(session_factory, "eta_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))

    first = (await client.get("/rides/eta", params=PICKUP, headers=rider)).json()
    assert first["enabled"] is True
    assert [row["vehicle_category"] for row in first["categories"]] == ["economy"]
    assert first["categories"][0]["minutes"] >= 1
    assert await _calls() == 1

    nearby = {"lat": PICKUP["lat"] + 0.0004, "lng": PICKUP["lng"] + 0.0004}
    second = (await client.get("/rides/eta", params=nearby, headers=rider)).json()
    assert second == first and await _calls() == 1


async def test_a_driver_has_no_eta_door(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    driver = await approved_driver(client, session_factory)
    response = await client.get("/rides/eta", params=PICKUP, headers=driver["headers"])
    assert response.status_code == 403
