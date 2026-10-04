"""§٦١-ي/١١: «الكبتن يقترب» — إشعارٌ للراكب حين يقترب كبتنُه، مرّةً لكلِّ رحلة.

**ما يُقاس هنا شرطُ المالك بحرفه**: يصل حين يقترب ولا يصل وهو بعيد · **مرّةً لكلِّ رحلة** — ولو تكرّر الموقعُ القريب ولو تزامن موقعان ·
**لا شيءَ بعد «وصلتُ»** · **المسافةُ مسافةُ السوق** يضبطها المشرف · لا يُحفظ في صندوق الوارد. **ولا يغيّر التوزيعَ ولا سيرَ الرحلة** —
والمجموعاتُ القائمةُ للتوزيع والرحلات تبقى خضراء.
"""

from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from tests.helpers import (
    RIDER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    broadcast_location,
    enable_push_provider,
    inbox_of,
    pushes_to,
    register,
    register_device,
)

# نقطةُ الانطلاق في المساعد (31.9539, 35.9106) — ونقاطٌ على الخطّ نفسِه بمسافاتٍ معروفة
FAR = (32.0000, 35.9106)  # نحو ٥ كم
NEAR_456 = (31.9580, 35.9106)  # نحو ٤٥٦ م
NEAR_110 = (31.9549, 35.9106)  # نحو ١١١ م


async def _ride(client: AsyncClient, session_factory) -> tuple[dict, dict, dict]:
    await enable_push_provider(session_factory)
    rider = auth(await register(client, RIDER))
    await register_device(client, rider, token="rider-token")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider, driver)
    return rider, driver, ride


async def _approaching(token: str = "rider-token") -> list[dict]:
    return [push for push in await pushes_to(token) if (push.get("data") or {}).get("type") == "driver_approaching"]


async def _notified_at(session_factory, ride_id: str):
    from app.models.ride import Ride

    async with session_factory() as session:
        return await session.scalar(select(Ride.approach_notified_at).where(Ride.id == uuid.UUID(ride_id)))


async def test_a_captain_far_away_sends_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    _, driver, ride = await _ride(client, session_factory)
    await broadcast_location(client, driver, *FAR)
    assert await _approaching() == []
    assert await _notified_at(session_factory, ride["id"]) is None


async def test_a_near_captain_tells_the_rider_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider, driver, ride = await _ride(client, session_factory)
    await broadcast_location(client, driver, *NEAR_456)
    await broadcast_location(client, driver, *NEAR_110)
    await broadcast_location(client, driver, *NEAR_456)

    pushes = await _approaching()
    assert len(pushes) == 1, pushes
    assert pushes[0]["data"]["ride_id"] == ride["id"]
    assert await _notified_at(session_factory, ride["id"]) is not None
    # **لحظةٌ تمضي لا خبرٌ يبقى**: لا صفَّ في صندوق الوارد
    kinds = [row.kind for row in await inbox_of(session_factory, ride["rider_id"])]
    assert "driver_approaching" not in kinds


async def test_two_locations_at_once_send_one_notice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    _, driver, ride = await _ride(client, session_factory)
    await asyncio.wait_for(
        asyncio.gather(
            broadcast_location(client, driver, *NEAR_456),
            broadcast_location(client, driver, *NEAR_110),
            broadcast_location(client, driver, *NEAR_456),
        ),
        timeout=30,
    )
    assert len(await _approaching()) == 1


async def test_nothing_once_the_captain_has_arrived(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    _, driver, ride = await _ride(client, session_factory)
    arrived = await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    assert arrived.status_code == 200, arrived.text
    await broadcast_location(client, driver, *NEAR_110)
    assert await _approaching() == []
    assert await _notified_at(session_factory, ride["id"]) is None


async def test_the_distance_is_the_markets_setting(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    current = (await client.get("/admin/campaigns/settings/JO", headers=admin_headers)).json()
    assert current["approach_notice_meters"] == 800
    saved = await client.put(
        "/admin/campaigns/settings/JO",
        json={
            "quiet_hours_start": current["quiet_hours_start"][:5],
            "quiet_hours_end": current["quiet_hours_end"][:5],
            "timezone": current["timezone"],
            "approach_notice_meters": 300,
        },
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["approach_notice_meters"] == 300

    _, driver, _ride_body = await _ride(client, session_factory)
    await broadcast_location(client, driver, *NEAR_456)  # ٤٥٦ م > ٣٠٠
    assert await _approaching() == []
    await broadcast_location(client, driver, *NEAR_110)  # ١١١ م < ٣٠٠
    assert len(await _approaching()) == 1


async def test_the_setting_is_bounded_and_optional(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    current = (await client.get("/admin/campaigns/settings/JO", headers=admin_headers)).json()
    base = {
        "quiet_hours_start": current["quiet_hours_start"][:5],
        "quiet_hours_end": current["quiet_hours_end"][:5],
        "timezone": current["timezone"],
    }
    for bad in (100, 5000):
        response = await client.put(
            "/admin/campaigns/settings/JO", json=base | {"approach_notice_meters": bad}, headers=admin_headers
        )
        assert response.status_code == 422, response.text
    # **ومن لا يرسله لا يتغيّر عنده شيء** — عقدُ ساعات الهدوء القائمُ كما هو
    unchanged = await client.put("/admin/campaigns/settings/JO", json=base, headers=admin_headers)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["approach_notice_meters"] == current["approach_notice_meters"]
