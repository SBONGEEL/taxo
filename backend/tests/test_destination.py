"""**«وجهتي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٥)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.services import destination
from tests.helpers import DRIVER, approved_driver

pytestmark = pytest.mark.asyncio

# عمّان: الكبتنُ في الوسط والوجهةُ شرقاً بنحو ٨ كم
HERE = (31.95, 35.91)
EAST = (31.95, 35.995)


def _fits(pickup: tuple[float, float], dropoff: tuple[float, float], percent: int = 30) -> bool:
    dest = destination.Destination(lat=EAST[0], lng=EAST[1], label="البيت", set_at=datetime.now(UTC))
    return destination.fits(
        dest,
        driver_lat=HERE[0],
        driver_lng=HERE[1],
        pickup_lat=pickup[0],
        pickup_lng=pickup[1],
        dropoff_lat=dropoff[0],
        dropoff_lng=dropoff[1],
        detour_percent=percent,
    )


async def test_only_a_ride_that_brings_him_closer_within_the_detour_fits() -> None:
    assert _fits((31.951, 35.915), (31.952, 35.97)), "على الطريق شرقاً"
    assert not _fits((31.951, 35.915), (31.95, 35.86)), "غرباً — يبعده"
    assert not _fits((31.951, 35.915), (31.99, 35.97)), "شرقاً لكن بانحرافٍ شماليٍّ كبير"
    assert _fits((31.951, 35.915), (31.99, 35.97), percent=100), "والنسبةُ من اللوحة تحكم"


async def test_keep_heading_drops_only_the_driver_whose_destination_disagrees(client: AsyncClient) -> None:
    import uuid

    from app.core.redis_client import get_redis_client

    redis_client = get_redis_client()

    with_dest, without = uuid.uuid4(), uuid.uuid4()
    await redis_client.set(
        f"driver:dest:{with_dest}",
        '{"lat": %s, "lng": %s, "label": "x", "set_at": "%s"}' % (EAST[0], EAST[1], datetime.now(UTC).isoformat()),
    )
    ride = SimpleNamespace(
        country_code="JO", pickup_lat=31.951, pickup_lng=35.915, dropoff_lat=31.95, dropoff_lng=35.86
    )
    ranked = [
        SimpleNamespace(driver_id=with_dest, lat=HERE[0], lng=HERE[1]),
        SimpleNamespace(driver_id=without, lat=HERE[0], lng=HERE[1]),
    ]

    class _NoSettings:
        async def scalar(self, *_a, **_k):
            return None

    kept = await destination.keep_heading(_NoSettings(), redis_client, ride=ride, ranked=ranked)
    assert [p.driver_id for p in kept] == [without]


async def test_the_daily_uses_come_from_the_panel_and_clearing_does_not_refund(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    headers = driver["headers"]
    put = {"lat": EAST[0], "lng": EAST[1], "label": "البيت"}

    shown = (await client.get("/drivers/me/destination", headers=headers)).json()
    assert shown["daily_uses"] == 2 and shown["uses_left"] == 2 and shown["lat"] is None

    first = await client.put("/drivers/me/destination", json=put, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["label"] == "البيت" and first.json()["uses_left"] == 1
    assert (await client.delete("/drivers/me/destination", headers=headers)).status_code == 204
    after = (await client.get("/drivers/me/destination", headers=headers)).json()
    assert after["lat"] is None and after["uses_left"] == 1, "الإلغاءُ لا يردّ مرّة"
    assert (await client.put("/drivers/me/destination", json=put, headers=headers)).status_code == 200
    third = await client.put("/drivers/me/destination", json=put, headers=headers)
    assert third.status_code == 422, third.text

    # **و`0` من اللوحة يطفئها في السوق**
    off = await client.patch(
        "/admin/settings/dispatch/JO", json={"destination_daily_uses": 0}, headers=admin_headers
    )
    assert off.status_code == 200, off.text
    assert off.json()["destination_daily_uses"] == 0
    refused = await client.put("/drivers/me/destination", json=put, headers=headers)
    assert refused.status_code == 422
