"""تزامنُ الحجز المضمون (SPEC §٦٣-ج/٣) — **قبولُ كبتنين معاً يقبله واحد**، والقفلُ في `guarantees._locked`.

**في ملفِّ تزامنٍ لا في ملفِّ الخدمة** — فيراه `test_locks_have_tests` (كان في `test_guaranteed_booking.py` فسقط الحارسُ في CI)."""

from __future__ import annotations

import asyncio

from httpx import AsyncClient

from app.services import guarantees
from tests.helpers import SECOND_DRIVER, approved_driver
from tests.test_guaranteed_booking import (  # noqa: F401 — المثبِّتاتُ التلقائيةُ لا تسري إلا حيث يوجد اسمُها
    _book,
    _service_settings,
    _setup,
)


async def test_two_captains_accept_at_once_and_one_wins(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**القفلُ وحدَه يملك هذا** — وتداخلٌ مقصود: الأولُ يتمهّل بعد قراءة الحجز فيبدأ الثاني والأولُ ممسكٌ به. **وبحذف القفل يقبلانه معاً**
    (قِيس: كان يمرّ بلا القفل قبل التمهّل — الطلبان لم يتداخلا أصلاً، فلم يكن يقيس شيئاً)."""
    original = guarantees._locked

    async def slow_locked(session, booking_id):
        row = await original(session, booking_id)
        await asyncio.sleep(0.5)
        return row

    monkeypatch.setattr(guarantees, "_locked", slow_locked)
    rider, first = await _setup(client, admin_headers, session_factory)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-22")
    booking = (await _book(client, rider)).json()

    offers = await client.get("/drivers/me/guarantee-offers", headers=first["headers"])
    assert [row["id"] for row in offers.json()] == [booking["id"]]

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=first["headers"]),
            client.post(f"/drivers/me/guarantees/{booking['id']}/accept", headers=second["headers"]),
        ),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["code"] == "guarantee_taken"
