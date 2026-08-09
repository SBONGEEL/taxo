"""التتبع اللحظي عبر WebSocket (SPEC القسم 10).

المقابس تُفتح على نفس تطبيق ASGI وفي نفس حلقة الأحداث عبر `httpx-ws`، فما
يُختبر هنا هو السلوك الحقيقي لا محاكاته.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from httpx_ws import HTTPXWSException, aconnect_ws

from app.core.redis_client import get_redis_client
from app.services import geo
from tests.conftest import ws_client
from tests.helpers import (
    NEAR_PICKUP,
    PICKUP,
    RIDER,
    approved_driver,
    auth,
    register,
    request_ride,
    token_of,
    wait_for_offer,
    wait_until,
)

WS_RIDER = "http://test/api/v1/ws/rider"
WS_DRIVER = "http://test/api/v1/ws/driver"

# مهلة انتظار رسالة واحدة — أسخى من دورة بثّ الجيران (5 ثوانٍ)
RECEIVE_TIMEOUT = 12.0


async def _receive(ws, *, of_type: str | None = None) -> dict:
    """أول رسالة (أو أول رسالة من نوع بعينه) خلال المهلة."""

    async def _read() -> dict:
        while True:
            message = await ws.receive_json()
            if of_type is None or message.get("type") == of_type:
                return message

    return await asyncio.wait_for(_read(), timeout=RECEIVE_TIMEOUT)


async def _rider_session(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "token": token_of(body)}


async def _nearby(client: AsyncClient, headers: dict) -> list[dict]:
    response = await client.get(
        "/drivers/nearby",
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ المصادقة


async def test_socket_rejects_an_invalid_token(client: AsyncClient) -> None:
    async with ws_client() as sockets:
        async with aconnect_ws(f"{WS_RIDER}?token=not-a-token", client=sockets) as ws:
            with pytest.raises(HTTPXWSException):
                await _receive(ws)


async def test_driver_socket_rejects_a_rider(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider = await _rider_session(client)
    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={rider['token']}", client=sockets
        ) as ws:
            with pytest.raises(HTTPXWSException):
                await _receive(ws)


# --------------------------------------------------------------- بثّ الموقع


async def test_driver_location_reaches_the_rider_map(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الكبتن يبث موقعه، والراكب يراه سيارةً مجهّلة على خريطته."""
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    rider = await _rider_session(client)

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={driver['token']}", client=sockets
        ) as driver_ws:
            assert (await _receive(driver_ws))["type"] == "connected"
            await driver_ws.send_json(
                {"type": "location", **NEAR_PICKUP, "heading": 45}
            )

            async with aconnect_ws(
                f"{WS_RIDER}?token={rider['token']}", client=sockets
            ) as rider_ws:
                assert (await _receive(rider_ws))["type"] == "connected"
                await rider_ws.send_json({"type": "viewport", **PICKUP})

                nearby = await _receive(rider_ws, of_type="nearby_drivers")
                assert len(nearby["drivers"]) == 1
                car = nearby["drivers"][0]
                assert car["vehicle_category"] == "economy"
                assert car["heading"] == 45
                # لا هوية ولا لوحة (SPEC القسم 10)
                assert str(driver["driver_id"]) not in str(car)


async def test_closing_the_driver_socket_takes_him_off_the_map(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    rider = await _rider_session(client)

    async def _visible() -> bool:
        return bool(await _nearby(client, rider["headers"]))

    async def _gone() -> bool:
        return not await _nearby(client, rider["headers"])

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={driver['token']}", client=sockets
        ) as driver_ws:
            await _receive(driver_ws)
            await driver_ws.send_json({"type": "location", **NEAR_PICKUP, "heading": 0})
            await wait_until(
                _visible, message="لم يظهر الكبتن على الخريطة بعد بثّ موقعه"
            )

    await wait_until(_gone, message="بقي الكبتن على الخريطة بعد إغلاق مقبسه")


# ------------------------------------------------------------ أحداث الرحلة


async def test_offer_and_ride_events_reach_both_sides(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """من بطاقة الطلب حتى إنهاء الرحلة — كل انتقال يصل الطرفين."""
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    rider = await _rider_session(client)

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={driver['token']}", client=sockets
        ) as driver_ws:
            await _receive(driver_ws)
            await driver_ws.send_json({"type": "location", **NEAR_PICKUP, "heading": 0})

            async with aconnect_ws(
                f"{WS_RIDER}?token={rider['token']}", client=sockets
            ) as rider_ws:
                await _receive(rider_ws)

                ride = await request_ride(client, rider["headers"])
                ride_id = ride["id"]

                # بطاقة الطلب الواردة بعدّادها (SPEC القسم 12.3)
                offer = await _receive(driver_ws, of_type="ride_offer")
                assert offer["ride"]["id"] == ride_id
                assert offer["expires_in_seconds"] > 0
                assert offer["distance_to_pickup_km"] >= 0

                await wait_for_offer(ride_id, driver["driver_id"])
                accepted = await client.post(
                    f"/rides/{ride_id}/accept", headers=driver["headers"]
                )
                assert accepted.status_code == 200, accepted.text

                assigned = await _receive(rider_ws, of_type="driver_assigned")
                assert (
                    assigned["ride"]["driver"]["vehicle"]["plate_number"] == "AMM-1"
                )

                # أثناء الرحلة يصل الراكبَ موقعُ كبتنه هو
                await driver_ws.send_json(
                    {"type": "location", "lat": 31.9550, "lng": 35.9100, "heading": 180}
                )
                location = await _receive(rider_ws, of_type="driver_location")
                assert location["driver_id"] == str(driver["driver_id"])
                assert location["heading"] == 180

                for action, event in (
                    ("arrive", "driver_arrived"),
                    ("start", "ride_started"),
                    ("complete", "ride_completed"),
                ):
                    response = await client.post(
                        f"/rides/{ride_id}/{action}", headers=driver["headers"]
                    )
                    assert response.status_code == 200, response.text
                    received = await _receive(rider_ws, of_type=event)
                    assert received["ride"]["id"] == ride_id


async def test_driver_silence_alerts_both_sides_without_ending_the_ride(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """انقطاع الكبتن أثناء الرحلة يُنبَّه له الطرفان ولا يُنهيها (SPEC القسم 5)."""
    driver = await approved_driver(client, session_factory, plate_number="AMM-1")
    rider = await _rider_session(client)
    redis = get_redis_client()

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_DRIVER}?token={driver['token']}", client=sockets
        ) as driver_ws:
            await _receive(driver_ws)
            await driver_ws.send_json({"type": "location", **NEAR_PICKUP, "heading": 0})

            async with aconnect_ws(
                f"{WS_RIDER}?token={rider['token']}", client=sockets
            ) as rider_ws:
                await _receive(rider_ws)

                ride = await request_ride(client, rider["headers"])
                ride_id = ride["id"]
                await wait_for_offer(ride_id, driver["driver_id"])
                for action in ("accept", "arrive", "start"):
                    response = await client.post(
                        f"/rides/{ride_id}/{action}", headers=driver["headers"]
                    )
                    assert response.status_code == 200, response.text

                # محاكاة الصمت: يسقط مفتاح الحضور كما يسقط بانقضاء عمره
                await redis.delete(geo.presence_key(driver["driver_id"]))

                lost = await _receive(rider_ws, of_type="driver_connection_lost")
                assert lost["ride"]["status"] == "in_progress"
                assert (
                    await _receive(driver_ws, of_type="driver_connection_lost")
                )["ride"]["id"] == ride_id

                # الرحلة لم تُنهَ آلياً
                current = await client.get(f"/rides/{ride_id}", headers=rider["headers"])
                assert current.json()["status"] == "in_progress"

                # ثم يعود
                await driver_ws.send_json(
                    {"type": "location", **NEAR_PICKUP, "heading": 10}
                )
                back = await _receive(rider_ws, of_type="driver_reconnected")
                assert back["ride"]["id"] == ride_id


async def test_rider_is_told_when_no_driver_is_found(
    client: AsyncClient, jordan_settings: None
) -> None:
    rider = await _rider_session(client)

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_RIDER}?token={rider['token']}", client=sockets
        ) as rider_ws:
            await _receive(rider_ws)
            ride = await request_ride(client, rider["headers"])

            event = await _receive(rider_ws, of_type="no_driver_found")
            assert event["ride"]["id"] == ride["id"]
            assert event["ride"]["status"] == "no_driver_found"


async def test_connected_frame_carries_the_active_ride(
    client: AsyncClient, jordan_settings: None
) -> None:
    """استرجاع الحالة بعد انقطاع الاتصال (SPEC القسم 10)."""
    rider = await _rider_session(client)
    ride = await request_ride(client, rider["headers"])

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_RIDER}?token={rider['token']}", client=sockets
        ) as rider_ws:
            connected = await _receive(rider_ws, of_type="connected")
            assert connected["active_ride"]["id"] == ride["id"]
