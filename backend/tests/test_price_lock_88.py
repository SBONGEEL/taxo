"""«اشحن مبلغ الرحلة الآن» — تثبيتُ السعر عشرَ دقائق (SPEC §٨٨/١، أمرُ المالك ٢٠٢٦-١٠-٢٨).

- التقديرُ بـ`lock_price` يعيد معرّفاً ونهايةَ مهلةٍ **وما ينقص المحفظة** (محسوباً في الخلفية).
- **ارتفاعُ التسعيرة بعد التثبيت لا يمسّ الطلبَ بالمعرّف** — ويمسّ من طلب بلا معرّف.
- **معرّفٌ بتفاصيل أخرى لا يُؤخذ**، **ومعرّفٌ يُستهلك مرّةً واحدة**، **ومعرّفُ راكبٍ لا يأخذه غيرُه**.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.pricing import PricingRule
from tests.helpers import DROPOFF, EXPECTED_FARE, OTHER_RIDER, PICKUP, RIDER, auth, register

pytestmark = pytest.mark.asyncio


async def _estimate(client, headers, **extra):
    response = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", **extra},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _request(client, headers, **extra):
    return await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy", **extra},
        headers=headers,
    )


async def _raise_prices(session_factory) -> None:
    async with session_factory() as session:
        for rule in (await session.scalars(select(PricingRule))).all():
            rule.base_fare = rule.base_fare + Decimal("5.000")
        await session.commit()


async def test_a_locked_price_survives_a_price_rise(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    headers = auth(await register(client, RIDER))
    locked = await _estimate(client, headers, lock_price=True)
    assert locked["quote_id"] and locked["locked_until"]
    assert locked["estimated_fare"] == EXPECTED_FARE
    # **رصيدٌ صفرٌ ⇐ ينقص المحفظةَ الأجرةُ كلُّها** (مقرَّبةً بوحدة السوق)
    assert Decimal(locked["wallet_shortfall"]) >= Decimal(EXPECTED_FARE)
    plain = await _estimate(client, headers)
    assert plain["quote_id"] is None and plain["wallet_shortfall"] is None

    await _raise_prices(session_factory)
    ride = await _request(client, headers, quote_id=locked["quote_id"])
    assert ride.status_code == 201, ride.text
    assert ride.json()["estimated_fare"] == EXPECTED_FARE


async def test_without_the_lock_or_with_other_details_the_price_is_fresh(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    headers = auth(await register(client, RIDER))
    locked = await _estimate(client, headers, lock_price=True)
    await _raise_prices(session_factory)
    moved = {"lat": DROPOFF["lat"] + 0.001, "lng": DROPOFF["lng"]}
    ride = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": moved, "vehicle_category": "economy", "quote_id": locked["quote_id"]},
        headers=headers,
    )
    assert ride.status_code == 201, ride.text
    assert Decimal(ride.json()["estimated_fare"]) > Decimal(EXPECTED_FARE)


async def test_a_lock_is_used_once_and_only_by_its_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    owner = auth(await register(client, RIDER))
    other = auth(await register(client, OTHER_RIDER))
    locked = await _estimate(client, owner, lock_price=True)
    await _raise_prices(session_factory)
    stolen = await _request(client, other, quote_id=locked["quote_id"])
    assert stolen.status_code == 201 and Decimal(stolen.json()["estimated_fare"]) > Decimal(EXPECTED_FARE)

    first = await _request(client, owner, quote_id=locked["quote_id"])
    assert first.status_code == 201 and first.json()["estimated_fare"] == EXPECTED_FARE
    cancelled = await client.post(f"/rides/{first.json()['id']}/cancel", json={}, headers=owner)
    assert cancelled.status_code == 200, cancelled.text
    again = await _request(client, owner, quote_id=locked["quote_id"])
    assert again.status_code == 201 and Decimal(again.json()["estimated_fare"]) > Decimal(EXPECTED_FARE)
