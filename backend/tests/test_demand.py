"""«الطلب مرتفع» حول الكبتن — `GET /drivers/me/demand` (§٦٢-ج/٤٣، C04).

**ما يُسأل هنا**: ثلاثةُ طلباتٍ في ثلاثة كيلومترات خلال ربع ساعةٍ ولا كبتنَ متاحاً سواه ⇐ **مرتفع**؛ وطلبان، أو طلبٌ خرج من
النافذة، أو كبتنٌ بعيدٌ أو صامت ⇐ **لا**. **والجوابُ نعم/لا وحدَها** — لا عددَ يُقرأ منه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import update

from app.models.ride import Ride
from tests.helpers import (
    FAR_PICKUP,
    OTHER_RIDER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    register,
    request_ride,
)

THIRD_RIDER = RIDER | {"phone": "0796666666", "name": "راكبة ثالثة"}


async def _demand(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/drivers/me/demand", headers=driver["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def _requests(client: AsyncClient, *riders: dict) -> list[dict]:
    return [await request_ride(client, auth(await register(client, rider))) for rider in riders]


async def test_three_requests_and_no_other_captain_is_high(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    await _requests(client, RIDER, OTHER_RIDER, THIRD_RIDER)

    body = await _demand(client, driver)
    # **نعم/لا وحدَها** — لا عددَ ولا موضعَ في الجواب
    assert body == {"high": True}


async def test_two_requests_or_one_outside_the_window_is_not(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """طلبان لا يكفيان؛ **وطلبٌ قبل عشرين دقيقةً خارجُ النافذة** — فثلاثةٌ أحدُها قديمٌ طلبان."""
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rides = await _requests(client, RIDER, OTHER_RIDER)
    assert (await _demand(client, driver))["high"] is False

    rides += await _requests(client, THIRD_RIDER)
    assert (await _demand(client, driver))["high"] is True

    async with session_factory() as session:
        await session.execute(
            update(Ride)
            .where(Ride.id == uuid.UUID(rides[0]["id"]))
            .values(created_at=datetime.now(UTC) - timedelta(minutes=20))
        )
        await session.commit()
    assert (await _demand(client, driver))["high"] is False


async def test_a_far_or_silent_captain_reads_no(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الدائرةُ حول موقعه المبثوث**: بعيدٌ عن الطلبات ⇐ لا؛ **وبلا بثٍّ حيٍّ ⇐ لا** — من لا يستقبل لا طلبَ «حوله»."""
    silent = await approved_driver(client, session_factory)
    assert (await _demand(client, silent))["high"] is False

    await bring_online(client, silent, FAR_PICKUP)
    await _requests(client, RIDER, OTHER_RIDER, THIRD_RIDER)
    assert (await _demand(client, silent))["high"] is False


async def test_a_rider_has_no_demand_door(client: AsyncClient, jordan_settings: None) -> None:
    rider = auth(await register(client, RIDER))
    response = await client.get("/drivers/me/demand", headers=rider)
    assert response.status_code == 403
