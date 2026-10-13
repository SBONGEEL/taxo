"""تخطّي Mapbox لحسابات الحمل وحدَها حين يُشعَل المفتاح (SPEC §٧٥) — **وما عداها كما كان حرفاً، وكلُّ نداءٍ حقيقيٍّ يُعدّ**."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.redis_client import get_redis_client
from app.models.user import User
from app.services import directions, stress
from tests.helpers import PICKUP, DROPOFF, RIDER, rider_session

pytestmark = pytest.mark.asyncio


@pytest.fixture
def route_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """**يعدّ نداءاتِ المزوّد** فوق بديله القائم (`stub_mapbox`) — فيُقاس «لا نداء» لا يُفترض."""
    calls: list[int] = []
    inner = directions.fetch_route

    async def counted(*args, **kwargs):
        calls.append(1)
        return await inner(*args, **kwargs)

    monkeypatch.setattr(directions, "fetch_route", counted)
    return calls


async def _tag(session_factory, user_id: str) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == uuid.UUID(user_id)).values(is_test=True))
        await session.commit()


async def _estimate(client: AsyncClient, headers: dict) -> dict:
    response = await client.post(
        "/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_only_a_tagged_stress_account_skips_mapbox_and_only_while_switched_on(
    client: AsyncClient, session_factory, jordan_settings: None, route_calls: list[int]
) -> None:
    redis = get_redis_client()
    await redis.delete(stress.SWITCH_KEY, stress.STUB_COUNT_KEY)
    stressed = await rider_session(client, RIDER | {"phone": "0719500001", "name": "حملٌ 1"})
    await _tag(session_factory, stressed["user"]["id"])
    other_test = await rider_session(client, RIDER | {"phone": "0790000777", "name": "تجربةٌ أخرى"})
    await _tag(session_factory, other_test["user"]["id"])
    untagged = await rider_session(client, RIDER | {"phone": "0719500002", "name": "رقمٌ في النطاق بلا وسم"})

    # **مطفأً: لا يتغيّر شيءٌ لأحد** — ولا لحساب الحمل نفسِه
    await _estimate(client, stressed["headers"])
    assert len(route_calls) == 1

    await redis.set(stress.SWITCH_KEY, "1", ex=60)
    try:
        body = await _estimate(client, stressed["headers"])
        assert len(route_calls) == 1 and body["estimated_fare"]
        assert int(await redis.get(stress.STUB_COUNT_KEY)) == 1
        # **والمفتاحُ لا يمسّ غيرَه**: حسابُ تجربةٍ خارج النطاق، ورقمٌ في النطاق بلا وسم
        await _estimate(client, other_test["headers"])
        await _estimate(client, untagged["headers"])
        assert len(route_calls) == 3
    finally:
        await redis.delete(stress.SWITCH_KEY, stress.STUB_COUNT_KEY)

    await _estimate(client, stressed["headers"])
    assert len(route_calls) == 4


async def test_every_real_mapbox_call_is_counted() -> None:
    redis = get_redis_client()
    key = stress.calls_key()
    before = int(await redis.get(key) or 0)
    await directions._count_call()
    assert int(await redis.get(key)) == before + 1
