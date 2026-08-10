"""التقييم المتبادل ومتوسط الكبتن (SPEC القسم 4/5.9)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from tests.helpers import (
    DRIVER,
    OTHER_RIDER,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    started_ride,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    return auth(await register(client, payload))


async def _online_driver(
    client: AsyncClient, session_factory, payload: dict = DRIVER, **kwargs
) -> dict:
    driver = await approved_driver(client, session_factory, payload, **kwargs)
    await bring_online(client, driver)
    return driver


async def _rating_avg(session_factory, driver_id) -> str:
    async with session_factory() as session:
        return str(
            await session.scalar(select(Driver.rating_avg).where(Driver.id == driver_id))
        )


async def _rate(client: AsyncClient, headers: dict, ride_id: str, stars: int, **extra):
    return await client.post(
        f"/rides/{ride_id}/ratings", json={"stars": stars, **extra}, headers=headers
    )


async def test_rider_rating_updates_the_driver_average(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    response = await _rate(client, rider, ride["id"], 4, comment="كبتن ممتاز")
    assert response.status_code == 201, response.text
    assert response.json()["rater_type"] == "rider"
    assert response.json()["stars"] == 4
    assert await _rating_avg(session_factory, driver["driver_id"]) == "4.00"


async def test_the_average_is_recomputed_from_the_whole_table(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """متوسطٌ مشتق لا مُراكَم: تقييمان (5 و2) يعطيان 3.50 بالضبط."""
    rider = await _rider(client)
    other = await _rider(client, OTHER_RIDER)
    driver = await _online_driver(client, session_factory)

    first = await completed_ride(client, rider, driver)
    await _rate(client, rider, first["id"], 5)
    second = await completed_ride(client, other, driver)
    await _rate(client, other, second["id"], 2)

    assert await _rating_avg(session_factory, driver["driver_id"]) == "3.50"


async def test_driver_rating_does_not_touch_the_driver_average(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تقييم الكبتن للراكب لا يرفع تقييم الكبتن نفسه."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    response = await _rate(client, driver["headers"], ride["id"], 5)
    assert response.status_code == 201, response.text
    assert response.json()["rater_type"] == "driver"
    assert await _rating_avg(session_factory, driver["driver_id"]) == "0.00"


async def test_both_sides_rate_the_same_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    await _rate(client, rider, ride["id"], 5)
    await _rate(client, driver["headers"], ride["id"], 3)

    listed = (await client.get(f"/rides/{ride['id']}/ratings", headers=rider)).json()
    assert {entry["rater_type"] for entry in listed} == {"rider", "driver"}


async def test_a_side_rates_only_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    await _rate(client, rider, ride["id"], 5)
    again = await _rate(client, rider, ride["id"], 1)

    assert again.status_code == 409
    assert again.json()["code"] == "already_rated"
    assert await _rating_avg(session_factory, driver["driver_id"]) == "5.00"


async def test_rating_before_completion_is_rejected(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await started_ride(client, rider, driver)

    response = await _rate(client, rider, ride["id"], 5)
    assert response.status_code == 409
    assert response.json()["code"] == "rating_not_allowed"


async def test_a_stranger_cannot_rate_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """404 من فحص الملكية نفسه — لا تصل الطلبات إلى منطق التقييم أصلاً."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    intruder = await _rider(client, OTHER_RIDER)

    assert (await _rate(client, intruder, ride["id"], 1)).status_code == 404


async def test_an_admin_reading_the_ride_is_still_not_a_party_to_it(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """الإدارة تقرأ الرحلات ولا تقيّمها: التقييم للطرفين وحدهما (القسم 5.9)."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    response = await _rate(client, admin_headers, ride["id"], 5)
    assert response.status_code == 409
    assert response.json()["code"] == "rating_not_allowed"


async def test_stars_outside_one_to_five_are_rejected(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)

    assert (await _rate(client, rider, ride["id"], 0)).status_code == 422
    assert (await _rate(client, rider, ride["id"], 6)).status_code == 422


async def test_a_driver_from_another_ride_cannot_rate_it(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الدور لا يكفي — الطرفية في هذه الرحلة بعينها هي الشرط."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider, driver)
    stranger = await _online_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )

    assert (await _rate(client, stranger["headers"], ride["id"], 1)).status_code == 404
