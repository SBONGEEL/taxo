"""تزامنُ المشوار الثابت (SPEC §٦٣-ج/٦) — **اعتمادُ كبتنين معاً يعتمده واحد**، والقفلُ في `commute`.

**في ملفِّ تزامنٍ لا في ملفِّ الخدمة** — فيراه `test_locks_have_tests` (سقط في CI)."""

from __future__ import annotations

import asyncio

from httpx import AsyncClient

from app.services import commute
from tests.helpers import DRIVER, SECOND_DRIVER, approved_driver
from tests.test_rider_subscription import (  # noqa: F401 — المثبِّتاتُ التلقائيةُ لا تسري إلا حيث يوجد اسمُها
    _bought,
    _service_settings,
)


async def test_two_captains_approve_at_once_and_one_wins(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**قفلُ الاشتراك وحدَه يملك هذا** — بتداخلٍ مقصود: الأولُ يتمهّل بعد القراءة."""
    original = commute.locked

    async def slow(session, subscription_id):
        row = await original(session, subscription_id)
        await asyncio.sleep(0.5)
        return row

    monkeypatch.setattr(commute, "locked", slow)
    rider, sub = await _bought(client, admin_headers, session_factory)
    first = await approved_driver(client, session_factory, DRIVER)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-22")
    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/drivers/me/commutes/{sub['id']}/approve", headers=first["headers"]),
            client.post(f"/drivers/me/commutes/{sub['id']}/approve", headers=second["headers"]),
        ),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
