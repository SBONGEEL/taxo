"""اشتراكُ الراكب — المشوارُ الثابت (SPEC §٦٣-ج/٦، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

ما يحرسه هذا الملف:

- **مطفأً يُرفض**؛ **والسعرُ «تقديرُ الطريق × (١ − الخصم)» مجمَّداً**، والمجموعُ من المحفظة مقدّماً، **ورصيدٌ لا يكفي يُرفض**.
- **التوليدُ يتكرّر بلا أن يُكرِّر**، **والتعليقُ لا يولّد ويُرحِّل**، بحدٍّ من اللوحة.
- **الكبتنُ المعتمدُ يأخذ رحلةَ اليوم مباشرةً**، **والرحلةُ تُدفع من المحفوظ** — فلا يدفع الراكبُ عند الوصول.
- **ما لم يُستعمل يعود رصيداً لا نقداً** — عند الإلغاء وعند النهاية، **مرّةً واحدة**.
- **كبتنان يعتمدان معاً ⇒ واحد.**
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.booking import RideBooking
from app.models.enums import CountryCode, FeatureKey, WalletTransactionType
from app.models.rider_subscription import RiderSubscription
from app.models.service_setting import ServiceSetting
from app.models.wallet import WalletTransaction
from app.services import bookings, commute
from app.services.stats import country_today
from tests.helpers import (
    DRIVER,
    DROPOFF,
    EXPECTED_FARE,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    payments_of,
    rider_session,
    topup_wallet,
    wallet_of,
)

FLAG = FeatureKey.RIDER_SUBSCRIPTION_ENABLED.value
BOOKINGS = FeatureKey.SCHEDULED_RIDES_ENABLED.value
PER_RIDE = (Decimal(EXPECTED_FARE) * Decimal("0.9")).quantize(Decimal("0.001"))


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", commute_discount_percent=Decimal("10.00")), ServiceSetting(country_code="LY")]
        )
        await session.commit()


async def _tomorrow(session_factory) -> date:
    async with session_factory() as session:
        return await country_today(session, CountryCode.JO) + timedelta(days=1)


async def _plan(session_factory, *, back: bool = True) -> dict:
    return {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "weekdays": 127,
        "go_time": "07:30:00",
        "return_time": "16:00:00" if back else None,
        "starts_on": (await _tomorrow(session_factory)).isoformat(),
    }


async def _bought(client, admin_headers, session_factory, *, balance: str = "600.000") -> tuple[dict, dict]:
    await enable_features(session_factory, FLAG, BOOKINGS)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], balance)
    bought = await client.post("/me/commutes", json=await _plan(session_factory), headers=rider["headers"])
    assert bought.status_code == 201, bought.text
    return rider, bought.json()


async def test_switched_off_the_commute_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await rider_session(client)
    refused = await client.post("/me/commutes/quote", json=await _plan(session_factory), headers=rider["headers"])
    assert refused.status_code == 403 and refused.json()["code"] == "rider_subscription_unavailable"


async def test_the_price_is_the_route_estimate_less_the_discount_and_is_paid_up_front(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await rider_session(client)
    quote = await client.post("/me/commutes/quote", json=await _plan(session_factory), headers=rider["headers"])
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert Decimal(body["price_per_ride"]) == PER_RIDE
    assert Decimal(body["total"]) == PER_RIDE * body["rides_total"]

    short = await client.post("/me/commutes", json=await _plan(session_factory), headers=rider["headers"])
    assert short.status_code == 409 and short.json()["code"] == "insufficient_balance"

    await topup_wallet(client, admin_headers, rider["user"]["id"], "600.000")
    bought = await client.post("/me/commutes", json=await _plan(session_factory), headers=rider["headers"])
    assert bought.status_code == 201, bought.text
    left = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    assert left == Decimal("600.000") - Decimal(body["total"])


async def test_generation_repeats_without_duplicating_and_a_suspended_day_is_skipped_and_carried(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, sub = await _bought(client, admin_headers, session_factory)
    first = date.fromisoformat(sub["starts_on"])
    async with session_factory() as session:
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        assert await commute.generate_for(session, row, first) == 2
        assert await commute.generate_for(session, row, first) == 0
        await session.commit()

    second = first + timedelta(days=1)
    suspended = await client.post(
        f"/me/commutes/{sub['id']}/suspend", json={"day": second.isoformat()}, headers=rider["headers"]
    )
    assert suspended.status_code == 200, suspended.text
    assert date.fromisoformat(suspended.json()["ends_on"]) == date.fromisoformat(sub["ends_on"]) + timedelta(days=1)
    async with session_factory() as session:
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        assert await commute.generate_for(session, row, second) == 0


async def test_the_approved_captain_takes_the_day_ride_and_it_is_paid_from_the_prepaid_money(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, sub = await _bought(client, admin_headers, session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    offers = await client.get("/drivers/me/commute-offers", headers=driver["headers"])
    assert [row["id"] for row in offers.json()] == [sub["id"]]
    approved = await client.post(f"/drivers/me/commutes/{sub['id']}/approve", headers=driver["headers"])
    assert approved.status_code == 200, approved.text

    async with session_factory() as session:
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        await commute.generate_for(session, row, date.fromisoformat(sub["starts_on"]))
        go = await session.scalar(select(RideBooking).where(RideBooking.commute_id == row.id).order_by(RideBooking.scheduled_at))
        go.scheduled_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.commit()
    async with session_factory() as session:
        await bookings.run_due(session, get_redis_client())
    async with session_factory() as session:
        go = await session.scalar(
            select(RideBooking).where(RideBooking.commute_id == uuid.UUID(sub["id"]), RideBooking.ride_id.is_not(None))
        )
        ride_id = str(go.ride_id)
    seen = (await client.get(f"/rides/{ride_id}", headers=driver["headers"])).json()
    assert seen["status"] == "accepted" and seen["commute"] is True
    assert Decimal(seen["estimated_fare"]) == PER_RIDE

    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    assert Decimal(done.json()["final_fare"]) == PER_RIDE
    payments = (await payments_of(client, rider["headers"], ride_id))["payments"]
    assert [(p["method"], p["status"]) for p in payments] == [("commute", "confirmed")]


async def test_cancelling_credits_every_unused_ride_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, sub = await _bought(client, admin_headers, session_factory)
    before = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    cancelled = await client.post(f"/me/commutes/{sub['id']}/cancel", headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    after = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    assert after - before == Decimal(sub["amount_paid"])
    again = await client.post(f"/me/commutes/{sub['id']}/cancel", headers=rider["headers"])
    assert again.status_code == 404
    async with session_factory() as session:
        credits = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.type == WalletTransactionType.COMMUTE_CREDIT
            )
        )
    assert credits == 1


async def test_the_month_end_settles_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    rider, sub = await _bought(client, admin_headers, session_factory)
    async with session_factory() as session:
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        row.starts_on = row.starts_on - timedelta(days=40)
        row.ends_on = row.starts_on + timedelta(days=5)
        await session.commit()
    async with session_factory() as session:
        assert (await commute.run_daily(session))["settled"] == 1
    async with session_factory() as session:
        assert (await commute.run_daily(session))["settled"] == 0
        row = await session.get(RiderSubscription, uuid.UUID(sub["id"]))
        assert row.status == "ended" and row.settled_at is not None
