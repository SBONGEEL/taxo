"""السعةُ قبل فتح الجزائر (SPEC §٧٥-د/٢) — **اتصالٌ واحدٌ بـRedis لكلِّ عمليّة** يوزّع على مقابسها ويعود بعد السقوط · **إيقافُ التوزيع يبلغ
عمليّةً أخرى** · **خريطةُ الراكب بخلايا مشتركة** تعطي ما يعطيه الحسابُ المباشر حرفاً ولا تسأل القاعدةَ لكلِّ راكب."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.user import User
from app.services import dispatch, drivers as drivers_service
from app.ws import hub as hub_module
from app.ws.events import publish
from app.ws.hub import Subscription
from tests.helpers import (
    DRIVER,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    THIRD_DRIVER,
    approved_driver,
    bring_online,
    request_ride,
    rider_session,
    wait_for_offer,
    wait_until,
)


async def _pubsub_clients(redis) -> int:
    return sum(1 for c in await redis.client_list() if (c.get("sub") or "0") != "0" or (c.get("psub") or "0") != "0")


async def _next(sub: Subscription, timeout: float = 3.0) -> dict | None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        frame = await sub.poll(0.2)
        if frame is not None:
            return frame
    return None


async def test_many_sockets_share_one_redis_connection_and_each_gets_its_own_channels() -> None:
    redis = get_redis_client()
    before = await _pubsub_clients(redis)
    subs = [Subscription(redis) for _ in range(40)]
    for i, sub in enumerate(subs):
        await sub.subscribe("cap:shared")
        await sub.subscribe(f"cap:own:{i}")
    # **أربعون مقبساً — واتصالُ اشتراكٍ واحدٌ زائد** (كان أربعين)
    assert await _pubsub_clients(redis) - before <= 1

    await publish(redis, "cap:shared", {"type": "all"})
    await publish(redis, "cap:own:7", {"type": "only7"})
    got = [await _next(sub) for sub in subs]
    assert all(frame == {"type": "all"} for frame in got)
    assert await _next(subs[7]) == {"type": "only7"}
    assert await subs[8].poll(0.3) is None  # **قناةُ غيره لا تصله**

    # **العدّادُ لا الاشتراك**: يبقى مشتركاً ما بقي مقبسٌ واحد، ويُلغى مع آخرهم
    for sub in subs[1:]:
        await sub.close()
    assert (await redis.pubsub_numsub("cap:shared"))[0][1] == 1
    await publish(redis, "cap:shared", {"type": "still"})
    assert await _next(subs[0]) == {"type": "still"}
    await subs[0].close()
    assert (await redis.pubsub_numsub("cap:shared"))[0][1] == 0


async def test_the_shared_connection_comes_back_after_redis_drops_it() -> None:
    redis = get_redis_client()
    sub = Subscription(redis)
    await sub.subscribe("cap:survive")
    killed = await redis.client_kill_filter(_type="pubsub")
    assert killed >= 1
    # **يعود ويشترك من جديد** — رسالةٌ تُنشر بعد العودة تصل
    async def delivered() -> bool:
        await publish(redis, "cap:survive", {"type": "back"})
        return await sub.poll(0.5) == {"type": "back"}

    await wait_until(delivered, timeout=15, message="لم يعد المحورُ بعد سقوط اتصاله")
    await sub.close()


async def test_a_cancel_in_another_process_stops_the_search_there(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الإلغاءُ يصل عاملاً والتوزيعُ يجري في آخر** (§٧٥-د/٢) — `stop` بلا مهمّةٍ محلّيّة يرسل «قِف» فيخرج انتظارُ العرض فوراً."""
    driver = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-C1")
    await bring_online(client, driver)
    rider = await rider_session(client, RIDER)
    ride = await request_ride(client, rider["headers"])
    ride_id = uuid.UUID(ride["id"])
    await wait_for_offer(ride["id"], driver["driver_id"])
    task = dispatch._tasks.pop(ride_id)  # **كأنّها في عمليّةٍ أخرى**
    started = asyncio.get_running_loop().time()
    await dispatch.stop(ride_id)
    await asyncio.wait_for(task, timeout=5)
    # **خرجت بالإشارة لا بانقضاء مهلة العرض** (ثانيتان في الاختبار) — وبلا الإشارة تنتظرها ثمّ تعرض ثانيةً
    assert asyncio.get_running_loop().time() - started < 1.5


async def test_map_cells_give_exactly_the_direct_answer_and_spare_the_database(
    client: AsyncClient, jordan_settings: None, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis = get_redis_client()
    spots = [
        {"lat": PICKUP["lat"] + 0.004, "lng": PICKUP["lng"]},
        {"lat": PICKUP["lat"] - 0.009, "lng": PICKUP["lng"] + 0.006},
        {"lat": PICKUP["lat"] + 0.03, "lng": PICKUP["lng"] - 0.02},
    ]
    for payload, plate, spot in zip((DRIVER, SECOND_DRIVER, THIRD_DRIVER), ("AMM-M1", "AMM-M2", "AMM-M3"), spots, strict=True):
        driver = await approved_driver(client, session_factory, payload, plate_number=plate)
        await bring_online(client, driver, spot)
    rider = await rider_session(client, RIDER)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.id == uuid.UUID(str(rider["user"]["id"]))))

    calls = {"n": 0}
    real = dispatch.eligible_driver_ids

    async def counting(*args, **kwargs):
        calls["n"] += 1
        return await real(*args, **kwargs)

    monkeypatch.setattr(dispatch, "eligible_driver_ids", counting)
    points = [PICKUP, {"lat": PICKUP["lat"] + 0.002, "lng": PICKUP["lng"] - 0.003}, {"lat": PICKUP["lat"] - 0.004, "lng": PICKUP["lng"]}]
    for point in points:
        async with session_factory() as session:
            direct = await drivers_service.nearby_available(
                redis, session, country_code=user.country_code, lat=point["lat"], lng=point["lng"], rider=user
            )
        calls_before = calls["n"]
        async with session_factory() as session:
            celled = await drivers_service.nearby_for_map(
                redis, session, country_code=user.country_code, lat=point["lat"], lng=point["lng"], rider=user
            )
        assert [(p.driver_id, round(p.distance_km, 2)) for p in celled] == [(p.driver_id, round(p.distance_km, 2)) for p in direct]
        assert calls["n"] - calls_before <= 1
    # **الراكبُ الثاني والثالث في الخليّة نفسِها لا يسألان القاعدة**
    assert len(await redis.keys("nearby:cell:*")) >= 1
    cached = 0
    for point in points:
        before = calls["n"]
        async with session_factory() as session:
            await drivers_service.nearby_for_map(
                redis, session, country_code=user.country_code, lat=point["lat"], lng=point["lng"], rider=user
            )
        cached += calls["n"] == before
    assert cached == len(points)
    assert json.loads(await redis.get((await redis.keys("nearby:cell:*"))[0])) is not None


async def test_hub_shutdown_closes_the_shared_connection() -> None:
    redis = get_redis_client()
    sub = Subscription(redis)
    await sub.subscribe("cap:bye")
    await hub_module.shutdown()
    assert not hub_module._hubs
