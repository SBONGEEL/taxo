"""إنذارُ السعة (SPEC §٧٦/٢) — **العدُّ، والعتبتان من اللوحة، وإشعارُ المشرفين مرّةً كلَّ نصف ساعة**."""

from __future__ import annotations

import time

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.notification import UserNotification
from app.services import capacity

pytestmark = pytest.mark.asyncio


async def _riders(redis, count: int, *, age: float = 0.0) -> None:
    now = time.time() - age
    await redis.zadd(capacity.RIDERS_KEY, {f"r-{i}-{age}": now for i in range(count)})


async def _inbox(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(UserNotification)))


async def test_riders_online_counts_the_fresh_and_drops_the_stale() -> None:
    redis = get_redis_client()
    await _riders(redis, 3)
    await _riders(redis, 2, age=capacity.RIDER_STALE_SECONDS + 5)
    assert await capacity.riders_online(redis) == 3
    # **والبائتُ يُكنس من المجموعة نفسِها** لا يُتجاوز في العدّ وحسب
    assert await redis.zcard(capacity.RIDERS_KEY) == 3


async def test_mark_and_drop_a_rider() -> None:
    import uuid

    redis = get_redis_client()
    rider = uuid.uuid4()
    await capacity.mark_rider(redis, rider)
    await capacity.mark_rider(redis, rider)  # الإنعاشُ لا يكرّر العدّ
    assert await capacity.riders_online(redis) == 1
    await capacity.drop_rider(redis, rider)
    assert await capacity.riders_online(redis) == 0


async def test_the_panel_sees_counts_and_editable_thresholds(client: AsyncClient, admin_headers) -> None:
    redis = get_redis_client()
    await _riders(redis, 4)
    live = (await client.get("/admin/stats/capacity", headers=admin_headers)).json()
    assert live["riders"] == 4 and live["captains"] == 0
    assert (live["alert_captains"], live["alert_riders"]) == (250, 500)
    assert live["alerting"] is False

    patched = await client.patch(
        "/admin/settings/broadcast", json={"alert_riders": 4, "alert_captains": 300}, headers=admin_headers
    )
    assert patched.status_code == 200, patched.text
    assert (patched.json()["alert_captains"], patched.json()["alert_riders"]) == (300, 4)

    live = (await client.get("/admin/stats/capacity", headers=admin_headers)).json()
    assert live["riders_alerting"] is True and live["captains_alerting"] is False and live["alerting"] is True


async def test_thresholds_must_be_positive(client: AsyncClient, admin_headers) -> None:
    refused = await client.patch("/admin/settings/broadcast", json={"alert_riders": 0}, headers=admin_headers)
    assert refused.status_code == 422


async def test_below_the_threshold_nobody_is_alerted(client: AsyncClient, admin_headers, session_factory) -> None:
    redis = get_redis_client()
    await _riders(redis, 3)
    async with session_factory() as session:
        snap = await capacity.check(session, redis)
        await session.commit()
    assert snap.alerting is False
    assert await _inbox(session_factory) == 0


async def test_reaching_the_threshold_alerts_admins_once_per_half_hour(
    client: AsyncClient, admin_headers, session_factory
) -> None:
    redis = get_redis_client()
    await client.patch("/admin/settings/broadcast", json={"alert_riders": 3}, headers=admin_headers)
    await _riders(redis, 3)

    async with session_factory() as session:
        first = await capacity.check(session, redis)
        await session.commit()
    assert first.alerting and first.last_alert_at is not None
    assert await _inbox(session_factory) == 1  # مشرفٌ واحدٌ في الاختبار

    async with session_factory() as session:
        row = await session.scalar(select(UserNotification))
    assert row.title == "السعةُ قاربت حدَّها" and "3 راكباً متّصلاً" in row.body

    async with session_factory() as session:
        await capacity.check(session, redis)
        await session.commit()
    assert await _inbox(session_factory) == 1  # **لا يتكرّر داخل نصف الساعة**

    await redis.delete(capacity.ALERT_COOLDOWN_KEY)
    async with session_factory() as session:
        await capacity.check(session, redis)
        await session.commit()
    assert await _inbox(session_factory) == 2  # وبعدها يعود إن بقي العددُ فوق العتبة

    live = (await client.get("/admin/stats/capacity", headers=admin_headers)).json()
    assert live["last_alert_at"] is not None
