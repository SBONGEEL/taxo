"""**أهدافُ الكبتن ومكافآتُها** (البند ١٦، §٩٧/١٦) — مطفأً لا شيء، ومشتعلاً تُصرف مرّةً إلى المحفظة ولا تتجاوز السقف."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.driver_goal import DriverGoalAward
from app.models.enums import FeatureKey, WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import driver_goals
from tests.helpers import NEAR_PICKUP, SECOND_DRIVER, approved_driver, bring_online, completed_ride, enable_features, rider_session


async def _goal(client: AsyncClient, admin_headers: dict, *, target: int = 1, reward: str = "5.000", cap: str = "5.000") -> dict:
    now = datetime.now(UTC)
    made = await client.post(
        "/admin/driver-goals",
        params={"country_code": "JO"},
        json={"title": "رحلةٌ واحدة", "target": target, "starts_at": (now - timedelta(hours=1)).isoformat(),
              "ends_at": (now + timedelta(days=1)).isoformat(), "reward_amount": reward, "budget_cap": cap},
        headers=admin_headers,
    )
    assert made.status_code == 201, made.text
    return made.json()


async def _rewards(session_factory, user_id: uuid.UUID) -> list[Decimal]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(WalletTransaction.amount).where(
                WalletTransaction.owner_id == user_id, WalletTransaction.type == WalletTransactionType.GOAL_REWARD
            )
        )
        return list(rows)


async def test_off_pays_nothing_and_on_pays_once(client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict) -> None:
    goal = await _goal(client, admin_headers)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver, NEAR_PICKUP)
    rider = await rider_session(client)
    await completed_ride(client, rider["headers"], driver)
    await client.post("/drivers/me/offline", headers=driver["headers"])
    user_id = uuid.UUID(str(driver["user_id"]))

    async with session_factory() as session:
        assert await driver_goals.sweep(session, get_redis_client()) == (0, 0)
    assert await _rewards(session_factory, user_id) == []
    off = (await client.get("/drivers/me/goals", headers=driver["headers"])).json()
    assert off["enabled"] is False and off["goals"] == [] and off["currency"]

    await enable_features(session_factory, FeatureKey.DRIVER_GOALS_ENABLED.value)
    mine = (await client.get("/drivers/me/goals", headers=driver["headers"])).json()
    assert mine["enabled"] is True and mine["goals"][0]["done"] == 1 and mine["goals"][0]["rewarded"] is False
    async with session_factory() as session:
        paid, _ = await driver_goals.sweep(session, get_redis_client())
    assert paid == 1
    async with session_factory() as session:
        assert await driver_goals.sweep(session, get_redis_client()) == (0, 0)
    assert await _rewards(session_factory, user_id) == [Decimal("5.000")]
    listed = (await client.get("/admin/driver-goals", params={"country_code": "JO"}, headers=admin_headers)).json()
    assert [(g["id"], g["awards"], g["spent"]) for g in listed] == [(goal["id"], 1, "5.000")]


async def test_amounts_follow_the_currency_and_the_cap_covers_one(client: AsyncClient, admin_headers: dict) -> None:
    now = datetime.now(UTC)
    body = {"title": "هدف", "target": 3, "starts_at": now.isoformat(), "ends_at": (now + timedelta(days=1)).isoformat(),
            "reward_amount": "5.000", "budget_cap": "4.000"}
    low = await client.post("/admin/driver-goals", params={"country_code": "JO"}, json=body, headers=admin_headers)
    assert low.status_code == 422
    dz = await client.post("/admin/driver-goals", params={"country_code": "DZ"},
                           json={**body, "reward_amount": "100.500", "budget_cap": "1000"}, headers=admin_headers)
    assert dz.status_code == 422


async def test_award_refuses_above_the_cap(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    goal = await _goal(client, admin_headers, reward="5.000", cap="5.000")
    await enable_features(session_factory, FeatureKey.DRIVER_GOALS_ENABLED.value)
    first = await approved_driver(client, session_factory)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-4243")
    async with session_factory() as session:
        assert await driver_goals.award(session, None, goal_id=uuid.UUID(goal["id"]), driver_id=uuid.UUID(str(first["driver_id"])))
    async with session_factory() as session:
        assert not await driver_goals.award(session, None, goal_id=uuid.UUID(goal["id"]), driver_id=uuid.UUID(str(second["driver_id"])))
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(DriverGoalAward))
    assert count == 1
