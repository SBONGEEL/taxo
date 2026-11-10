"""**خريطةُ الطلب الحراريّة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٨) — مجمَّعة: لا موضعَ راكبٍ ولا عددَ للكبتن."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import DRIVER, OTHER_RIDER, PICKUP, DROPOFF, approved_driver, auth, register, rider_session

pytestmark = pytest.mark.asyncio


async def _request(client: AsyncClient, headers: dict) -> None:
    made = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}, headers=headers
    )
    assert made.status_code == 201, made.text


async def test_cells_are_aggregated_and_the_captain_sees_levels_only_above_the_floor(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    first = (await rider_session(client))["headers"]
    await _request(client, first)

    # **طلبٌ واحدٌ لا يُرسم للكبتن** — موضعُ راكبٍ واحدٍ بتقريب كيلومتر
    assert (await client.get("/drivers/me/heatmap", headers=driver["headers"])).json() == []
    panel = (await client.get("/admin/heatmap?country_code=JO", headers=admin_headers)).json()
    assert len(panel) == 1 and panel[0]["requests"] == 1
    # **مركزُ الخلية لا موضعُ الطلب**
    assert abs(panel[0]["lat"] - round(PICKUP["lat"], 2)) < 1e-9 and abs(panel[0]["lng"] - round(PICKUP["lng"], 2)) < 1e-9

    second = auth(await register(client, OTHER_RIDER))
    third = auth(await register(client, OTHER_RIDER | {"phone": "0796666666", "name": "راكب ثالث"}))
    await _request(client, second)
    await _request(client, third)
    seen = (await client.get("/drivers/me/heatmap", headers=driver["headers"])).json()
    assert seen == [{"lat": panel[0]["lat"], "lng": panel[0]["lng"], "level": 3}]
    assert "requests" not in seen[0]

    other = (await client.get("/admin/heatmap?country_code=DZ", headers=admin_headers)).json()
    assert other == [], "سوقٌ آخرُ لا يرى طلباتِ هذا"
