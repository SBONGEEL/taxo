"""بثُّ موقع الكبتن المتكيّف (SPEC §٧٥-ج) — الطورُ الآليُّ بلا تذبذب، والمهلةُ متّسقة، ودفعاتُ الرحلة لا تُقصِّر المسافة، والتوزيعُ يختار
الأقربَ حقّاً بمواقعَ قديمة."""

from __future__ import annotations

import asyncio
import importlib
import math
import time
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.broadcast import BroadcastChange, BroadcastSettings
from app.models.ride import RideRoutePoint
from app.services import broadcast, geo, live_map, route
from app.ws.hub import Subscription
from tests.conftest import ws_client
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    bring_online,
    request_ride,
    rider_session,
    started_ride,
    wait_for_offer,
    wait_until,
)

WS_DRIVER = "http://test/api/v1/ws/driver"
STEPS = broadcast.DEFAULT_STEPS


@pytest.fixture(autouse=True)
def _fresh_policy_cache():
    broadcast.forget_cache()
    yield
    broadcast.forget_cache()


async def _frame(sub: Subscription, timeout: float = 3.0) -> dict | None:
    """أوّلُ إطارٍ في المهلة — **و`poll` يعيد `None` لرسالة تأكيد الاشتراك** فلا يُقرأ أوّلُ `None` صمتاً."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        frame = await sub.poll(0.2)
        if frame is not None:
            return frame
    return None


async def _receive(ws, *, of_type: str, timeout: float = 10.0) -> dict:
    async def _read() -> dict:
        while True:
            message = await ws.receive_json()
            if message.get("type") == of_type:
                return message

    return await asyncio.wait_for(_read(), timeout=timeout)


# ------------------------------------------------------------------ الدرجات


def test_bands_step_up_at_once_and_down_only_with_margin_and_dwell() -> None:
    assert [broadcast.band_of(n, STEPS) for n in (0, 1000, 1001, 2000, 2001, 3000, 3001, 99_999)] == [0, 0, 1, 1, 2, 2, 3, 3]
    # **الصعودُ فوريّ** ولو بلا مُكث
    assert broadcast.next_band(0, 1001, STEPS, dwell_ok=False) == 1
    assert broadcast.next_band(1, 3500, STEPS, dwell_ok=False) == 3
    # **ولا تذبذب حول العتبة**: عددٌ يتأرجح حول الألف يبقى على ٢٠
    for online in (999, 1001, 995, 1003, 960, 930, 901, 900):
        assert broadcast.next_band(1, online, STEPS, dwell_ok=True) == 1, online
    # النزولُ بالهامش **والمُكث معاً**
    assert broadcast.next_band(1, 899, STEPS, dwell_ok=False) == 1
    assert broadcast.next_band(1, 899, STEPS, dwell_ok=True) == 0
    # ومن ٤٥ إلى ١٥ مباشرةً إن هبط العددُ كلُّه
    assert broadcast.next_band(3, 100, STEPS, dwell_ok=True) == 0


def test_the_presence_timeout_outlasts_every_interval_plus_the_heartbeat() -> None:
    """**كبتنٌ ساكنٌ أو بطيءُ الإرسال لا يُعدّ غيرَ متّصلٍ أبداً** — المهلةُ أطولُ من كلِّ فاصلٍ ومعه النبضة، في كلِّ درجةٍ وحدَّيها."""
    for seconds in [step["seconds"] for step in STEPS] + [15, 45]:
        policy = broadcast.Policy(
            mode="automatic", available_seconds=seconds, heading_seconds=10, trip_send_seconds=15,
            trip_record_seconds=2, move_meters=30, heartbeat_seconds=60,
        )
        assert policy.presence_ttl > policy.heartbeat_seconds + policy.available_seconds
        assert policy.presence_ttl > policy.heartbeat_seconds + policy.trip_send_seconds
    assert broadcast.clamp(5) == 15 and broadcast.clamp(90) == 45


def test_the_beat_cycle_is_the_service_cycle() -> None:
    celery_module = importlib.import_module("app.tasks.celery_app")
    assert celery_module.BROADCAST_TICK_SECONDS == broadcast.TICK_SECONDS
    assert "broadcast-tick" in celery_module.celery_app.conf.beat_schedule


async def test_automatic_mode_walks_up_and_down_the_table_without_touching_the_settings_row(
    session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """١٥ ← ٢٠ ← ٣٠ ← ٤٥ وعودة — **كلُّ تغييرٍ سطرٌ في السجلّ، والنشرُ للكباتن، وصفُّ الإعدادات لا يُمسّ**."""
    redis = get_redis_client()
    online = {"n": 10}

    async def fake_count(_redis) -> int:
        return online["n"]

    monkeypatch.setattr(broadcast, "count_online", fake_count)
    async with session_factory() as session:
        row = await broadcast.get_settings(session)
        await session.commit()
        stamp = row.updated_at

    frames: list[int] = []
    async with Subscription(redis) as sub:
        await sub.subscribe(broadcast.CHANNEL)
        clock = 1_000_000.0
        plan = [
            (10, 15), (1001, 20), (1500, 20), (2001, 30), (3001, 45), (5000, 45),
            # النزول: لا قبل المُكث، ولا بلا هامش
            (2900, 45), (2600, 45), (2600, 30), (1950, 30), (1700, 20), (950, 20), (850, 15),
        ]
        dwell = {7: 0, 8: broadcast.MIN_DWELL_SECONDS, 9: 0, 10: broadcast.MIN_DWELL_SECONDS, 11: 0, 12: broadcast.MIN_DWELL_SECONDS}
        for index, (count, expected) in enumerate(plan):
            online["n"] = count
            clock += dwell.get(index, 30)
            async with session_factory() as session:
                policy = await broadcast.apply(session, redis, now=clock)
                await session.commit()
            assert policy.available_seconds == expected, (index, count, policy.available_seconds)
            if (frame := await _frame(sub, 0.6)) is not None:
                frames.append(frame["available_seconds"])

    async with session_factory() as session:
        changes = list(await session.scalars(select(BroadcastChange).order_by(BroadcastChange.created_at)))
        row = await session.scalar(select(BroadcastSettings))
    assert [(c.old_seconds, c.new_seconds) for c in changes] == [
        (None, 15), (15, 20), (20, 30), (30, 45), (45, 30), (30, 20), (20, 15),
    ], [(c.old_seconds, c.new_seconds, c.created_at.isoformat()) for c in changes]
    assert all(c.source == "automatic" for c in changes)
    assert frames == [15, 20, 30, 45, 30, 20, 15]
    # **الطورُ الآليُّ لا يكتب إعداداً أبداً**
    assert row.updated_at == stamp and row.available_seconds == 15 and row.mode == "automatic"


async def test_manual_mode_uses_the_admin_value_and_the_admin_change_reaches_drivers_live(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    redis = get_redis_client()
    async with Subscription(redis) as sub:
        await sub.subscribe(broadcast.CHANNEL)
        response = await client.patch(
            "/admin/settings/broadcast",
            json={"mode": "manual", "available_seconds": 40, "move_meters": 50},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["live"]["mode"] == "manual" and body["live"]["available_seconds"] == 40
        assert body["live"]["presence_ttl"] == 60 + 40 + broadcast.GRACE_SECONDS
        frame = await _frame(sub)
        assert frame is not None and frame["type"] == "broadcast_policy" and frame["available_seconds"] == 40 and frame["move_meters"] == 50
    assert body["changes"][0]["source"] == "admin" and body["changes"][0]["new_seconds"] == 40

    # **الحدّان الصلبان**، والدرجاتُ تصاعديّةٌ آخرُها بلا حدّ، ونقطةُ الرحلة أقصرُ من نصف دفعتها
    for bad in (
        {"available_seconds": 10},
        {"available_seconds": 50},
        {"auto_steps": [{"max_online": 2000, "seconds": 20}, {"max_online": 1000, "seconds": 30}, {"max_online": None, "seconds": 45}]},
        {"auto_steps": [{"max_online": 1000, "seconds": 15}]},
        {"auto_steps": [{"max_online": None, "seconds": 60}]},
        {"trip_record_seconds": 10, "trip_send_seconds": 15},
    ):
        rejected = await client.patch("/admin/settings/broadcast", json=bad, headers=admin_headers)
        assert rejected.status_code == 422, (bad, rejected.text)


# ------------------------------------------------------------------ مسافةُ الأجرة


def _curve(points: int = 90, *, every_ms: int = 2000) -> list[route.TripPoint]:
    """طريقٌ بمنعطفات — قوسٌ ثمّ زاويةٌ ثمّ قوس، نقطةٌ كلَّ ثانيتين بسرعة ~٤٠ كم/س (~٢٢ م بين النقطتين)."""
    out: list[route.TripPoint] = []
    lat, lng = NEAR_PICKUP["lat"], NEAR_PICKUP["lng"]
    for i in range(points):
        bearing = math.radians((i * 6) % 360)  # يلفّ دورةً كاملةً كلَّ ٦٠ نقطة
        lat += 0.0002 * math.cos(bearing)
        lng += 0.0002 * math.sin(bearing)
        out.append(route.TripPoint(lat=lat, lng=lng, heading=None, t=1_700_000_000_000 + i * every_ms))
    return out


async def _trip(client: AsyncClient, session_factory, payload=DRIVER, plate="AMM-9") -> tuple[dict, str]:
    driver = await approved_driver(client, session_factory, payload, plate_number=plate)
    await bring_online(client, driver)
    rider = await rider_session(client, RIDER)
    ride = await started_ride(client, rider["headers"], driver)
    return driver, ride["id"]


async def _distance(session_factory, ride_id: str) -> Decimal | None:
    async with session_factory() as session:
        return await route.actual_distance_km(session, uuid.UUID(ride_id))


async def test_batches_and_single_points_give_the_same_trip_distance(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**المسارُ نفسُه بمنعطفاته**: نقاطُ ثانيتين واحدةً واحدةً مقابلَ دفعات ١٥ ثانية **يجب أن تتطابق** — ولا تقصر عن طول الطريق."""
    redis = get_redis_client()
    path = _curve()
    driver, ride_id = await _trip(client, session_factory)
    driver_id = uuid.UUID(str(driver["driver_id"]))

    clock = time.time()
    for seq, start in enumerate(range(0, len(path), 7)):
        chunk = path[start:start + 7]
        assert await route.capture_points(redis, driver_id=driver_id, points=chunk, seq=seq, received_at=clock + seq * 15)
    batched = await _distance(session_factory, ride_id)

    async with session_factory() as session:
        for row in await session.scalars(select(RideRoutePoint).where(RideRoutePoint.ride_id == uuid.UUID(ride_id))):
            await session.delete(row)
        await session.commit()
    await redis.delete(route.tail_key(ride_id))
    for seq, point in enumerate(path):
        assert await route.capture_points(redis, driver_id=driver_id, points=[point], seq=seq, received_at=clock + seq * 2)
    single = await _distance(session_factory, ride_id)

    true_km = sum(
        route._meters(a.lat, a.lng, b.lat, b.lng) for a, b in zip(path, path[1:], strict=False)
    ) / 1000
    assert batched == single
    # **ولا تقصر عن طول الطريق** — والفرقُ الباقي فرقُ الكرة (هنا) والإهليلج (PostGIS)، دون نصفٍ بالمئة
    assert abs(float(batched) - true_km) / true_km < 0.005, (batched, true_km)


async def test_a_resent_batch_is_acknowledged_but_not_written_twice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    redis = get_redis_client()
    driver, ride_id = await _trip(client, session_factory)
    driver_id = uuid.UUID(str(driver["driver_id"]))
    path = _curve(20)
    assert await route.capture_points(redis, driver_id=driver_id, points=path[:10], seq=1)
    assert await route.capture_points(redis, driver_id=driver_id, points=path[10:], seq=2)
    once = await _distance(session_factory, ride_id)
    # الدفعتان تُعادان بعد انقطاع — مقبولتان، ولا تُكتبان ثانية
    assert await route.capture_points(redis, driver_id=driver_id, points=path[:10], seq=1)
    assert await route.capture_points(redis, driver_id=driver_id, points=path[10:], seq=2)
    assert await _distance(session_factory, ride_id) == once
    async with session_factory() as session:
        count = len(list(await session.scalars(select(RideRoutePoint.id).where(RideRoutePoint.ride_id == uuid.UUID(ride_id)))))
    assert count <= 20


async def test_gps_jitter_at_a_red_light_is_not_billed(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**رجفةُ GPS دون خمسة أمتار لا تُكتب** — وزحفٌ بطيءٌ يُكتب حين يبلغها مجموعُه."""
    redis = get_redis_client()
    driver, ride_id = await _trip(client, session_factory)
    driver_id = uuid.UUID(str(driver["driver_id"]))
    base = NEAR_PICKUP
    jitter = [
        route.TripPoint(lat=base["lat"] + (0.00002 if i % 2 else -0.00002), lng=base["lng"], heading=None, t=i * 2000)
        for i in range(30)
    ]
    assert await route.capture_points(redis, driver_id=driver_id, points=jitter, seq=1)
    assert await _distance(session_factory, ride_id) is None  # نقطةٌ واحدة — الرجفةُ كلُّها ~٤٫٤ م
    creep = [route.TripPoint(lat=base["lat"] + i * 0.00001, lng=base["lng"], heading=None, t=60_000 + i * 2000) for i in range(1, 30)]
    assert await route.capture_points(redis, driver_id=driver_id, points=creep, seq=2)
    km = await _distance(session_factory, ride_id)
    assert km is not None and abs(float(km) - 0.032) < 0.006, km


# ------------------------------------------------------------------ المقبس


async def test_the_socket_carries_the_policy_acks_batches_and_takes_heartbeats(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    redis = get_redis_client()
    driver, ride_id = await _trip(client, session_factory)
    async with ws_client() as sockets:
        async with aconnect_ws(f"{WS_DRIVER}?token={driver['token']}", client=sockets) as ws:
            connected = await _receive(ws, of_type="connected")
            assert connected["broadcast"]["available_seconds"] == 15
            assert connected["broadcast"]["trip_record_seconds"] == 2
            assert connected["broadcast"]["presence_ttl"] == 60 + 15 + broadcast.GRACE_SECONDS

            points = [{"lat": p.lat, "lng": p.lng, "heading": 90, "t": p.t} for p in _curve(8)]
            await ws.send_json({"type": "locations", "seq": 7, "points": points})
            assert (await _receive(ws, of_type="points_ack"))["seq"] == 7
            assert await _distance(session_factory, ride_id) is not None

            # النبضة تجدّد العمرَ ولا تمسّ الموقع
            key = geo.presence_key(driver["driver_id"])
            await redis.expire(key, 5)
            at_before = await redis.hget(key, "at")
            await ws.send_json({"type": "heartbeat"})
            await wait_until(lambda: _ttl_above(redis, key, 60), message="النبضةُ لم تجدّد العمر")
            assert await redis.hget(key, "at") == at_before

            # وحضورٌ انقضى: النبضةُ تطلب موقعاً
            await redis.delete(key)
            await ws.send_json({"type": "heartbeat"})
            await _receive(ws, of_type="location_request")


async def _ttl_above(redis, key: str, floor: int) -> bool:
    return (await redis.ttl(key)) > floor


async def test_the_rest_fallback_takes_a_batch_and_serves_the_policy(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver, ride_id = await _trip(client, session_factory)
    points = [{"lat": p.lat, "lng": p.lng, "heading": None, "t": p.t} for p in _curve(8)]
    response = await client.post("/drivers/me/locations", json={"seq": 3, "points": points}, headers=driver["headers"])
    assert response.status_code == 200, response.text
    assert response.json() == {"seq": 3}
    policy = await client.get("/drivers/me/broadcast", headers=driver["headers"])
    assert policy.status_code == 200 and policy.json()["heading_seconds"] == 10


async def test_stale_means_silent_not_still(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**الساكنُ حاضر**: موقعُه قديمٌ ونبضتُه حديثة فلا «يشحب» على خريطة الإشراف — **ومن صمت يشحب**."""
    redis = get_redis_client()
    driver = await approved_driver(client, session_factory, plate_number="AMM-7")
    await bring_online(client, driver)
    key = geo.presence_key(driver["driver_id"])
    now = int(time.time())
    await redis.hset(key, mapping={"at": str(now - 600), "seen": str(now - 5)})
    position = await live_map.position_of(redis, driver_id=uuid.UUID(str(driver["driver_id"])), country=geo.CountryCode.JO)
    assert position.seconds_since_update >= 600 and position.stale is False
    await redis.hset(key, "seen", str(now - 200))
    position = await live_map.position_of(redis, driver_id=uuid.UUID(str(driver["driver_id"])), country=geo.CountryCode.JO)
    assert position.stale is True


# ------------------------------------------------------------------ التوزيع


async def test_dispatch_refreshes_stale_positions_and_offers_the_truly_nearest(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**المخزَّنُ قديمٌ ومضلِّل**: «أ» مخزَّنٌ أقربَ وهو الآن بعيد، و«ب» مخزَّنٌ أبعدَ وهو الآن عند الراكب — **فيُعرض على «ب»**."""
    redis = get_redis_client()
    near_a = {"lat": PICKUP["lat"] + 0.004, "lng": PICKUP["lng"]}  # ~٤٤٥ م
    near_b = {"lat": PICKUP["lat"] + 0.009, "lng": PICKUP["lng"]}  # ~١ كم
    a = await approved_driver(client, session_factory, DRIVER, plate_number="AMM-A")
    b = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-B")
    truly = {
        str(a["driver_id"]): {"lat": PICKUP["lat"] + 0.025, "lng": PICKUP["lng"]},  # ~٢٫٨ كم
        str(b["driver_id"]): {"lat": PICKUP["lat"] + 0.0005, "lng": PICKUP["lng"]},  # ~٥٥ م
    }
    rider = await rider_session(client, RIDER)

    async def answer(ws, driver: dict) -> None:
        while True:
            message = await ws.receive_json()
            if message.get("type") == "location_request":
                await ws.send_json({"type": "location", **truly[str(driver["driver_id"])], "heading": 0})

    async with ws_client() as sockets:
        async with (
            aconnect_ws(f"{WS_DRIVER}?token={a['token']}", client=sockets) as ws_a,
            aconnect_ws(f"{WS_DRIVER}?token={b['token']}", client=sockets) as ws_b,
        ):
            await _receive(ws_a, of_type="connected")
            await _receive(ws_b, of_type="connected")
            await ws_a.send_json({"type": "location", **near_a, "heading": 0})
            await ws_b.send_json({"type": "location", **near_b, "heading": 0})
            for driver in (a, b):
                await wait_until(lambda d=driver: redis.hget(geo.presence_key(d["driver_id"]), "at"))
                await redis.hset(geo.presence_key(driver["driver_id"]), "at", str(int(time.time()) - 40))
            listeners = [asyncio.create_task(answer(ws_a, a)), asyncio.create_task(answer(ws_b, b))]
            try:
                ride = await request_ride(client, rider["headers"])
                offered = await wait_for_offer(ride["id"])
            finally:
                for task in listeners:
                    task.cancel()
    assert str(offered) == str(b["driver_id"])
