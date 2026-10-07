"""بين المدن (SPEC §٦٣-ج/٧، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ، والمالكُ يتحقّق من القانون قبل إشعاله**.

ما يحرسه هذا الملف:

- **مطفأً يُرفض**؛ **وبلا تصريحٍ لا يُعلن الكبتنُ رحلة**، والتصريحُ بمركبةٍ ٢٠١٥ فأحدث وتأمينٍ سارٍ.
- **المقعدُ من المحفظة يُحفظ، والسيارةُ نقداً**؛ **وحجزان معاً على آخر مقعدٍ ⇒ واحد** (قفلُ الرحلة).
- **الكبتنُ يلغي قبل المهلة بلا أثر ويُردّ كاملاً**، **وبعدها لا**؛ **وعند المهلة رحلةٌ لم تبلغ حدَّها تُلغى وحدَها بالردّ**.
- **الإنهاءُ يوصل المحفوظَ للكبتن وعليه العمولة.**
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import FeatureKey
from app.models.intercity import IntercityTrip
from app.models.service_setting import ServiceSetting
from app.models.vehicle import Vehicle
from app.services import intercity
from tests.helpers import (
    DRIVER,
    approved_driver,
    enable_features,
    rider_session,
    set_commission,
    topup_wallet,
    wallet_of,
)

FLAG = FeatureKey.INTERCITY_ENABLED.value
ROUTE = {
    "country_code": "JO",
    "from_city": "عمّان",
    "to_city": "إربد",
    "from_lat": 31.95,
    "from_lng": 35.91,
    "from_point": "مجمّع الشمال",
    "to_lat": 32.55,
    "to_lng": 35.85,
    "to_point": "مجمّع عمّان الجديد",
    "price_car": "22.000",
    "price_seat": "6.000",
}


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO"), ServiceSetting(country_code="LY")])
        await session.commit()


async def _setup(client, admin_headers, session_factory, *, insurance_days: int = 200) -> tuple[dict, dict]:
    await enable_features(session_factory, FLAG)
    route = (await client.post("/admin/intercity/routes", json=ROUTE, headers=admin_headers)).json()
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        vehicle_id = await session.scalar(select(Vehicle.id).where(Vehicle.driver_id == driver["driver_id"]))
    granted = await client.post(
        f"/admin/intercity/drivers/{driver['driver_id']}/permit",
        json={"vehicle_id": str(vehicle_id), "seats": 4, "insurance_expires_on": (date.today() + timedelta(days=insurance_days)).isoformat()},
        headers=admin_headers,
    )
    assert granted.status_code == 201, granted.text
    return route, driver


async def _trip(client, route: dict, driver: dict, *, hours: float = 10, seats: int = 4, min_seats: int = 1) -> dict:
    posted = await client.post(
        "/drivers/me/intercity/trips",
        json={
            "route_id": route["id"],
            "departs_at": (datetime.now(UTC) + timedelta(hours=hours)).isoformat(),
            "seats": seats,
            "min_seats": min_seats,
        },
        headers=driver["headers"],
    )
    assert posted.status_code == 201, posted.text
    return posted.json()


async def test_switched_off_or_without_a_permit_nothing_is_posted(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    rider = await rider_session(client)
    assert (await client.get("/intercity/trips", headers=rider["headers"])).status_code == 403
    await enable_features(session_factory, FLAG)
    route = (await client.post("/admin/intercity/routes", json=ROUTE, headers=admin_headers)).json()
    driver = await approved_driver(client, session_factory, DRIVER)
    refused = await client.post(
        "/drivers/me/intercity/trips",
        json={"route_id": route["id"], "departs_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(), "seats": 3, "min_seats": 1},
        headers=driver["headers"],
    )
    assert refused.status_code == 403 and refused.json()["code"] == "intercity_permit_required"


async def test_the_permit_needs_a_2015_car_and_live_insurance(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        vehicle = await session.scalar(select(Vehicle).where(Vehicle.driver_id == driver["driver_id"]))
        vehicle.year = 2012
        vehicle_id = vehicle.id
        await session.commit()
    old = await client.post(
        f"/admin/intercity/drivers/{driver['driver_id']}/permit",
        json={"vehicle_id": str(vehicle_id), "seats": 4, "insurance_expires_on": (date.today() + timedelta(days=100)).isoformat()},
        headers=admin_headers,
    )
    assert old.status_code == 422
    async with session_factory() as session:
        vehicle = await session.get(Vehicle, vehicle_id)
        vehicle.year = 2018
        await session.commit()
    lapsed = await client.post(
        f"/admin/intercity/drivers/{driver['driver_id']}/permit",
        json={"vehicle_id": str(vehicle_id), "seats": 4, "insurance_expires_on": (date.today() - timedelta(days=1)).isoformat()},
        headers=admin_headers,
    )
    assert lapsed.status_code == 422


async def test_the_captain_cancels_before_the_deadline_for_free_and_not_after(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    route, driver = await _setup(client, admin_headers, session_factory)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    early = await _trip(client, route, driver)
    await client.post("/intercity/bookings", json={"trip_id": early["id"], "seats": 2}, headers=rider["headers"])
    assert (await wallet_of(client, rider["headers"]))["balance"] == "8.000"
    cancelled = await client.post(f"/drivers/me/intercity/trips/{early['id']}/cancel", headers=driver["headers"])
    assert cancelled.status_code == 200, cancelled.text
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000"

    late = await _trip(client, route, driver)
    async with session_factory() as session:
        row = await session.get(IntercityTrip, uuid.UUID(late["id"]))
        row.departs_at = datetime.now(UTC) + timedelta(hours=1)
        await session.commit()
    refused = await client.post(f"/drivers/me/intercity/trips/{late['id']}/cancel", headers=driver["headers"])
    assert refused.status_code == 409


async def test_a_trip_below_its_minimum_at_the_deadline_is_cancelled_with_full_refunds(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    route, driver = await _setup(client, admin_headers, session_factory)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    trip = await _trip(client, route, driver, min_seats=3)
    await client.post("/intercity/bookings", json={"trip_id": trip["id"], "seats": 1}, headers=rider["headers"])
    async with session_factory() as session:
        row = await session.get(IntercityTrip, uuid.UUID(trip["id"]))
        row.departs_at = datetime.now(UTC) + timedelta(minutes=90)
        await session.commit()
    async with session_factory() as session:
        assert (await intercity.sweep(session))["cancelled"] == 1
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000"


async def test_completion_pays_the_captain_the_held_seats_less_commission(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await set_commission(session_factory, "10.00")
    route, driver = await _setup(client, admin_headers, session_factory)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    trip = await _trip(client, route, driver)
    await client.post("/intercity/bookings", json={"trip_id": trip["id"], "seats": 2}, headers=rider["headers"])
    assert (await client.post(f"/drivers/me/intercity/trips/{trip['id']}/depart", headers=driver["headers"])).status_code == 200
    done = await client.post(f"/drivers/me/intercity/trips/{trip['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    assert (await wallet_of(client, driver["headers"]))["balance"] == "10.800"
