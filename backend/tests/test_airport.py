"""المطار (SPEC §٦٣-ج/٢، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

ما يحرسه هذا الملف:

- **مطفأً لا رسم** ولو بدأت الرحلةُ في المطار؛ ومشتعلاً **الرسمُ سطرٌ مستقلٌّ في التقدير والرحلة، داخلَ الأجرة**.
- **لا يصلها إلا كبتنٌ أشعل «طلبات المطار»** — مطفأةٌ حتى يُشعلها هو.
- **الرسمُ للكبتن كاملاً بلا عمولة**: العمولةُ على الأجرة دون الرسم، **والخصمُ كذلك**.
- **مرفقٌ رسمُه صفرٌ أو مطفأٌ لا يُطبَّق** — ومعيتيقة صفرٌ حتى يضبطه المالك.
- **واللوحة**: إضافةٌ وتعديلٌ وتدقيق، ومضلّعٌ يتقاطع يُرفض، ولا حذف.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import FeatureKey, WalletTransactionType
from app.models.facility import Facility
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    set_commission,
    topup_wallet,
    wait_for_offer,
)

FLAG = FeatureKey.AIRPORT_ENABLED.value
#: داخل مضلّع الملكة علياء المبذور (35.965–36.010 × 31.700–31.745)
AIRPORT = {"lat": 31.7226, "lng": 35.9932}
CITY = {"lat": 31.9539, "lng": 35.9106}
NEAR_AIRPORT = {"lat": 31.7300, "lng": 35.9932}
#: **خارج المضلّع بقليل** (شماله) — قريبٌ من الكبتن فيُعرض عليه، ولا رسمَ عليه
OUTSIDE = {"lat": 31.7500, "lng": 35.9932}
FEE = "1.000"

#: **مطارا الإطلاق كما تبذرهما الترحيلة `0091`** — والاختباراتُ تفرّغ الجداولَ قبل كلٍّ منها، فتعيدهما بالمضلّعين نفسيهما
QUEEN_ALIA = "SRID=4326;POLYGON((35.965 31.700, 36.010 31.700, 36.010 31.745, 35.965 31.745, 35.965 31.700))"
MITIGA = "SRID=4326;POLYGON((13.262 32.884, 13.296 32.884, 13.296 32.902, 13.262 32.902, 13.262 32.884))"


@pytest.fixture(autouse=True)
async def _launch_airports(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all(
            [
                Facility(country_code="JO", name="مطار الملكة علياء الدولي", area=QUEEN_ALIA, fee=Decimal(FEE)),
                Facility(country_code="LY", name="مطار معيتيقة الدولي", area=MITIGA, fee=Decimal("0.000")),
            ]
        )
        await session.commit()


def _body(pickup=AIRPORT, dropoff=CITY) -> dict:
    return {"pickup": pickup, "dropoff": dropoff, "vehicle_category": "economy"}


async def _captain(client, session_factory, *, airport: bool) -> dict:
    driver = await approved_driver(client, session_factory, DRIVER)
    if airport:
        response = await client.patch("/drivers/me", json={"accepts_airport": True}, headers=driver["headers"])
        assert response.status_code == 200, response.text
        assert response.json()["accepts_airport"] is True
    await bring_online(client, driver, NEAR_AIRPORT)
    return driver


async def test_switched_off_there_is_no_fee_even_at_the_airport(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = (await rider_session(client))["headers"]
    quote = await client.post("/rides/estimate", json=_body(), headers=rider)
    assert quote.status_code == 200, quote.text
    assert quote.json()["estimated_fare"] == EXPECTED_FARE
    assert quote.json()["airport_fee"] is None


async def test_the_fee_is_its_own_line_inside_the_fare_in_estimate_and_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    await _captain(client, session_factory, airport=True)
    rider = (await rider_session(client))["headers"]

    quote = (await client.post("/rides/estimate", json=_body(), headers=rider)).json()
    assert quote["airport_fee"] == FEE
    assert Decimal(quote["estimated_fare"]) == Decimal(EXPECTED_FARE) + Decimal(FEE)

    # **ومن الوجهة أيضاً**: رحلةٌ تنتهي في المطار تحمله كما تحمله التي تبدأ فيه
    back = (await client.post("/rides/estimate", json=_body(CITY, AIRPORT), headers=rider)).json()
    assert back["airport_fee"] == FEE

    created = await client.post("/rides", json=_body(), headers=rider)
    assert created.status_code == 201, created.text
    ride = created.json()
    assert ride["airport"] is True
    assert ride["estimated_fare"] == quote["estimated_fare"]
    lines = {line["kind"]: line["amount"] for line in ride["fare_lines"]}
    assert lines["airport_fee"] == FEE
    assert sum(Decimal(v) for v in lines.values()) == Decimal(ride["estimated_fare"])


async def test_only_a_captain_who_switched_airport_on_gets_the_offer(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**مطفأةٌ حتى يُشعلها الكبتنُ بنفسه** — ومن لم يُشعلها لا يُعرض عليه طلبُ مطار، ويُعرض عليه غيرُه كما كان."""
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory, airport=False)
    rider = (await rider_session(client))["headers"]

    ride = (await client.post("/rides", json=_body(), headers=rider)).json()
    await asyncio.sleep(3)
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        assert row.driver_id is None
    await client.post(f"/rides/{ride['id']}/cancel", json={"reason": "تجربة"}, headers=rider)

    city = (await client.post("/rides", json=_body(OUTSIDE, CITY), headers=rider)).json()
    assert city["airport"] is False
    await wait_for_offer(city["id"], driver["driver_id"])


async def _airport_ride_paid_by_wallet(client, admin_headers, session_factory) -> tuple[dict, dict]:
    # المحفظةُ مشتعلةٌ من `jordan_wallet` — وإشعالُها ثانيةً يصطدم بصفّها
    await enable_features(session_factory, FLAG)
    driver = await _captain(client, session_factory, airport=True)
    session = await rider_session(client)
    await topup_wallet(client, admin_headers, session["user"]["id"], "50.000")
    ride = (await client.post("/rides", json=_body(), headers=session["headers"])).json()
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            break
    for step in ("arrive", "start", "complete"):
        response = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
        assert response.status_code == 200, response.text
    return response.json(), session


async def test_the_fee_reaches_the_captain_whole_and_commission_is_on_the_fare_alone(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**«للكبتن» = كاملاً بلا عمولة** (§٦٣-ب، السؤال ١): نسبةُ السوق على الأجرة دون الرسم، والرسمُ يصله كلُّه."""
    await set_commission(session_factory, "10.00")
    done, rider = await _airport_ride_paid_by_wallet(client, admin_headers, session_factory)
    assert Decimal(done["final_fare"]) == Decimal(EXPECTED_FARE) + Decimal(FEE)
    paid = await client.post(
        f"/rides/{done['id']}/payments",
        json={"method": "wallet", "idempotency_key": "airport-pay-1"},
        headers=rider["headers"],
    )
    assert paid.status_code == 201, paid.text
    async with session_factory() as session:
        commission = await session.scalar(
            select(func.sum(WalletTransaction.amount)).where(
                WalletTransaction.ride_id == uuid.UUID(done["id"]),
                WalletTransaction.type == WalletTransactionType.COMMISSION,
            )
        )
    # ١٠٪ من ٨٫٠٠٠ لا من ٩٫٠٠٠
    assert commission == Decimal("-0.800")


async def test_two_wallet_payments_at_once_pay_an_airport_ride_once(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    await set_commission(session_factory, "10.00")
    done, rider = await _airport_ride_paid_by_wallet(client, admin_headers, session_factory)
    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    f"/rides/{done['id']}/payments",
                    json={"method": "wallet", "idempotency_key": f"airport-pay-{i}"},
                    headers=rider["headers"],
                )
                for i in range(3)
            )
        ),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses)[201] == 1
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Payment).where(Payment.ride_id == uuid.UUID(done["id"]))
        )
        commission = await session.scalar(
            select(func.sum(WalletTransaction.amount)).where(
                WalletTransaction.ride_id == uuid.UUID(done["id"]),
                WalletTransaction.type == WalletTransactionType.COMMISSION,
            )
        )
    assert count == 1
    assert commission == Decimal("-0.800")


async def test_a_zero_fee_or_switched_off_facility_charges_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = (await rider_session(client))["headers"]
    async with session_factory() as session:
        row = await session.scalar(select(Facility).where(Facility.country_code == "JO"))
        row.is_active = False
        await session.commit()
    off = (await client.post("/rides/estimate", json=_body(), headers=rider)).json()
    assert off["airport_fee"] is None and off["estimated_fare"] == EXPECTED_FARE
    async with session_factory() as session:
        row = await session.scalar(select(Facility).where(Facility.country_code == "JO"))
        row.is_active = True
        row.fee = Decimal("0.000")
        await session.commit()
    zero = (await client.post("/rides/estimate", json=_body(), headers=rider)).json()
    assert zero["airport_fee"] is None


async def test_the_admin_adds_and_edits_facilities_and_a_crossed_area_is_refused(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    listed = await client.get("/admin/facilities?country=JO", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert [row["name"] for row in listed.json()] == ["مطار الملكة علياء الدولي"]
    assert listed.json()[0]["fee"] == FEE

    bow = [[35.80, 31.90], [35.82, 31.92], [35.80, 31.92], [35.82, 31.90]]
    crossed = await client.post(
        "/admin/facilities",
        json={"country_code": "JO", "name": "مرفقٌ معقود", "area": bow, "fee": "0.500", "is_active": True},
        headers=admin_headers,
    )
    assert crossed.status_code == 422 and crossed.json()["code"] == "invalid_input"

    square = [[35.80, 31.90], [35.82, 31.90], [35.82, 31.92], [35.80, 31.92]]
    created = await client.post(
        "/admin/facilities",
        json={"country_code": "JO", "name": "مطار ماركا", "area": square, "fee": "0.500", "is_active": True},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["area"] == square and row["fee"] == "0.500"

    patched = await client.patch(
        f"/admin/facilities/{row['id']}", json={"is_active": False, "fee": "0.750"}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["is_active"] is False and patched.json()["fee"] == "0.750"
    # ولا بابَ حذف
    assert (await client.delete(f"/admin/facilities/{row['id']}", headers=admin_headers)).status_code == 405


async def test_the_rider_sees_her_markets_active_airports_with_a_point_inside_each(
    client: AsyncClient, jordan_settings, session_factory
) -> None:
    """**«المطار» من الرئيسية** (قِيس على S21 ٢٠٢٦-١٠-٠٨: كانت «قريباً» والخدمةُ مشتعلة، والبحثُ يعيد شارعَ المطار لا المطار):
    مطفأً لا شيء · مشتعلاً مطاراتُ سوقه وحدَها، **ونقطةُ كلٍّ داخل مضلّعه فيُحسب عليها الرسم** · والمطفأُ من المرافق لا يُعرض."""
    rider = await rider_session(client)
    headers = rider["headers"]
    off = await client.get("/airports", headers=headers)
    assert off.status_code == 200 and off.json() == []

    await enable_features(session_factory, FLAG)
    listed = (await client.get("/airports", headers=headers)).json()
    assert [row["name"] for row in listed] == ["مطار الملكة علياء الدولي"], listed
    point = listed[0]
    async with session_factory() as session:
        inside = await session.scalar(
            select(func.ST_Covers(Facility.area, func.ST_GeogFromText(f"SRID=4326;POINT({point['lng']} {point['lat']})"))).where(
                Facility.name == "مطار الملكة علياء الدولي"
            )
        )
        assert inside is True
        facility = await session.scalar(select(Facility).where(Facility.name == "مطار الملكة علياء الدولي"))
        facility.is_active = False
        await session.commit()
    assert (await client.get("/airports", headers=headers)).json() == []
