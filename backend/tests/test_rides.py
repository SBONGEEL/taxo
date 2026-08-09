from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.commission import CommissionSetting
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, ProviderKey, VehicleCategory
from app.models.pricing import PricingRule
from app.models.ride import Ride
from app.services import directions
from app.services.directions import Route
from app.services.providers import credentials as credentials_service

# نقطتان في عمّان — القيم الحقيقية لا تهم لأن Mapbox مُستبدَل في الاختبار
PICKUP = {"lat": 31.9539, "lng": 35.9106}
DROPOFF = {"lat": 31.9800, "lng": 35.8900}

MAPBOX_SECRET = "sk.test-token"

RIDER = {
    "phone": "0791111111",
    "name": "راكب الرحلات",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "rider",
}
DRIVER = {
    "phone": "0792222222",
    "name": "كبتن الرحلات",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "driver",
}
OTHER_RIDER = RIDER | {"phone": "0793333333", "name": "راكب آخر"}

# 1.000 + (10 × 0.500) + (20 × 0.100) = 8.000
STUB_ROUTE = Route(distance_km=Decimal("10.000"), duration_min=Decimal("20.00"))
EXPECTED_FARE = "8.000"
CANCELLATION_FEE = "0.750"


@pytest.fixture(autouse=True)
def stub_mapbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """يستبدل نداء Mapbox وحده — قراءة التوكن من عقود المزودين تبقى حقيقية."""

    async def _fetch_route(token: str, pickup, dropoff) -> Route:
        assert token == MAPBOX_SECRET, "التوكن السري يجب أن يأتي من جدول العقود"
        return STUB_ROUTE

    monkeypatch.setattr(directions, "fetch_route", _fetch_route)


@pytest.fixture
async def jordan_settings(session_factory) -> None:
    """تسعيرة الأردن + عقد Mapbox مفعّل — أدنى ما تحتاجه رحلة."""
    async with session_factory() as session:
        session.add(
            PricingRule(
                country_code=CountryCode.JO,
                vehicle_category=VehicleCategory.ECONOMY,
                base_fare=Decimal("1.000"),
                price_per_km=Decimal("0.500"),
                price_per_min=Decimal("0.100"),
                minimum_fare=Decimal("2.000"),
                cancellation_fee=Decimal(CANCELLATION_FEE),
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


async def _register(client: AsyncClient, payload: dict) -> dict:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['tokens']['access_token']}"}


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    return _auth(await _register(client, payload))


async def _approved_driver(client: AsyncClient, session_factory) -> dict:
    """كبتن معتمد بمركبة — الموافقة تتم من اللوحة (المرحلة 11) فنكتبها مباشرة."""
    headers = _auth(await _register(client, DRIVER))
    await client.post(
        "/drivers/me/vehicles",
        json={
            "make": "Toyota",
            "model": "Camry",
            "year": 2021,
            "color": "أبيض",
            "plate_number": "AMM-4242",
            "category": "economy",
        },
        headers=headers,
    )

    async with session_factory() as session:
        driver = await session.scalar(select(Driver))
        driver.status = DriverStatus.APPROVED
        await session.commit()

    return headers


async def _request_ride(client: AsyncClient, headers: dict) -> dict:
    response = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------------ التسعير


async def test_estimate_prices_the_route_in_the_backend(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    response = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["estimated_fare"] == EXPECTED_FARE
    assert data["distance_km"] == "10.000"
    assert data["currency"] == "JOD"
    assert data["minimum_fare_applied"] is False


async def test_estimate_fails_without_a_pricing_rule(client: AsyncClient) -> None:
    headers = await _rider(client)
    response = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": DROPOFF},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "pricing_rule_missing"


async def test_estimate_fails_without_an_active_mapbox_contract(
    client: AsyncClient, session_factory
) -> None:
    async with session_factory() as session:
        session.add(
            PricingRule(
                country_code=CountryCode.JO,
                vehicle_category=VehicleCategory.ECONOMY,
                base_fare=Decimal("1.000"),
                price_per_km=Decimal("0.500"),
                price_per_min=Decimal("0.100"),
                minimum_fare=Decimal("2.000"),
                cancellation_fee=Decimal(CANCELLATION_FEE),
            )
        )
        await session.commit()

    headers = await _rider(client)
    response = await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": DROPOFF},
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["code"] == "routing_unavailable"


async def test_driver_cannot_request_a_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = _auth(await _register(client, DRIVER))
    response = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=headers
    )

    assert response.status_code == 403


async def test_coordinates_are_validated(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    response = await client.post(
        "/rides/estimate",
        json={"pickup": {"lat": 200, "lng": 35.9}, "dropoff": DROPOFF},
        headers=headers,
    )

    assert response.status_code == 422


# -------------------------------------------------------------------- الطلب


async def test_requested_ride_stores_backend_computed_values(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride = await _request_ride(client, headers)

    assert ride["status"] == "requested"
    assert ride["estimated_fare"] == EXPECTED_FARE
    assert ride["currency"] == "JOD"
    assert ride["driver"] is None
    assert ride["final_fare"] is None
    # الإحداثيات تعود كما أُرسلت بعد رحلة ذهاب وإياب لعمود geography
    assert ride["pickup"]["lat"] == pytest.approx(PICKUP["lat"])
    assert ride["dropoff"]["lng"] == pytest.approx(DROPOFF["lng"])


async def test_rider_cannot_have_two_active_rides(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    await _request_ride(client, headers)

    response = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ride_already_active"


async def test_commission_percent_is_frozen_at_creation(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رفع النسبة بعد الإنشاء لا يمس رحلة قائمة (SPEC القسم 4)."""
    async with session_factory() as session:
        session.add(
            CommissionSetting(
                country_code=CountryCode.JO,
                commission_enabled=True,
                commission_percent=Decimal("12.50"),
            )
        )
        await session.commit()

    headers = await _rider(client)
    ride = await _request_ride(client, headers)
    assert ride["commission_percent_at_ride"] == "12.50"

    async with session_factory() as session:
        setting = await session.scalar(select(CommissionSetting))
        setting.commission_percent = Decimal("30.00")
        await session.commit()

    fetched = await client.get(f"/rides/{ride['id']}", headers=headers)
    assert fetched.json()["commission_percent_at_ride"] == "12.50"


async def test_commission_is_zero_while_the_switch_is_off(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    async with session_factory() as session:
        session.add(
            CommissionSetting(
                country_code=CountryCode.JO,
                commission_enabled=False,
                commission_percent=Decimal("20.00"),
            )
        )
        await session.commit()

    ride = await _request_ride(client, await _rider(client))
    assert ride["commission_percent_at_ride"] == "0.00"


# --------------------------------------------------------------- دورة الحياة


async def test_full_ride_lifecycle(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride = await _request_ride(client, rider_headers)
    ride_id = ride["id"]

    accepted = await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["accepted_at"] is not None
    # بطاقة الكبتن التي يراها الراكب (SPEC القسم 5.4)
    assert body["driver"]["name"] == DRIVER["name"]
    assert body["driver"]["vehicle"]["plate_number"] == "AMM-4242"

    for action, expected in (
        ("arrive", "arrived"),
        ("start", "in_progress"),
        ("complete", "completed"),
    ):
        response = await client.post(f"/rides/{ride_id}/{action}", headers=driver_headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected

    final = await client.get(f"/rides/{ride_id}", headers=rider_headers)
    data = final.json()
    assert data["final_fare"] == EXPECTED_FARE
    assert data["completed_at"] is not None

    # الكبتن تحرر لرحلة جديدة
    async with session_factory() as session:
        driver = await session.scalar(select(Driver))
        assert driver.current_ride_id is None


async def test_status_actions_follow_the_state_machine(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride_id = (await _request_ride(client, rider_headers))["id"]

    # لا بدء قبل قبول
    early = await client.post(f"/rides/{ride_id}/start", headers=driver_headers)
    assert early.status_code == 403  # ليست مُسندة إليه بعد

    await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)

    # لا بدء قبل الوصول
    out_of_order = await client.post(f"/rides/{ride_id}/start", headers=driver_headers)
    assert out_of_order.status_code == 409
    assert out_of_order.json()["code"] == "invalid_ride_transition"

    # ولا قبول مرتين
    again = await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)
    assert again.status_code == 409


async def test_unapproved_driver_cannot_accept(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider_headers = await _rider(client)
    driver_headers = _auth(await _register(client, DRIVER))
    ride_id = (await _request_ride(client, rider_headers))["id"]

    response = await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)
    assert response.status_code == 403


async def test_completed_ride_is_terminal(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride_id = (await _request_ride(client, rider_headers))["id"]

    await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)
    await client.post(f"/rides/{ride_id}/arrive", headers=driver_headers)
    await client.post(f"/rides/{ride_id}/start", headers=driver_headers)
    await client.post(f"/rides/{ride_id}/complete", headers=driver_headers)

    cancelled = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=rider_headers
    )
    assert cancelled.status_code == 409


# ------------------------------------------------------------------- الإلغاء


async def test_cancelling_before_acceptance_is_free(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride_id = (await _request_ride(client, headers))["id"]

    response = await client.post(
        f"/rides/{ride_id}/cancel", json={"reason": "غيّرت رأيي"}, headers=headers
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "cancelled_by_rider"
    assert data["cancellation_fee"] == "0.000"
    assert data["cancelled_reason"] == "غيّرت رأيي"


async def test_rider_cancelling_after_acceptance_pays_the_fee(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride_id = (await _request_ride(client, rider_headers))["id"]
    await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)

    response = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=rider_headers
    )

    assert response.status_code == 200
    assert response.json()["cancellation_fee"] == CANCELLATION_FEE

    async with session_factory() as session:
        driver = await session.scalar(select(Driver))
        assert driver.current_ride_id is None


async def test_driver_cancelling_costs_the_rider_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride_id = (await _request_ride(client, rider_headers))["id"]
    await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)

    response = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=driver_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled_by_driver"
    assert data["cancellation_fee"] == "0.000"


async def test_cancelling_releases_the_rider_for_a_new_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride_id = (await _request_ride(client, headers))["id"]
    await client.post(f"/rides/{ride_id}/cancel", json={}, headers=headers)

    second = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=headers
    )
    assert second.status_code == 201


# ------------------------------------------------- الملكية والقراءة (لا IDOR)


async def test_other_rider_cannot_read_or_cancel_the_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    owner_headers = await _rider(client)
    ride_id = (await _request_ride(client, owner_headers))["id"]
    intruder_headers = await _rider(client, OTHER_RIDER)

    assert (
        await client.get(f"/rides/{ride_id}", headers=intruder_headers)
    ).status_code == 404
    assert (
        await client.post(
            f"/rides/{ride_id}/cancel", json={}, headers=intruder_headers
        )
    ).status_code == 404


async def test_unassigned_driver_cannot_touch_the_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider_headers = await _rider(client)
    ride_id = (await _request_ride(client, rider_headers))["id"]
    driver_headers = _auth(await _register(client, DRIVER))

    assert (
        await client.get(f"/rides/{ride_id}", headers=driver_headers)
    ).status_code == 404
    assert (
        await client.post(f"/rides/{ride_id}/arrive", headers=driver_headers)
    ).status_code == 403


async def test_staff_can_read_any_ride(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    """قسم الرحلات في اللوحة يفصل في النزاعات — قراءة فقط (SPEC القسم 13)."""
    rider_headers = await _rider(client)
    ride_id = (await _request_ride(client, rider_headers))["id"]

    assert (
        await client.get(f"/rides/{ride_id}", headers=support_headers)
    ).status_code == 200
    assert (
        await client.post(f"/rides/{ride_id}/cancel", json={}, headers=support_headers)
    ).status_code == 403


async def test_my_rides_lists_both_sides(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver_headers = await _approved_driver(client, session_factory)
    ride_id = (await _request_ride(client, rider_headers))["id"]
    await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)

    rider_list = await client.get("/rides/me", headers=rider_headers)
    driver_list = await client.get("/rides/me", headers=driver_headers)

    assert [r["id"] for r in rider_list.json()] == [ride_id]
    assert [r["id"] for r in driver_list.json()] == [ride_id]


async def test_active_ride_endpoint_reflects_current_state(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    assert (await client.get("/rides/me/active", headers=headers)).json() is None

    ride_id = (await _request_ride(client, headers))["id"]
    active = await client.get("/rides/me/active", headers=headers)
    assert active.json()["id"] == ride_id

    await client.post(f"/rides/{ride_id}/cancel", json={}, headers=headers)
    assert (await client.get("/rides/me/active", headers=headers)).json() is None


async def test_rides_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/rides/me")).status_code == 401
    assert (
        await client.post("/rides", json={"pickup": PICKUP, "dropoff": DROPOFF})
    ).status_code == 401


async def test_missing_ride_returns_404(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    response = await client.get(
        "/rides/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404


async def test_geography_columns_round_trip(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """العمودان geography فعلاً، والإحداثيات تُقرأ منهما بحساب في القاعدة."""
    headers = await _rider(client)
    await _request_ride(client, headers)

    async with session_factory() as session:
        ride = await session.scalar(select(Ride))
        assert ride.pickup_lat == pytest.approx(PICKUP["lat"])
        assert ride.pickup_lng == pytest.approx(PICKUP["lng"])
        assert ride.dropoff_lat == pytest.approx(DROPOFF["lat"])
