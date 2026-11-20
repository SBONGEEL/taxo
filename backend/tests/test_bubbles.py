"""**الفقاعتان — أجزاءُ الخادم** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، SPEC §١١٠).

ما يُقاس: الاستراحةُ (٤٤) تُخرج الكبتنَ من التوزيع حتى تنتهي **بالساعة وحدَها** ويمحوها الخروجُ، ولا تبدأ إلا متّصلاً بلا رحلة،
(والتزامنُ في `test_bubbles_concurrency.py`) · أقربُ منطقةٍ مزدحمة (٤٥) من خلايا الخريطة بمستوى ٢ فما فوق، و«لا نعرف»
بلا موقع · الردودُ السريعة (٥٠) بافتراض الأمر حرفاً، والحفظُ يرفض الرقمَ والرابطَ بمرشِّح المحادثة · وكلُّها مطفأةٌ بلا صفٍّ في المفاتيح.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.driver import Driver
from app.services import busy_area, heatmap
from tests.helpers import approved_driver, bring_online, enable_features

pytestmark = pytest.mark.asyncio


async def _eligible(session_factory, driver_id: uuid.UUID) -> bool:
    from app.services import dispatch

    async with session_factory() as session:
        return driver_id in await dispatch._eligible_levels(session, [driver_id], "economy")


# ─────────────────────────────── ٤٤ الاستراحة


async def test_a_break_is_refused_while_its_switch_is_off(client: AsyncClient, session_factory) -> None:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    refused = await client.post("/drivers/me/break", json={"minutes": 15}, headers=driver["headers"])
    assert refused.status_code == 403, refused.text


async def test_a_break_takes_the_driver_out_of_dispatch_until_the_clock_passes(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "driver_break")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    driver_id = uuid.UUID(str(driver["driver_id"]))
    assert await _eligible(session_factory, driver_id), "الكبتنُ غيرُ مؤهَّلٍ أصلاً — الاختبارُ لا يقيس شيئاً"

    started = await client.post("/drivers/me/break", json={"minutes": 15}, headers=driver["headers"])
    assert started.status_code == 200, started.text
    until = datetime.fromisoformat(started.json()["break_until"])
    assert timedelta(minutes=14) < until - datetime.now(UTC) <= timedelta(minutes=15)
    assert not await _eligible(session_factory, driver_id)
    me = await client.get("/drivers/me", headers=driver["headers"])
    assert me.json()["driver"]["break_until"] is not None

    # **يعود وحدَه** — بلا نداءٍ ولا مهمّة: الساعةُ تجاوزت الموعد
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        row.break_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert await _eligible(session_factory, driver_id)


async def test_ending_early_and_going_offline_both_clear_it(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "driver_break")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    driver_id = uuid.UUID(str(driver["driver_id"]))
    await client.post("/drivers/me/break", json={"minutes": 30}, headers=driver["headers"])
    ended = await client.delete("/drivers/me/break", headers=driver["headers"])
    assert ended.status_code == 200 and ended.json()["break_until"] is None
    assert await _eligible(session_factory, driver_id)

    await client.post("/drivers/me/break", json={"minutes": 15}, headers=driver["headers"])
    await client.post("/drivers/me/offline", headers=driver["headers"])
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        assert row.is_online is False and row.break_until is None


async def test_only_fifteen_or_thirty_and_only_while_online(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "driver_break")
    driver = await approved_driver(client, session_factory)
    offline = await client.post("/drivers/me/break", json={"minutes": 15}, headers=driver["headers"])
    assert offline.status_code == 409 and offline.json()["code"] == "break_not_allowed", offline.text
    await bring_online(client, driver)
    odd = await client.post("/drivers/me/break", json={"minutes": 45}, headers=driver["headers"])
    assert odd.status_code == 422, odd.text


# ─────────────────────────────── ٤٥ أقربُ منطقةٍ مزدحمة


def test_the_nearest_busy_cell_skips_the_light_ones() -> None:
    cells = [
        heatmap.Cell(lat=31.96, lng=35.91, requests=3, unserved=0),  # خفيفةٌ (٣ من ١٠) وقريبة — لا تُعدّ
        heatmap.Cell(lat=31.99, lng=35.88, requests=10, unserved=1),  # مرتفعة
        heatmap.Cell(lat=31.90, lng=35.95, requests=6, unserved=0),  # متوسّطة
    ]
    best = busy_area.nearest(cells, lat=31.955, lng=35.91)
    assert best is not None and best.level >= 2
    assert (best.lat, best.lng) in {(31.99, 35.88), (31.90, 35.95)}
    assert best.distance_km == round(best.distance_km, 1) and best.distance_km > 0


def test_no_busy_area_when_everything_is_light_or_below_the_floor() -> None:
    assert busy_area.nearest([heatmap.Cell(lat=31.96, lng=35.91, requests=2, unserved=0)], lat=31.95, lng=35.91) is None
    assert busy_area.nearest([], lat=31.95, lng=35.91) is None


async def test_the_busy_area_door(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    driver = await approved_driver(client, session_factory)
    off = await client.get("/drivers/me/busy-area", headers=driver["headers"])
    assert off.status_code == 200 and off.json() == {"enabled": False, "area": None, "reason": None}

    await enable_features(session_factory, "bubble_busy_area")
    silent = await client.get("/drivers/me/busy-area", headers=driver["headers"])
    assert silent.json()["reason"] == "no_position"

    await bring_online(client, driver)

    async def cells(*_args, **_kwargs):
        return [heatmap.Cell(lat=31.97, lng=35.92, requests=8, unserved=0)]

    async def reverse(*_args, **_kwargs):
        return "الشميساني", "test"

    from app.services import maps

    monkeypatch.setattr(heatmap, "cells", cells)
    monkeypatch.setattr(maps, "reverse", reverse)
    found = await client.get("/drivers/me/busy-area", headers=driver["headers"])
    area = found.json()["area"]
    assert area["lat"] == 31.97 and area["level"] == 3 and area["name"] == "الشميساني" and area["distance_km"] > 0


# ─────────────────────────────── ٥٠ الردودُ السريعة


async def test_quick_replies_are_off_then_the_owners_defaults(client: AsyncClient, session_factory) -> None:
    driver = await approved_driver(client, session_factory)
    off = await client.get("/quick-replies", params={"side": "driver"}, headers=driver["headers"])
    assert off.json() == {"enabled": False, "texts": []}
    await enable_features(session_factory, "quick_replies")
    on = await client.get("/quick-replies", params={"side": "driver"}, headers=driver["headers"])
    assert on.json() == {"enabled": True, "texts": ["أنا في الطريق", "وصلت", "دقيقتين"]}
    rider = await client.get("/quick-replies", params={"side": "rider"}, headers=driver["headers"])
    assert rider.json()["texts"] == ["أنا قادم", "انتظرني دقيقة", "أنا عند المدخل"]


async def test_the_panel_edits_them_and_the_chat_filter_guards_them(
    client: AsyncClient, session_factory, admin_headers: dict[str, str]
) -> None:
    bad = await client.put(
        "/admin/quick-replies/JO", json={"driver_texts": ["اتصل على 0791234567"], "rider_texts": []}, headers=admin_headers
    )
    assert bad.status_code == 422, bad.text
    saved = await client.put(
        "/admin/quick-replies/JO",
        json={"driver_texts": [" أنا قريب ", "أنا قريب", "انتظرني"], "rider_texts": []},
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    # **المكرَّرُ يسقط والمسافاتُ تُقصّ، والفارغُ يعود إلى الافتراض**
    assert saved.json()["driver_texts"] == ["أنا قريب", "انتظرني"]
    assert saved.json()["rider_texts"] == ["أنا قادم", "انتظرني دقيقة", "أنا عند المدخل"]
    await enable_features(session_factory, "quick_replies")
    driver = await approved_driver(client, session_factory)
    mine = await client.get("/quick-replies", params={"side": "driver"}, headers=driver["headers"])
    assert mine.json()["texts"] == ["أنا قريب", "انتظرني"]
