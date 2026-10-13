"""مناطقُ التسعير (SPEC §٧٤-أ/٥) — **سعرٌ موحَّدٌ لكلِّ الولايات إلا الوعرة، وولايةُ الانطلاق تحكم**.

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**

١) **الحدودُ صحيحة**: ٥٨ ولاية، ومدنٌ معروفةٌ في ولاياتها، **والولايةُ الجديدةُ في أمّها** (بوسعادة في المسيلة) حتى ٢٠٢٧.
٢) **إعادةُ التحميل لا تمحو قرارَ المالك** (الوسمُ والنسبة).
٣) **العاصمةُ بلا سطر، وتيزي وزو بسطر «تسعيرة المناطق الوعرة»** = النسبةُ من أجرة الطريق، **والجدولُ يحلّ محلَّ تسعيرة الدولة**
   ويظهر فرقُه سطراً.
٤) **المنطقةُ تُجمَّد على الرحلة** وتُعاد عند انحراف الطريق بنفسها.
٥) **اللوحةُ**: القراءةُ للطاقم والكتابةُ لمن يكتب التسعير، وتجميدُ التسعير يجمّدها.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import CountryCode, FeatureKey, ProviderKey, VehicleCategory
from app.models.pricing import PricingRule
from app.models.pricing_zone import PricingZone
from app.models.ride import Ride
from app.services import pricing_zones, settings_service
from app.services.providers import credentials as credentials_service
from scripts.load_pricing_zones import RUGGED_PROPOSAL
from tests.helpers import MAPBOX_SECRET, RIDER, rider_session

pytestmark = pytest.mark.asyncio

ALGERIAN_RIDER = RIDER | {"phone": "0551234567", "country_code": "DZ", "name": "راكبٌ من الجزائر"}
#: نقاطٌ بأسمائها (عرض، طول)
PLACES = {
    "16": (36.7538, 3.0588),  # الجزائر العاصمة
    "31": (35.6971, -0.6308),  # وهران
    "25": (36.3650, 6.6147),  # قسنطينة
    "15": (36.7169, 4.0497),  # تيزي وزو
    "11": (22.7850, 5.5228),  # تمنراست
    "28": (35.2133, 4.1739),  # بوسعادة — ولايةٌ جديدةٌ مضمومةٌ إلى المسيلة حتى ٢٠٢٧
    "17": (34.1500, 3.5000),  # مسعد — مضمومةٌ إلى الجلفة
}


async def _load(session_factory) -> None:
    async with session_factory() as session:
        await pricing_zones.load_country(session, CountryCode.DZ, rugged_codes=RUGGED_PROPOSAL[CountryCode.DZ])
        await session.commit()


async def _algeria_pricing(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            PricingRule(
                country_code=CountryCode.DZ,
                vehicle_category=VehicleCategory.ECONOMY,
                base_fare=Decimal("100"),
                price_per_km=Decimal("40"),
                price_per_min=Decimal("8"),
                minimum_fare=Decimal("230"),
                cancellation_fee=Decimal("100"),
            )
        )
        await credentials_service.upsert(
            session,
            provider_key=ProviderKey.MAPBOX,
            country_code=None,
            values={"public_token": "pk.test", "secret_token": MAPBOX_SECRET},
            is_active=True,
        )
        await session.commit()


def _point(code: str, east: float = 0.01) -> tuple[dict, dict]:
    lat, lng = PLACES[code]
    return {"lat": lat, "lng": lng}, {"lat": lat, "lng": lng + east}


# ─────────────────────────────────────────── ١) الحدود


async def test_fifty_eight_zones_and_each_city_in_its_wilaya(session_factory) -> None:
    await _load(session_factory)
    async with session_factory() as session:
        zones = await pricing_zones.list_for(session, CountryCode.DZ)
        assert len(zones) == 58
        assert {zone.code for zone in zones} == {f"{n:02d}" for n in range(1, 59)}
        for code, (lat, lng) in PLACES.items():
            zone = await pricing_zones.zone_at(session, CountryCode.DZ, lat, lng)
            assert zone is not None and zone.code == code, (code, zone and zone.code)
        # **والمقترحُ موسومٌ في التحميل الأوّل** بنسبته الافتراضية
        rugged = {zone.code for zone in zones if zone.rugged}
        assert rugged == set(RUGGED_PROPOSAL[CountryCode.DZ])
        assert all(zone.adjustment_percent == Decimal("25.00") for zone in zones)
        msila = next(zone for zone in zones if zone.code == "28")
        assert "بوسعادة" in (msila.note or "")


async def test_reloading_keeps_the_owners_decision(session_factory) -> None:
    await _load(session_factory)
    async with session_factory() as session:
        zone = (await session.scalars(select(PricingZone).where(PricingZone.code == "15"))).one()
        zone.rugged = False
        zone.adjustment_percent = Decimal("30.00")
        await session.commit()
    await _load(session_factory)
    async with session_factory() as session:
        zone = (await session.scalars(select(PricingZone).where(PricingZone.code == "15"))).one()
        assert zone.rugged is False and zone.adjustment_percent == Decimal("30.00")


# ─────────────────────────────────────────── ٣) السعر


async def _estimate(client: AsyncClient, rider: dict, code: str) -> dict:
    pickup, dropoff = _point(code)
    answer = await client.post(
        "/rides/estimate",
        json={"pickup": pickup, "dropoff": dropoff, "vehicle_category": "economy"},
        headers=rider["headers"],
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


async def test_a_normal_wilaya_keeps_the_unified_price_and_a_rugged_one_adds_its_line(
    client: AsyncClient, session_factory
) -> None:
    """**الطريقُ المستعار ١٠ كم و٢٠ دقيقة**: `100 + 10×40 + 20×8 = 660` — والوعرةُ بنسبتها ٢٥٪: `165` فـ`825`."""
    await _load(session_factory)
    await _algeria_pricing(session_factory)
    rider = await rider_session(client, ALGERIAN_RIDER)

    algiers = await _estimate(client, rider, "16")
    assert algiers["priced_fare"] == "660" and algiers["rugged_fee"] is None

    tizi = await _estimate(client, rider, "15")
    assert tizi["rugged_fee"] == "165" and tizi["priced_fare"] == "825"


async def test_a_zone_table_replaces_the_country_rates_and_shows_the_difference(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**بالجدول**: `150 + 10×60 + 20×10 = 950` بدل `660` — والفرقُ `290` سطرُ المنطقة، ومجموعُ الأسطر هو السعر."""
    await _load(session_factory)
    await _algeria_pricing(session_factory)
    rider = await rider_session(client, ALGERIAN_RIDER)
    zones = (await client.get("/admin/pricing-zones", params={"country_code": "DZ"}, headers=admin_headers)).json()["zones"]
    tizi = next(zone for zone in zones if zone["code"] == "15")
    rule = await client.put(
        f"/admin/pricing-zones/{tizi['id']}/rules/economy",
        json={"base_fare": "150", "price_per_km": "60", "price_per_min": "10", "minimum_fare": "300"},
        headers=admin_headers,
    )
    assert rule.status_code == 200, rule.text
    mode = await client.put(f"/admin/pricing-zones/{tizi['id']}", json={"adjustment_mode": "table"}, headers=admin_headers)
    assert mode.status_code == 200, mode.text

    body = await _estimate(client, rider, "15")
    assert body["priced_fare"] == "950" and body["rugged_fee"] == "290"


async def test_the_zone_is_frozen_on_the_ride(client: AsyncClient, session_factory) -> None:
    await _load(session_factory)
    await _algeria_pricing(session_factory)
    rider = await rider_session(client, ALGERIAN_RIDER)
    pickup, dropoff = _point("15")
    made = await client.post(
        "/rides", json={"pickup": pickup, "dropoff": dropoff, "vehicle_category": "economy"}, headers=rider["headers"]
    )
    assert made.status_code == 201, made.text
    async with session_factory() as session:
        ride = await session.get(Ride, made.json()["id"])
        zone = await session.get(PricingZone, ride.pricing_zone_id)
        assert zone.code == "15"
        rugged = [Decimal(line["amount"]) for line in ride.fare_lines if line["kind"] == "rugged"]
        assert rugged == [Decimal("165")]
        assert ride.estimated_fare == Decimal("825")


async def test_a_market_without_zones_is_untouched(client: AsyncClient, jordan_settings: None) -> None:
    from tests.helpers import DROPOFF, PICKUP

    rider = await rider_session(client)
    body = (
        await client.post(
            "/rides/estimate",
            json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
            headers=rider["headers"],
        )
    ).json()
    assert body["rugged_fee"] is None


# ─────────────────────────────────────────── ٥) اللوحة


async def test_staff_read_the_zones_and_the_map(client: AsyncClient, session_factory, support_headers: dict) -> None:
    await _load(session_factory)
    listed = await client.get("/admin/pricing-zones", params={"country_code": "DZ"}, headers=support_headers)
    assert listed.status_code == 200 and len(listed.json()["zones"]) == 58
    assert "OpenStreetMap" in listed.json()["attribution"]
    drawn = await client.get("/admin/pricing-zones/map", params={"country_code": "DZ"}, headers=support_headers)
    assert drawn.status_code == 200
    features = drawn.json()["features"]
    assert len(features) == 58 and features[0]["geometry"]["type"] == "MultiPolygon"


async def test_support_cannot_write_and_a_pricing_freeze_freezes_zones_too(
    client: AsyncClient, session_factory, support_headers: dict, admin_headers: dict
) -> None:
    await _load(session_factory)
    zones = (await client.get("/admin/pricing-zones", params={"country_code": "DZ"}, headers=admin_headers)).json()["zones"]
    zone_id = zones[0]["id"]
    denied = await client.put(f"/admin/pricing-zones/{zone_id}", json={"rugged": True}, headers=support_headers)
    assert denied.status_code == 403, denied.text
    async with session_factory() as session:
        await settings_service.set_flag(
            session, country_code=CountryCode.DZ, feature_key=FeatureKey.PRICING_WRITES_ENABLED, enabled=False
        )
        await session.commit()
    frozen = await client.put(f"/admin/pricing-zones/{zone_id}", json={"adjustment_percent": "40"}, headers=admin_headers)
    assert frozen.status_code >= 400, frozen.text
    bad = await client.put(f"/admin/pricing-zones/{zone_id}", json={"adjustment_percent": "250"}, headers=admin_headers)
    assert bad.status_code == 422, bad.text
