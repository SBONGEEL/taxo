"""بالساعة (SPEC §٦٣-ج/٥، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأةٌ لكلِّ سوقٍ حتى يُشعلها المالك**.

ما يحرسه هذا الملف:

- **مطفأةً تُرفض**، وبغير الاقتصادي أو بساعاتٍ فوق السقف تُرفض.
- **سعرُها ساعاتٌ لا طريق** — «الساعات × السعر» في التقدير والرحلة سطراً `hourly`.
- **المحجوزُ عند البدء**: من المحفظة يُسوّى فوراً، **ورصيدٌ لا يكفي يرفض البدء** حتى يبدّل الراكبُ إلى النقد؛ ونقداً دفعةٌ معلَّقة.
- **وبدءان معاً يدفعان مرّةً واحدة** (قفلُ البدء لرحلة الساعة).
- **وما زاد من الوقت يُحسب بالدقيقة** عند الإنهاء، **والباقي وحدَه يُطلب**.
- **وإلغاءُ الراكب بعد الوصول: نصفُ ساعةٍ من سعرها.**
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import FeatureKey, WalletTransactionType
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    payments_of,
    rider_session,
    topup_wallet,
    wait_for_offer,
)

FLAG = FeatureKey.HOURLY_ENABLED.value
RATE = Decimal("8.000")


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO", hourly_rate=RATE), ServiceSetting(country_code="LY")])
        await session.commit()


def _body(hours: int = 2, prepay: str = "wallet", category: str = "economy") -> dict:
    return {"pickup": PICKUP, "dropoff": PICKUP, "vehicle_category": category, "hourly": {"hours": hours, "prepay": prepay}}


async def _arrived(client, rider: dict, driver: dict, **kw) -> dict:
    created = await client.post("/rides", json=_body(**kw), headers=rider)
    assert created.status_code == 201, created.text
    ride = created.json()
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            break
        if accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text
    arrived = await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    assert arrived.status_code == 200, arrived.text
    return arrived.json()


async def _captain(client, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    return driver


async def test_switched_off_beyond_economy_or_past_the_cap_an_hourly_ride_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = (await rider_session(client))["headers"]
    off = await client.post("/rides", json=_body(), headers=rider)
    assert off.status_code == 403 and off.json()["code"] == "hourly_unavailable"
    await enable_features(session_factory, FLAG)
    assert (await client.post("/rides", json=_body(category="comfort"), headers=rider)).status_code == 422
    assert (await client.post("/rides", json=_body(hours=9), headers=rider)).status_code == 422


async def test_the_price_is_hours_times_the_rate_in_estimate_and_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    quote = await client.post(
        "/rides/estimate", json={"pickup": PICKUP, "dropoff": PICKUP, "hourly_hours": 3}, headers=rider
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["estimated_fare"] == "24.000"
    assert quote.json()["hourly_rate"] == "8.000" and quote.json()["hourly_km_per_hour"] == 15
    created = (await client.post("/rides", json=_body(hours=3), headers=rider)).json()
    assert created["ride_type"] == "hourly" and created["estimated_fare"] == "24.000"
    assert created["hourly_included_km"] == 45
    assert [line["kind"] for line in created["fare_lines"]] == ["hourly"]


async def test_wallet_prepay_settles_at_start_and_a_short_wallet_blocks_the_start_until_cash(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "5.000")
    ride = await _arrived(client, session["headers"], driver)

    short = await client.post(f"/rides/{ride['id']}/start", headers=driver["headers"])
    assert short.status_code == 409 and short.json()["code"] == "insufficient_balance"
    switched = await client.patch(
        f"/rides/{ride['id']}/hourly-prepay", json={"prepay": "cash"}, headers=session["headers"]
    )
    assert switched.status_code == 200, switched.text
    started = await client.post(f"/rides/{ride['id']}/start", headers=driver["headers"])
    assert started.status_code == 200, started.text
    payments = (await payments_of(client, session["headers"], ride["id"]))["payments"]
    assert [(p["method"], p["status"], p["amount"]) for p in payments] == [("cash", "pending", "16.000")]


async def test_wallet_prepay_is_taken_once_even_when_started_twice_at_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "50.000")
    ride = await _arrived(client, session["headers"], driver)
    responses = await asyncio.wait_for(
        asyncio.gather(*(client.post(f"/rides/{ride['id']}/start", headers=driver["headers"]) for _ in range(2))),
        timeout=20,
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    async with session_factory() as db:
        paid = await db.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride["id"]),
                WalletTransaction.type == WalletTransactionType.RIDE_PAYMENT,
            )
        )
    assert paid == Decimal("-16.000")


async def test_extra_time_is_charged_at_completion_and_only_the_remainder_is_owed(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "50.000")
    ride = await _arrived(client, session["headers"], driver, hours=1)
    assert (await client.post(f"/rides/{ride['id']}/start", headers=driver["headers"])).status_code == 200
    # ساعةٌ وعشرُ دقائق
    async with session_factory() as db:
        row = await db.get(Ride, uuid.UUID(ride["id"]))
        row.started_at = datetime.now(UTC) - timedelta(minutes=70)
        await db.commit()
    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    lines = {line["kind"]: line for line in done.json()["fare_lines"]}
    assert lines["hourly"]["amount"] == "8.000"
    assert "hourly_extra_time" in lines and Decimal(lines["hourly_extra_time"]["quantity"]) >= 10
    final = Decimal(done.json()["final_fare"])
    assert final > Decimal("8.000")
    async with session_factory() as db:
        covered = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.ride_id == uuid.UUID(ride["id"]))
        )
    assert covered == Decimal("8.000")


async def test_cancelling_after_arrival_costs_half_an_hour(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "20.000")
    ride = await _arrived(client, session["headers"], driver)
    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel", json={"reason": "غيّرت رأيي"}, headers=session["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancellation_fee"] == "4.000"
