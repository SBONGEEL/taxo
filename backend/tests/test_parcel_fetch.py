"""«أحضر غرضي» (SPEC §٧٢-ج/١، أمرُ المالك ٢٠٢٦-١٠-١٠) — **الطردُ معكوساً، بمفتاحه ورسمه**.

ما يحرسه هذا الملف:

- **مفتاحُه مستقلٌّ**: مطفأً يُرفض ولو اشتعل الطرد، ومشتعلاً يُقبل ولو أُطفئ الطرد.
- **يدفعه صاحبُه وحدَه**، **ووصفُ الغرض شرط** — وما يخالف يُرفض ولا تُنشأ رحلة.
- **رسمُه هو** في التقدير والرحلة (سطرُ الطرد نفسُه برقمه).
- **من يسلّم الغرضَ ووصفُه يُريان بعد القبول وحدَه، ويُمحيان بعد ٣٠ يوماً.**
- **إشعارُ الراكب عند الاستلام وعند التسليم** بلغة الغرض.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import FeatureKey
from app.models.ride import Ride
from app.models.service_setting import ServiceSetting
from app.services import ride_for_other
from tests.helpers import (
    DRIVER,
    DROPOFF,
    EXPECTED_FARE,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    inbox_of,
    rider_session,
    wait_for_offer,
)

FETCH = FeatureKey.PARCEL_FETCH_ENABLED.value
PARCEL = FeatureKey.PARCEL_ENABLED.value
#: **رسمان مختلفان عمداً** — فيُعرف أيُّهما حُسب
PARCEL_FEE = Decimal("0.500")
FETCH_FEE = Decimal("0.750")
HANDOVER = {"recipient_name": "أم خالد", "recipient_phone": "0791234567", "recipient_address": "الصويفية، عمارة ١٢"}
ITEM = "شاحن هاتف أبيض على طاولة المدخل"


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                ServiceSetting(country_code="JO", parcel_fee=PARCEL_FEE, parcel_fetch_fee=FETCH_FEE),
                ServiceSetting(country_code="LY"),
            ]
        )
        await session.commit()


def _body(*, payer: str = "requester", item: str | None = ITEM, fetch: bool = True) -> dict:
    parcel = HANDOVER | {"payer": payer, "accepted_terms": True, "fetch": fetch}
    if item is not None:
        parcel["item"] = item
    return {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", "parcel": parcel}


async def _rides(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(Ride))


async def test_its_own_switch_decides_and_only_its_owner_pays_for_a_described_item(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = (await rider_session(client))["headers"]
    # **الطردُ مشتعلٌ لا يفتحه**
    await enable_features(session_factory, PARCEL)
    off = await client.post("/rides", json=_body(), headers=rider)
    assert off.status_code == 403 and off.json()["code"] == "parcel_fetch_unavailable"

    await enable_features(session_factory, FETCH)
    cash_by_other = await client.post("/rides", json=_body(payer="recipient_cash"), headers=rider)
    assert cash_by_other.status_code == 422 and cash_by_other.json()["code"] == "invalid_input"
    no_item = await client.post("/rides", json=_body(item=None), headers=rider)
    assert no_item.status_code == 422 and "الغرض" in no_item.json()["message"]
    assert await _rides(session_factory) == 0

    created = await client.post("/rides", json=_body(), headers=rider)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["ride_type"] == "parcel" and body["parcel_fetch"] is True and body["payer"] == "requester"
    # **ولا يُرى من يسلّم الغرضَ ولا وصفُه قبل القبول**
    assert body["recipient_name"] is None and body["parcel_item"] is None


async def test_the_fetch_fee_is_its_own_and_the_parcel_switch_is_not_needed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FETCH)
    rider = (await rider_session(client))["headers"]
    quote = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "is_parcel": True, "parcel_fetch": True},
        headers=rider,
    )
    assert quote.status_code == 200, quote.text
    body = quote.json()
    assert body["parcel_fee"] == "0.750"
    assert Decimal(body["estimated_fare"]) == Decimal(EXPECTED_FARE) + FETCH_FEE
    assert len(body["parcel_terms"]) == 4
    # **والطردُ المطفأُ لا رسمَ له** — المفتاحان مستقلّان
    plain_parcel = (
        await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF, "is_parcel": True}, headers=rider)
    ).json()
    assert plain_parcel["parcel_fee"] is None
    refused = await client.post("/rides", json=_body(fetch=False), headers=rider)
    assert refused.status_code == 403 and refused.json()["code"] == "parcel_unavailable"


async def test_the_captain_sees_the_handover_after_accepting_the_rider_hears_pickup_and_delivery_and_it_is_erased(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FETCH)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    session = await rider_session(client)
    rider = session["headers"]
    created = await client.post("/rides", json=_body(), headers=rider)
    assert created.status_code == 201, created.text
    ride = created.json()
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200 or accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text
    seen = accepted.json()
    assert seen["parcel_fetch"] is True
    assert seen["recipient_name"] == "أم خالد" and seen["recipient_phone"] == "+962791234567"
    assert seen["parcel_item"] == ITEM
    lines = {line["kind"]: line["amount"] for line in seen["fare_lines"]}
    assert lines["parcel_fee"] == "0.750"

    for step in ("arrive", "start", "complete"):
        done = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
        assert done.status_code == 200, done.text
    assert done.json()["parcel_item"] is None and done.json()["recipient_name"] is None

    titles = [row.title for row in await inbox_of(session_factory, session["user"]["id"])]
    assert "استلم الكبتن غرضك" in titles and "وصل غرضك" in titles
    assert "بدأت الرحلة" not in titles

    async with session_factory() as db:
        ended = (await db.get(Ride, uuid.UUID(ride["id"]))).completed_at
        assert await ride_for_other.purge_passengers(db, now=ended + timedelta(days=31)) == 1
        await db.commit()
    async with session_factory() as db:
        row = await db.get(Ride, uuid.UUID(ride["id"]))
        assert row.parcel_item is None and row.recipient_name is None and row.recipient_phone is None
        assert row.parcel_fetch is True and row.passenger_erased_at is not None
