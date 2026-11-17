"""**إشاراتُ الجهاز** (SPEC §١٠٣ B/17 و25) — موقعٌ مزيَّفٌ وجهازٌ معدَّلٌ يصلان درجَ الكبتن في اللوحة، **ولا يحجبان شيئاً**.

يُقاس: المقيسُ وحدَه يُكتب (مفتاحٌ غائبٌ «لم يُقس») · بلا شيءٍ مقيسٍ ٤٢٢ ولا كتابة · مفتاحٌ مجهولٌ يُردّ ·
والحالُ كما كانت (بلاغٌ لا قرار) · والراكبُ لا يبلغ الباب.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import DRIVER, approved_driver

pytestmark = pytest.mark.asyncio


async def _row(client: AsyncClient, admin_headers: dict, driver_id) -> dict:
    listed = await client.get("/admin/drivers", headers=admin_headers, params={"limit": 200})
    assert listed.status_code == 200, listed.text
    return next(row for row in listed.json() if row["driver_id"] == str(driver_id))


async def test_measured_signals_reach_the_admin_row_and_block_nothing(client: AsyncClient, session_factory, admin_headers) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    before = await _row(client, admin_headers, driver["driver_id"])
    assert before["device_signals"] is None and before["device_signals_at"] is None

    sent = await client.put("/drivers/me/device-signals", headers=driver["headers"], json={"mock_location": True})
    assert sent.status_code == 204, sent.text
    row = await _row(client, admin_headers, driver["driver_id"])
    # **«rooted» لم يُقس فلا يُكتب** — غيابُه غيرُ «لا»
    assert row["device_signals"] == {"mock_location": True}
    assert row["device_signals_at"]
    assert row["status"] == before["status"]

    both = await client.put(
        "/drivers/me/device-signals", headers=driver["headers"], json={"mock_location": False, "rooted": True}
    )
    assert both.status_code == 204
    assert (await _row(client, admin_headers, driver["driver_id"]))["device_signals"] == {"mock_location": False, "rooted": True}


async def test_nothing_measured_is_refused_and_not_written(client: AsyncClient, session_factory, admin_headers) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    empty = await client.put("/drivers/me/device-signals", headers=driver["headers"], json={})
    assert empty.status_code == 422
    unknown = await client.put("/drivers/me/device-signals", headers=driver["headers"], json={"jailbreak": True})
    assert unknown.status_code == 422
    assert (await _row(client, admin_headers, driver["driver_id"]))["device_signals"] is None


async def test_a_rider_cannot_report_signals(client: AsyncClient) -> None:
    from tests.helpers import RIDER, auth, register

    rider = await register(client, RIDER)
    refused = await client.put("/drivers/me/device-signals", headers=auth(rider), json={"rooted": False})
    assert refused.status_code in (401, 403, 404)
