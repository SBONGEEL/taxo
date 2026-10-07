"""الطرد (SPEC §٦٣-ج/٤، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

ما يحرسه هذا الملف:

- **مطفأً يُرفض**، **وبلا إقرارٍ بالشروط يُرفض**، **وبغير الاقتصادي يُرفض**.
- **رسمُه سطرٌ داخل الأجرة** في التقدير والرحلة، **والشروطُ من الخلفية**.
- **المستلمُ يُرى بعد القبول وحدَه**، **ويُمحى بعد ٣٠ يوماً**.
- **المستلمُ نقداً ⇒ دفعةٌ يفتحها الإنهاء**؛ **والمرسلُ ⇒ أيُّ قناة**؛ **والعمولةُ على الأجرة دون الرسم**.
- **رفضُ الكبتن عند الاستلام في «وصل» وحدَه، بلا مالٍ على أحد.**
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cancellation import RideCancellationCharge
from app.models.enums import FeatureKey, WalletTransactionType
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.models.wallet import WalletTransaction
from app.services import ride_for_other
from tests.helpers import (
    DRIVER,
    DROPOFF,
    EXPECTED_FARE,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    payments_of,
    pay_ride,
    rider_session,
    set_commission,
    wait_for_offer,
)

FLAG = FeatureKey.PARCEL_ENABLED.value
FEE = Decimal("0.500")
RECIPIENT = {"recipient_name": "أبو سالم", "recipient_phone": "0792223333", "recipient_address": "جبل الحسين، بناية ٤"}


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    """**صفُّ الإعدادات كما تبذره الترحيلتان `0092` و`0093`** — والاختباراتُ تفرّغ الجداولَ قبل كلٍّ منها."""
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO", parcel_fee=FEE), ServiceSetting(country_code="LY")])
        await session.commit()


def _body(payer: str = "requester", *, terms: bool = True, category: str = "economy") -> dict:
    return {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "vehicle_category": category,
        "parcel": RECIPIENT | {"payer": payer, "accepted_terms": terms},
    }


async def _accepted(client: AsyncClient, rider: dict, driver: dict, payer: str = "requester") -> dict:
    created = await client.post("/rides", json=_body(payer), headers=rider)
    assert created.status_code == 201, created.text
    ride = created.json()
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            return accepted.json()
        if accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


async def _captain(client, session_factory) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    return driver


async def test_switched_off_without_terms_or_beyond_economy_a_parcel_is_refused(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = (await rider_session(client))["headers"]
    off = await client.post("/rides", json=_body(), headers=rider)
    assert off.status_code == 403 and off.json()["code"] == "parcel_unavailable"

    await enable_features(session_factory, FLAG)
    no_terms = await client.post("/rides", json=_body(terms=False), headers=rider)
    assert no_terms.status_code == 422 and no_terms.json()["code"] == "invalid_input"
    comfort = await client.post("/rides", json=_body(category="comfort"), headers=rider)
    assert comfort.status_code == 422
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Ride)) == 0


async def test_the_fee_is_its_own_line_and_the_terms_come_from_the_backend(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    quote = await client.post(
        "/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF, "is_parcel": True}, headers=rider
    )
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert body["parcel_fee"] == "0.500"
    assert Decimal(body["estimated_fare"]) == Decimal(EXPECTED_FARE) + FEE
    assert len(body["parcel_terms"]) == 4 and "النقود" in body["parcel_terms"][0]
    plain = (await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider)).json()
    assert plain["parcel_fee"] is None and plain["parcel_terms"] is None


async def test_the_captain_sees_the_recipient_only_after_accepting_and_it_is_erased_after_thirty_days(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    assert ride["ride_type"] == "parcel"
    assert ride["recipient_name"] == "أبو سالم" and ride["recipient_phone"] == "+962792223333"
    lines = {line["kind"]: line["amount"] for line in ride["fare_lines"]}
    assert lines["parcel_fee"] == "0.500"

    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    assert done.json()["recipient_name"] is None

    async with session_factory() as session:
        ended = (await session.get(Ride, uuid.UUID(ride["id"]))).completed_at
        assert await ride_for_other.purge_passengers(session, now=ended + timedelta(days=31)) == 1
        await session.commit()
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        assert row.recipient_name is None and row.recipient_phone is None and row.recipient_address is None
        assert row.ride_type == "parcel" and row.passenger_erased_at is not None


async def test_the_recipient_pays_cash_through_a_payment_the_completion_opens(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver, payer="recipient_cash")
    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
    payments = (await payments_of(client, rider, ride["id"]))["payments"]
    assert [(p["method"], p["status"], p["amount"]) for p in payments] == [("cash", "pending", done.json()["final_fare"])]
    assert (await pay_ride(client, rider, ride["id"], "wallet")).status_code == 409


async def test_the_sender_may_pay_cash_and_the_commission_skips_the_fee(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**المرسلُ عند الالتقاط فيدفع نقداً إن شاء**، **والعمولةُ على الأجرة دون رسم الطرد** — دَينُ النقد بقدرها."""
    from app.models.debt import DriverDebt

    await set_commission(session_factory, "10.00")
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    for step in ("arrive", "start", "complete"):
        await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
    opened = await pay_ride(client, rider, ride["id"], "cash", key="parcel-cash-1")
    assert opened.status_code == 201, opened.text
    payment_id = opened.json()["payments"][0]["id"] if "payments" in opened.json() else opened.json()[0]["id"]
    confirmed = await client.post(f"/payments/{payment_id}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text
    async with session_factory() as session:
        debt = await session.scalar(select(func.coalesce(func.sum(DriverDebt.amount), 0)))
    # ١٠٪ من ٨٫٠٠٠ لا من ٨٫٥٠٠
    assert debt == Decimal("0.800")


async def test_the_captain_refuses_a_parcel_only_on_arrival_and_nobody_pays(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory)
    rider = (await rider_session(client))["headers"]
    ride = await _accepted(client, rider, driver)
    early = await client.post(f"/rides/{ride['id']}/parcel-refuse", headers=driver["headers"])
    assert early.status_code == 409
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    refused = await client.post(f"/rides/{ride['id']}/parcel-refuse", headers=driver["headers"])
    assert refused.status_code == 200, refused.text
    assert refused.json()["status"] == "cancelled_by_driver"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(RideCancellationCharge)) == 0
        assert await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.type == WalletTransactionType.CANCELLATION_FEE
            )
        ) == 0
