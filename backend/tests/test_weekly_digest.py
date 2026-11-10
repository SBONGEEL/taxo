"""**ملخّصُ أسبوع الكبتن** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٧)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.driver import Driver
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    enable_features,
    pay_ride,
    rider_session,
    topup_wallet,
)

pytestmark = pytest.mark.asyncio


async def test_last_week_counts_the_ride_its_hour_and_compares_with_the_week_before(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    from app.services import weekly_digest

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await enable_features(session_factory, "wallet_enabled")
    account = await rider_session(client)
    rider = account["headers"]
    await topup_wallet(client, admin_headers, account["user"]["id"], "50.000")
    ride = await completed_ride(client, rider, driver)
    paid = await pay_ride(client, rider, ride["id"], "wallet")
    assert paid.status_code in (200, 201), paid.text

    # **الشاشةُ اليومَ لا ترى رحلةَ اليوم** — الأسبوعُ ينتهي بأمس
    today = (await client.get("/drivers/me/earnings/weekly", headers=driver["headers"])).json()
    assert today["completed_rides"] == 0 and today["best_hours"] == []
    assert today["rating_count"] == 0 and today["rating_average"] is None

    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        digest = await weekly_digest.weekly(
            session, driver=row, user_id=row.user_id, country=_jo(), now=tomorrow
        )
    assert digest.completed_rides == 1 and digest.previous_rides == 0
    assert digest.earned > 0 and digest.previous_earned == 0
    assert digest.earned_change_percent is None, "لا أساسَ للمقارنة بأسبوعٍ صفر"
    assert len(digest.best_hours) == 1 and digest.best_hours[0].rides == 1
    assert digest.best_day is not None


async def test_the_saturday_push_goes_once_per_captain(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    from app.core.redis_client import get_redis_client
    from app.tasks import weekly_digest as task

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = (await rider_session(client))["headers"]
    await completed_ride(client, rider, driver)

    first = await task._send()
    again = await task._send()
    assert first == 1 and again == 0, "مرّةً في الأسبوع ولو أُعيد beat"
    keys = [key async for key in get_redis_client().scan_iter("digest:weekly:*")]
    assert len(keys) == 1


def _jo():
    from app.models.enums import CountryCode

    return CountryCode.JO
