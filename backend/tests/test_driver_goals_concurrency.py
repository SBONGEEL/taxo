"""**تزامنُ صرف مكافأة الهدف** (البند ١٦) — `driver_goals.award` يقفل صفَّ الهدف قبل قراءة المصروف.

**يسقط بحذف القفل**: بلا `with_for_update` في `driver_goals.locked` يقرأ صرفان لكبتنين مختلفين المصروفَ صفراً معاً فيُصرفان كلاهما
فوق سقفٍ يسع واحدةً — ولا يمسكه القيدُ الفريد (كبتنان) ولا مفتاحُ عدم التكرار (مفتاحان).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver_goal import DriverGoalAward
from app.models.enums import FeatureKey
from app.services import driver_goals
from tests.helpers import SECOND_DRIVER, approved_driver, enable_features


async def test_two_awards_at_once_stay_under_the_cap(client: AsyncClient, session_factory, admin_headers: dict, monkeypatch) -> None:
    now = datetime.now(UTC)
    made = await client.post(
        "/admin/driver-goals",
        params={"country_code": "JO"},
        json={"title": "هدف", "target": 1, "starts_at": (now - timedelta(hours=1)).isoformat(),
              "ends_at": (now + timedelta(days=1)).isoformat(), "reward_amount": "5.000", "budget_cap": "5.000"},
        headers=admin_headers,
    )
    goal_id = uuid.UUID(made.json()["id"])
    await enable_features(session_factory, FeatureKey.DRIVER_GOALS_ENABLED.value)
    first = await approved_driver(client, session_factory)
    second = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-4243")

    # **التداخلُ مفروضٌ لا مأمول**: الأوّلُ يبقي معاملته مفتوحةً بعد قراءة المصروف، فيبدأ الثاني وهو في منتصفه
    real_spent = driver_goals.spent

    async def slow_spent(session, gid):
        found = await real_spent(session, gid)
        await asyncio.sleep(0.4)
        return found

    monkeypatch.setattr(driver_goals, "spent", slow_spent)

    async def pay(driver: dict) -> bool:
        async with session_factory() as session:
            return await driver_goals.award(session, None, goal_id=goal_id, driver_id=uuid.UUID(str(driver["driver_id"])))

    results = await asyncio.wait_for(asyncio.gather(pay(first), pay(second)), timeout=30)
    assert sorted(results) == [False, True]
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DriverGoalAward)) == 1
