"""**ما يضيفه الناسُ إلى الخريطة، والازدحامُ المجهول** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢-٣ و٣).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**
١) الاقتراحُ لا يُرى قبل الموافقة، والموافقةُ تُولِّد مكاناً بمصدر `community` يُرسم؛ والرفضُ بسبب؛ والمطفأُ يُردّ.
٢) **والتزامنُ في `test_map_community_concurrency.py`** — موافقاتٌ معاً وتأكيداتٌ معاً، وكلٌّ يسقط بحذف قفله.
٣) البلاغُ لا يُرى بكبتنٍ واحد، ويُرى بكبتنَين مختلفين أو بموافقة المشرف؛ والكبتنُ لا يؤكّد بلاغَه مرّتين؛ والراكبُ لا يبلّغ؛ والمزالُ لا يُرى.
٤) الازدحام: لا هويّةَ في العيّنة، والعيّناتُ تُمحى عند التجميع، **ولا لونَ تحت ثلاثة كباتن مختلفين**؛ والمطفأُ لا يجمع شيئاً.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest
from httpx import AsyncClient

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.services import traffic
from tests.helpers import DRIVER, SECOND_DRIVER, auth, enable_features, register, rider_session

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("jordan_settings")]

PLACE = {"kind": "add", "name_ar": "صيدلية النور", "category": "clinic", "lat": 31.95, "lng": 35.91}


async def test_a_suggestion_is_invisible_until_approved_then_drawn_as_a_community_place(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    rider = await rider_session(client)
    refused = await client.post("/map/suggestions", json=PLACE, headers=rider["headers"])
    assert refused.status_code == 422, "المفتاحُ مطفأ ⇐ يُردّ"

    await enable_features(session_factory, "map_place_suggestions", "map_places_enabled")
    sent = await client.post("/map/suggestions", json=PLACE, headers=rider["headers"])
    assert sent.status_code == 201, sent.text
    assert sent.json()["status"] == "pending"
    drawn = (await client.get("/map-places", headers=rider["headers"])).json()
    assert all(p["name_ar"] != "صيدلية النور" for p in drawn), "لا يُرى قبل الموافقة"

    queue = (await client.get("/admin/map/suggestions", headers=admin_headers)).json()
    assert [row["name_ar"] for row in queue] == ["صيدلية النور"]
    approved = await client.post(
        f"/admin/map/suggestions/{queue[0]['id']}/approve", json={"category": "clinic"}, headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    drawn = (await client.get("/map-places", headers=rider["headers"])).json()
    assert any(p["name_ar"] == "صيدلية النور" for p in drawn), "بعد الموافقة يُرسم"
    again = await client.post(f"/admin/map/suggestions/{queue[0]['id']}/reject", json={"reason": "مكرّر"}, headers=admin_headers)
    assert again.status_code == 422, "رُوجع من قبل"

    other = await client.post("/map/suggestions", json=PLACE | {"name_ar": "مكانٌ وهميّ"}, headers=rider["headers"])
    rejected = await client.post(f"/admin/map/suggestions/{other.json()['id']}/reject", json={"reason": "غير موجود"}, headers=admin_headers)
    assert rejected.json()["status"] == "rejected" and rejected.json()["review_note"] == "غير موجود"


async def test_a_road_report_needs_a_second_driver_or_the_admin(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    await enable_features(session_factory, "map_road_reports")
    rider = await rider_session(client)
    first = auth(await register(client, DRIVER))
    second = auth(await register(client, SECOND_DRIVER))
    spot = {"kind": "works", "lat": 31.96, "lng": 35.90}

    assert (await client.post("/map/road-reports", json=spot, headers=rider["headers"])).status_code == 403, "الراكبُ لا يبلّغ"
    made = (await client.post("/map/road-reports", json=spot, headers=first)).json()
    assert made["created"] is True and made["visible"] is False
    assert (await client.get("/map/road-reports", headers=rider["headers"])).json() == [], "كابتنٌ واحدٌ لا يكفي"
    twice = (await client.post("/map/road-reports", json=spot, headers=first)).json()
    assert twice["counted"] is False and twice["confirmations"] == 1, "لا يؤكّد بلاغَه مرّتين"
    near = (await client.post("/map/road-reports", json=spot | {"lat": 31.9605}, headers=second)).json()
    assert near["created"] is False and near["confirmations"] == 2 and near["visible"] is True
    shown = (await client.get("/map/road-reports", headers=rider["headers"])).json()
    assert [r["kind"] for r in shown] == ["works"] and "user_id" not in shown[0]

    lone = (await client.post("/map/road-reports", json={"kind": "closed", "lat": 31.99, "lng": 35.85}, headers=first)).json()
    assert (await client.post(f"/admin/map/road-reports/{lone['id']}/approve", headers=admin_headers)).status_code == 200
    assert {r["kind"] for r in (await client.get("/map/road-reports", headers=rider["headers"])).json()} == {"works", "closed"}
    assert (await client.post(f"/admin/map/road-reports/{lone['id']}/remove", headers=admin_headers)).status_code == 200
    assert {r["kind"] for r in (await client.get("/map/road-reports", headers=rider["headers"])).json()} == {"works"}


async def test_traffic_is_anonymous_and_needs_three_distinct_drivers(monkeypatch) -> None:
    redis = get_redis_client()
    segment = {"free": 60, "coords": [[35.9, 31.95], [35.901, 31.95]]}

    async def fake_places(path: str, payload: dict | None = None):
        if path == "/match":
            return {"segs": [7] * len(payload["points"])}
        return {"segments": {"7": segment}}

    monkeypatch.setattr(traffic, "_places", fake_places)
    off = await traffic.aggregate(redis, CountryCode.JO, enabled=False)
    assert off["enabled"] is False
    assert await traffic.previous(redis, driver_id=uuid.uuid4(), country_code=CountryCode.JO) is None, "مطفأٌ ⇐ لا قراءة"

    await traffic.aggregate(redis, CountryCode.JO, enabled=True)  # يرفع علامةَ الدولة
    now = int(time.time())
    drivers = [uuid.uuid4() for _ in range(3)]
    for driver in drivers[:2]:
        await traffic.sample(redis, driver_id=driver, country_code=CountryCode.JO, previous=(31.95, 35.9, now - 10),
                             lat=31.95, lng=35.9005, heading=90.0)
    raw = await redis.lrange("traffic:raw:JO", 0, -1)
    assert len(raw) == 2 and all(str(d) not in r.decode() if isinstance(r, bytes) else str(d) not in r for r in raw for d in drivers), \
        "لا هويّةَ في العيّنة"
    await traffic.aggregate(redis, CountryCode.JO, enabled=True)
    assert await redis.llen("traffic:raw:JO") == 0, "العيّناتُ تُمحى عند التجميع"
    assert (await traffic.view(redis, CountryCode.JO))["features"] == [], "كابتنان ⇐ لا لون"

    await traffic.sample(redis, driver_id=drivers[2], country_code=CountryCode.JO, previous=(31.95, 35.9, now - 10),
                         lat=31.95, lng=35.9005, heading=90.0)
    await traffic.aggregate(redis, CountryCode.JO, enabled=True)
    features = (await traffic.view(redis, CountryCode.JO))["features"]
    assert len(features) == 1 and features[0]["properties"] == {"l": "heavy"}, "ثلاثةٌ مختلفون ⇐ لون (≈١٧ كم/س على طريقٍ بستّين: ثقيل)"
    assert json.dumps(features).count(str(drivers[0])) == 0
