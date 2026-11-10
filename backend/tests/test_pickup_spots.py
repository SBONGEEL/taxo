"""**نقاطُ التقاطٍ ذكيّة** (البند ١١، §٩٧/١١) — نقطةُ المالك أوّلاً باسمها، ثم الالتقاطاتُ المجمَّعة، ولا خليةَ دون ثلاثة ركّاب."""

from __future__ import annotations

import json
import uuid

from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.map_place import MapPlace
from app.services import pickup_spots
from tests.helpers import rider_session

PIN = (31.9539, 35.9106)


def test_a_cell_needs_three_different_riders() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [(a, 31.95, 35.91), (b, 31.95001, 35.91001), (c, 31.95002, 35.90999)]
    # **راكبٌ واحدٌ يلتقط من بابه عشرَ مرّاتٍ لا يصير «نقطة»** — فلا يُقرأ موقعُه من الخلايا
    rows += [(a, 31.96, 35.92)] * 10
    spots = pickup_spots.cluster(rows)
    assert len(spots) == 1 and spots[0][2] == 3


async def test_owner_point_first_then_history_and_the_switch(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    rider = await rider_session(client)
    url = "/pickup/suggestion"

    # لا شيءَ بعد ⇒ null
    empty = await client.get(url, params={"lat": PIN[0], "lng": PIN[1]}, headers=rider["headers"])
    assert empty.status_code == 200 and empty.json() is None

    # **الالتقاطاتُ السابقة**: خليةٌ على بُعد ~٦٠ م
    redis = get_redis_client()
    await redis.set(pickup_spots.KEY.format(country="JO"), json.dumps([[31.9544, 35.9107, 12]]))
    learned = (await client.get(url, params={"lat": PIN[0], "lng": PIN[1]}, headers=rider["headers"])).json()
    assert learned["source"] == "history" and learned["name_ar"] is None and 40 <= learned["distance_m"] <= 80

    # **نقطةُ المالك تتقدّم** باسمها
    async with session_factory() as session:
        session.add(MapPlace(country_code=CountryCode.JO, name_ar="البوّابة الشمالية", name_en="North gate",
                             category="pickup", lat=31.9537, lng=35.9109))
        await session.commit()
    named = (await client.get(url, params={"lat": PIN[0], "lng": PIN[1]}, headers=rider["headers"])).json()
    assert named["source"] == "place" and named["name_ar"] == "البوّابة الشمالية"

    # **والدبّوسُ على النقطة نفسِها لا يُقترح عليه شيء**
    there = await client.get(url, params={"lat": 31.9537, "lng": 35.9109}, headers=rider["headers"])
    assert there.json() is None

    # **والمفتاحُ يطفئه** من اللوحة
    off = await client.patch("/admin/settings/map/JO", json={"pickup_suggest_enabled": False}, headers=admin_headers)
    assert off.status_code == 200 and off.json()["pickup_suggest_enabled"] is False
    assert (await client.get(url, params={"lat": PIN[0], "lng": PIN[1]}, headers=rider["headers"])).json() is None


async def test_the_nightly_build_runs_on_real_rides(session_factory) -> None:
    async with session_factory() as session:
        counts = await pickup_spots.rebuild(session, get_redis_client())
    assert set(counts) == {country.value for country in CountryCode}
