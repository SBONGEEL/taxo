from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.commission import CommissionSetting
from app.models.driver import Driver
from app.models.enums import CountryCode, VehicleCategory
from app.models.pricing import PricingRule
from app.models.ride import Ride
from tests.helpers import (
    CANCELLATION_FEE,
    DRIVER,
    DROPOFF,
    EXPECTED_FARE,
    OTHER_RIDER,
    PICKUP,
    RIDER,
    accepted_ride,
    approved_driver,
    auth,
    bring_online,
    register,
    request_ride,
    wait_for_status,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    return auth(await register(client, payload))


async def _online_driver(client: AsyncClient, session_factory) -> dict:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    return driver


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
    headers = auth(await register(client, DRIVER))
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
    ride = await request_ride(client, headers)

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
    await request_ride(client, headers)

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
    ride = await request_ride(client, headers)
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

    ride = await request_ride(client, await _rider(client))
    assert ride["commission_percent_at_ride"] == "0.00"


# --------------------------------------------------------------- دورة الحياة


async def test_full_ride_lifecycle(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver = await _online_driver(client, session_factory)

    body = await accepted_ride(client, rider_headers, driver)
    ride_id = body["id"]
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
        response = await client.post(
            f"/rides/{ride_id}/{action}", headers=driver["headers"]
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected

    final = await client.get(f"/rides/{ride_id}", headers=rider_headers)
    data = final.json()
    assert data["final_fare"] == EXPECTED_FARE
    assert data["completed_at"] is not None

    # الكبتن تحرر لرحلة جديدة
    async with session_factory() as session:
        driver_row = await session.get(Driver, driver["driver_id"])
        assert driver_row.current_ride_id is None


async def test_status_actions_follow_the_state_machine(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride_id = (await accepted_ride(client, rider_headers, driver))["id"]

    # لا بدء قبل الوصول
    out_of_order = await client.post(
        f"/rides/{ride_id}/start", headers=driver["headers"]
    )
    assert out_of_order.status_code == 409
    assert out_of_order.json()["code"] == "invalid_ride_transition"

    # ولا قبول مرتين — العرض استُهلك
    again = await client.post(f"/rides/{ride_id}/accept", headers=driver["headers"])
    assert again.status_code == 409
    assert again.json()["code"] == "ride_offer_expired"


async def test_unapproved_driver_cannot_accept(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider_headers = await _rider(client)
    driver_headers = auth(await register(client, DRIVER))
    ride_id = (await request_ride(client, rider_headers))["id"]

    response = await client.post(f"/rides/{ride_id}/accept", headers=driver_headers)
    assert response.status_code == 403


async def test_completed_ride_is_terminal(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride_id = (await accepted_ride(client, rider_headers, driver))["id"]

    for action in ("arrive", "start", "complete"):
        await client.post(f"/rides/{ride_id}/{action}", headers=driver["headers"])

    cancelled = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=rider_headers
    )
    assert cancelled.status_code == 409


# ------------------------------------------------------------------- الإلغاء


async def test_cancelling_before_acceptance_is_free(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride_id = (await request_ride(client, headers))["id"]

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
    driver = await _online_driver(client, session_factory)
    ride_id = (await accepted_ride(client, rider_headers, driver))["id"]

    response = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=rider_headers
    )

    assert response.status_code == 200
    assert response.json()["cancellation_fee"] == CANCELLATION_FEE

    async with session_factory() as session:
        driver_row = await session.get(Driver, driver["driver_id"])
        assert driver_row.current_ride_id is None


async def test_driver_cancelling_costs_the_rider_nothing(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider_headers = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride_id = (await accepted_ride(client, rider_headers, driver))["id"]

    response = await client.post(
        f"/rides/{ride_id}/cancel", json={}, headers=driver["headers"]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled_by_driver"
    assert data["cancellation_fee"] == "0.000"


async def test_cancelling_releases_the_rider_for_a_new_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    ride_id = (await request_ride(client, headers))["id"]
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
    ride_id = (await request_ride(client, owner_headers))["id"]
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
    ride_id = (await request_ride(client, rider_headers))["id"]
    driver_headers = auth(await register(client, DRIVER))

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
    ride_id = (await request_ride(client, rider_headers))["id"]

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
    driver = await _online_driver(client, session_factory)
    ride_id = (await accepted_ride(client, rider_headers, driver))["id"]

    rider_list = await client.get("/rides/me", headers=rider_headers)
    driver_list = await client.get("/rides/me", headers=driver["headers"])

    # الصفُّ صار `RideListItem`: الرحلةُ ومعها ملخّصُ دفعها (البند 19)
    assert [r["ride"]["id"] for r in rider_list.json()] == [ride_id]
    assert [r["ride"]["id"] for r in driver_list.json()] == [ride_id]
    assert rider_list.json()[0]["has_open_dispute"] is False


async def test_active_ride_endpoint_reflects_current_state(
    client: AsyncClient, jordan_settings: None
) -> None:
    headers = await _rider(client)
    assert (await client.get("/rides/me/active", headers=headers)).json() is None

    ride_id = (await request_ride(client, headers))["id"]
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
    await request_ride(client, headers)

    async with session_factory() as session:
        ride = await session.scalar(select(Ride))
        assert ride.pickup_lat == pytest.approx(PICKUP["lat"])
        assert ride.pickup_lng == pytest.approx(PICKUP["lng"])
        assert ride.dropoff_lat == pytest.approx(DROPOFF["lat"])


async def test_ride_without_any_driver_ends_as_no_driver_found(
    client: AsyncClient, jordan_settings: None
) -> None:
    """لا كبتن أونلاين ← تنتهي المهلة بحالة `no_driver_found` (SPEC القسم 5.3)."""
    headers = await _rider(client)
    ride_id = (await request_ride(client, headers))["id"]

    await wait_for_status(client, headers, ride_id, "no_driver_found")
