"""تزامنُ «بين المدن» (SPEC §٦٣-ج/٧) — **آخرُ مقعدٍ لراكبين معاً يأخذه واحد**، والقفلُ في `intercity.locked_trip`.

**في ملفِّ تزامنٍ لا في ملفِّ الخدمة** — فيراه `test_locks_have_tests` (سقط في CI)."""

from __future__ import annotations

import asyncio

from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import intercity
from tests.helpers import (
    OTHER_RIDER,
    auth,
    register,
    rider_session,
    topup_wallet,
)
from tests.test_intercity import (  # noqa: F401 — المثبِّتاتُ التلقائيةُ لا تسري إلا حيث يوجد اسمُها
    _service_settings,
    _setup,
    _trip,
)


async def test_seats_are_held_from_the_wallet_and_the_last_seat_goes_to_one_of_two(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    route, driver = await _setup(client, admin_headers, session_factory)
    trip = await _trip(client, route, driver, seats=1)
    first = await rider_session(client)
    second = {"headers": auth(await register(client, OTHER_RIDER))}
    await topup_wallet(client, admin_headers, first["user"]["id"], "20.000")
    me = (await client.get("/auth/me", headers=second["headers"])).json()
    await topup_wallet(client, admin_headers, me["id"], "20.000")

    original = intercity.locked_trip

    async def slow(session, trip_id):
        row = await original(session, trip_id)
        await asyncio.sleep(0.5)
        return row

    monkeypatch.setattr(intercity, "locked_trip", slow)
    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post("/intercity/bookings", json={"trip_id": trip["id"], "seats": 1}, headers=first["headers"]),
            client.post("/intercity/bookings", json={"trip_id": trip["id"], "seats": 1}, headers=second["headers"]),
        ),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    async with session_factory() as session:
        held = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.type == WalletTransactionType.INTERCITY_HOLD
            )
        )
    assert held == Decimal("-6.000")
