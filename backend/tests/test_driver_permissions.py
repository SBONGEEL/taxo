"""**بلاغُ مركز الأذونات** (SPEC §١٠٣ المرحلة A/28) — الأساسيّةُ المطفأةُ على هاتف الكبتن تصل درجَه في اللوحة، **ولا تحجب شيئاً**.

يُقاس: البلاغُ يُخزَّن مرتَّباً بلا تكرار ويظهر في صفِّ اللوحة · `[]` غيرُ «لم يُبلَّغ» · مفتاحٌ مجهولٌ يُردّ ولا يُكتب ·
والكبتنُ يبقى يستقبل (البلاغُ لا يمسّ `is_online` ولا الحال) · والراكبُ لا يبلغ الباب.
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


async def test_report_reaches_the_admin_row_sorted_and_unique(client: AsyncClient, session_factory, admin_headers) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    before = await _row(client, admin_headers, driver["driver_id"])
    assert before["permissions_off"] is None and before["permissions_reported_at"] is None

    sent = await client.put(
        "/drivers/me/permissions", headers=driver["headers"], json={"off": ["overlay", "battery", "overlay"], "build": 1200}
    )
    assert sent.status_code == 204, sent.text
    row = await _row(client, admin_headers, driver["driver_id"])
    assert row["permissions_off"] == ["battery", "overlay"]
    assert row["permissions_reported_at"]
    # **قراءةٌ لا قرار**: الحالُ كما كانت
    assert row["status"] == before["status"]


async def test_all_on_is_an_empty_list_not_unreported(client: AsyncClient, session_factory, admin_headers) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await client.put("/drivers/me/permissions", headers=driver["headers"], json={"off": ["location"]})
    sent = await client.put("/drivers/me/permissions", headers=driver["headers"], json={"off": []})
    assert sent.status_code == 204
    row = await _row(client, admin_headers, driver["driver_id"])
    assert row["permissions_off"] == []


async def test_unknown_key_is_refused_and_not_written(client: AsyncClient, session_factory, admin_headers) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    bad = await client.put("/drivers/me/permissions", headers=driver["headers"], json={"off": ["camera_roll_secret"]})
    assert bad.status_code == 422
    row = await _row(client, admin_headers, driver["driver_id"])
    assert row["permissions_off"] is None


async def test_a_rider_cannot_report(client: AsyncClient) -> None:
    from tests.helpers import RIDER, auth, register

    rider = await register(client, RIDER)
    refused = await client.put("/drivers/me/permissions", headers=auth(rider), json={"off": []})
    assert refused.status_code in (403, 404)
