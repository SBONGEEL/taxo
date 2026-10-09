"""رنينُ المكالمة والتطبيقُ مغلق (SPEC §٦٦-ج/١٧، الحزمةُ «2.0») — **ما يرسله الخادمُ لكلِّ جهازٍ بما يحمله**.

أربعةٌ تُقاس هنا، على المسارات الحقيقيّة (البدءُ والردُّ والرفضُ والقطعُ والكنس) لا على دالّةٍ معزولة:

١. **جهازٌ في المجموعة الثالثة يصله الرنينُ بياناتٍ وحدَها** على `taxo.call` بعمره، **وما دونها يصله ما يصله اليومَ حرفاً**.
٢. **وكلُّ ما يُسكت الرنينَ يُسكت خدمتَه** — الردُّ والرفضُ وقطعُ المتصل والفوات — **للمتصَل به في المجموعة الثالثة وحدَها**،
   **بأولويّةٍ عاديّة**، **ولو حسبه الخادمُ أمامَ صاحبه**.
٣. **لا رقمَ يمرّ** في شيءٍ من ذلك.
٤. **ومن فتح مقبسَه ورنينٌ قائمٌ له يصله إطارُه** بما بقي من ثلاثينه — للمتصَل به وحدَه، وما رنّ عنده وحدَه.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from sqlalchemy import update

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.models.ride_call import RideCall
from app.models.service_setting import ServiceSetting
from app.services import presence, ride_calls
from app.services.push import channels
from tests.conftest import ws_client
from tests.helpers import (
    DRIVER,
    RIDER,
    accepted_ride,
    approved_driver,
    bring_online,
    enable_features,
    enable_push_provider,
    pushes_to,
    register_device,
    rider_session,
    wait_until,
)

pytestmark = pytest.mark.usefixtures("jordan_settings")

WS = {"rider": "http://test/api/v1/ws/rider", "driver": "http://test/api/v1/ws/driver"}
RECEIVE_TIMEOUT = 12.0
#: **ما يحمله الرنينُ اليومَ** — والأقدمُ يبقى عليه حرفاً
TODAY = {"type", "ride_id", "call_id", "caller_role", "recording"}


def _tok(label: str) -> str:
    """رمزُ جهازٍ باسمه — **ثمانيةُ أحرفٍ فأكثر** كما يشترط المخطَّط، والاسمُ القصيرُ للقراءة وحدَها."""
    return f"fcm-token-{label}"


async def _trip(client: AsyncClient, session_factory) -> dict:
    await enable_features(session_factory, "trip_chat_enabled", "ride_calls_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride": ride}


async def _start(client: AsyncClient, trip: dict, who: str = "rider") -> str:
    started = await client.post(f"/rides/{trip['ride']['id']}/calls", headers=trip[who]["headers"])
    assert started.status_code == 201, started.text
    return started.json()["call_id"]


async def _devices(client: AsyncClient, headers: dict, prefix: str) -> None:
    """**ثلاثةُ أجهزةٍ لحسابٍ واحد**: حزمةٌ أقدمُ لا تبلّغ، والمجموعةُ الثانية، والثالثة (الحزمةُ «2.0»)."""
    await register_device(client, headers, device_id=f"{prefix}-old", token=_tok(f"{prefix}-old"))
    await register_device(client, headers, device_id=f"{prefix}-v2", token=_tok(f"{prefix}-v2"), push_channels=2)
    await register_device(client, headers, device_id=f"{prefix}-v3", token=_tok(f"{prefix}-v3"), push_channels=3)


def _kinds(pushes: list[dict]) -> list[str]:
    return [push["data"].get("type", "") for push in pushes]


def _no_phone_in(blob: object) -> None:
    """**لا رقمَ يمرّ** — لا رقمُ الراكب ولا الكبتن بأيِّ صيغةٍ مخزَّنة (نسخةُ `test_ride_calls._no_phone_in`)."""
    text = json.dumps(blob, ensure_ascii=False)
    for phone in (RIDER["phone"], DRIVER["phone"]):
        assert phone.lstrip("0") not in text, text


async def _age(session_factory, call_id: str, seconds: int) -> None:
    async with session_factory() as session:
        await session.execute(
            update(RideCall)
            .where(RideCall.id == uuid.UUID(call_id))
            .values(started_at=datetime.now(UTC) - timedelta(seconds=seconds))
        )
        await session.commit()


# ═════════════════════════ ١) الرنينُ بما يحمله الجهاز


async def test_a_native_device_rings_from_data_and_older_ones_are_unchanged(
    client: AsyncClient, session_factory
) -> None:
    trip = await _trip(client, session_factory)
    await enable_push_provider(session_factory)
    await _devices(client, trip["driver"]["headers"], "cap")

    call_id = await _start(client, trip)

    [old] = await pushes_to(_tok("cap-old"))
    [v2] = await pushes_to(_tok("cap-v2"))
    [v3] = await pushes_to(_tok("cap-v3"))
    # **الأقدمُ والثانيةُ كما اليومَ حرفاً** — إشعارٌ يرسمه النظام، والحمولةُ نفسُها
    for push in (old, v2):
        assert set(push["data"]) == TODAY
        assert push["data_only"] is False and push["android_channel_id"] is None
        assert push["title"] == "مكالمةٌ من الراكب" and push["high_priority"] is True
    assert old["data"] == v2["data"]

    # **والثالثةُ بياناتٌ وحدَها على قناة المكالمة، بعمرها ونصِّ درجها**
    assert v3["data_only"] is True and v3["android_channel_id"] == "taxo.call" and v3["high_priority"] is True
    assert set(v3["data"]) == TODAY | {"expires_in_seconds", "title", "body"}
    assert {key: v3["data"][key] for key in TODAY} == old["data"]
    assert v3["data"]["call_id"] == call_id and v3["data"]["caller_role"] == "rider"
    assert 25 <= int(v3["data"]["expires_in_seconds"]) <= 30
    assert v3["data"]["title"] == old["title"] and v3["data"]["body"] == old["body"]
    _no_phone_in([old, v2, v3])


async def test_the_ring_left_is_what_remains_of_thirty(client: AsyncClient, session_factory) -> None:
    """**عمرُ الرنين ما بقي منه لا ثلاثون دائماً** — مسجَّلةٌ ترنّ من إقرار المتصل، ورنينٌ يُرسل متأخّراً لا يَعِد بما فات."""
    trip = await _trip(client, session_factory)
    call_id = await _start(client, trip)
    await _age(session_factory, call_id, 12)
    async with session_factory() as session:
        call = await session.get(RideCall, uuid.UUID(call_id))
        assert call is not None
        assert 17 <= ride_calls.seconds_left(call) <= 18
        # **ولا أقلَّ من واحدة** — صفرٌ يُقرأ «بلا عمر» عند `fcm._lifetime`
        assert ride_calls.seconds_left(call, now=call.started_at + timedelta(seconds=40)) == 1


# ═════════════════════════ ٢) كلُّ ما يُسكت الرنينَ يُسكت خدمتَه — للثالثة وحدَها


async def _silenced_by(client: AsyncClient, session_factory, trip: dict, call_id: str, how: str) -> None:
    if how == "answer":
        done = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
        assert done.status_code == 200, done.text
        # **وإنهاءُ ما رُدّ عليه لا يُسكت ثانيةً** — سكت عند الردّ
        ended = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])
        assert ended.status_code == 200 and ended.json()["end_reason"] == "completed"
    elif how == "decline":
        done = await client.post(f"/calls/{call_id}/decline", json={}, headers=trip["driver"]["headers"])
        assert done.status_code == 200 and done.json()["end_reason"] == "declined"
    elif how == "cancel":
        done = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])
        assert done.status_code == 200 and done.json()["end_reason"] == "cancelled"
    else:
        await _age(session_factory, call_id, 31)
        async with session_factory() as session:
            swept = await ride_calls.expire_ringing(session)
            await session.commit()
            for lapsed in swept:
                await ride_calls.publish_missed(session, get_redis_client(), lapsed)
        assert [str(call.id) for call in swept] == [call_id]


@pytest.mark.parametrize("how", ["answer", "decline", "cancel", "timeout"])
async def test_whatever_stops_the_ring_silences_the_native_one(
    client: AsyncClient, session_factory, how: str
) -> None:
    trip = await _trip(client, session_factory)
    await enable_push_provider(session_factory)
    await _devices(client, trip["driver"]["headers"], "cap")
    # **والمتصلُ لا يرنّ عنده شيء** — فلا أمرَ إسكاتٍ له ولو حمل الخدمة
    await register_device(client, trip["rider"]["headers"], device_id="rid-v3", token=_tok("rid-v3"), push_channels=3)

    call_id = await _start(client, trip)
    await _silenced_by(client, session_factory, trip, call_id, how)

    v3 = await pushes_to(_tok("cap-v3"))
    stops = [push for push in v3 if push["data"]["type"] == channels.CALL_RING_STOPPED]
    assert len(stops) == 1, _kinds(v3)
    [stop] = stops
    # **بعد الرنين لا قبله**، وأمرٌ بلا نصٍّ ولا قناة: الخدمةُ تطوي إشعارَها بمعرّف المكالمة
    assert _kinds(v3).index(channels.CALL_RING_STOPPED) > _kinds(v3).index("incoming_call")
    assert stop["data"] == {
        "type": channels.CALL_RING_STOPPED,
        "ride_id": trip["ride"]["id"],
        "call_id": call_id,
        "expires_in_seconds": "30",
    }
    # **وبأولويّةٍ عاديّة** — عاليةٌ لا يُرى منها شيءٌ تُبطئ عند FCM طلبَ الرحلة والرنينَ نفسَه
    assert stop["data_only"] is True and stop["high_priority"] is False and stop["android_channel_id"] is None

    # **ولا يصل ما دون الثالثة** — إشعارُها رسمه النظام ولا خدمةَ تفهم الأمر
    for token in ("cap-old", "cap-v2", "rid-v3"):
        assert channels.CALL_RING_STOPPED not in _kinds(await pushes_to(_tok(token))), token
    _no_phone_in([v3, await pushes_to(_tok("cap-old")), await pushes_to(_tok("rid-v3"))])


async def test_the_stop_reaches_a_native_device_whose_screen_is_open(client: AsyncClient, session_factory) -> None:
    """**«أسكت» لا يُحجب عن جهازٍ أمامَ صاحبه** (`notify_user` ← `channels.NATIVE_ONLY_KINDS`) — هاتفٌ رنّ بخدمته والتطبيقُ
    مغلق، **ثمّ فُتح التطبيقُ والرنينُ قائم** (فتحُ القفل يتخطّى طيَّه)، **ثمّ قطعها المتصل**: مقبسُه ظاهرٌ عند الخادم، والويبُ لا
    يرى الأمر، **وحجبُه عنه رنينٌ يدوّي لمكالمةٍ انتهت** حتى عمره."""
    trip = await _trip(client, session_factory)
    await enable_push_provider(session_factory)
    await _devices(client, trip["driver"]["headers"], "cap")
    driver_id = uuid.UUID(trip["driver"]["user_id"])
    redis = get_redis_client()

    call_id = await _start(client, trip)
    # **رنّ بخدمته** — لا مقبسَ له بعد
    assert _kinds(await pushes_to(_tok("cap-v3"))) == ["incoming_call"]

    async def _shown() -> bool:
        return "cap-v3" in await presence.foreground_devices(redis, driver_id)

    url = f"{WS['driver']}?token={trip['driver']['token']}&device_id=cap-v3"
    async with ws_client() as sockets:
        async with aconnect_ws(url, client=sockets) as ws:
            await _receive(ws, "connected")
            await wait_until(_shown, message="لم يُحسب المقبسُ أمامَ صاحبه")
            cancelled = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])
            assert cancelled.status_code == 200 and cancelled.json()["end_reason"] == "cancelled"

    kinds = _kinds(await pushes_to(_tok("cap-v3")))
    assert kinds.count(channels.CALL_RING_STOPPED) == 1, kinds
    assert kinds.index(channels.CALL_RING_STOPPED) > kinds.index("incoming_call")
    # **وما دون الثالثة لا يصله** — رفعُ الحجب لا يوسّع من يُرسل إليه: لا خدمةَ هناك تفهمه
    assert channels.CALL_RING_STOPPED not in _kinds(await pushes_to(_tok("cap-v2")))


async def test_a_recorded_call_that_never_rang_sends_no_stop(client: AsyncClient, session_factory) -> None:
    """**ما لم يرنّ لا يُسكَت** (`_rang`) — مسجَّلةٌ قطعها متصلُها على التنبيه لم يصل الطرفَ الآخرَ منها شيء."""
    async with session_factory() as session:
        session.add(ServiceSetting(country_code=CountryCode.JO, call_recording_enabled=True))
        await session.commit()
    trip = await _trip(client, session_factory)
    await enable_push_provider(session_factory)
    await register_device(client, trip["driver"]["headers"], device_id="cap-v3", token=_tok("cap-v3"), push_channels=3)

    call_id = await _start(client, trip)
    cancelled = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])
    assert cancelled.status_code == 200 and cancelled.json()["end_reason"] == "cancelled"
    assert await pushes_to(_tok("cap-v3")) == []


# ═════════════════════════ ٤) الرنينُ القائمُ يُستعاد مع المقبس


async def _receive(ws, of_type: str) -> dict:
    async def _read() -> dict:
        while True:
            message = await ws.receive_json()
            if message.get("type") == of_type:
                return message

    return await asyncio.wait_for(_read(), timeout=RECEIVE_TIMEOUT)


@pytest.mark.parametrize("callee", ["rider", "driver"])
async def test_a_socket_opened_while_ringing_gets_the_ring(
    client: AsyncClient, session_factory, callee: str
) -> None:
    """**فتحُ التطبيق من أيقونته وهاتفُه يرنّ** — الحدثُ بُثّ قبل أن يُفتح المقبس، **فيُعاد مع `connected`** بما بقي من ثلاثينه.
    والخدمةُ الأصليّةُ تطوي رنينَها حين يظهر التطبيق، **فبلا هذا كان يرى شاشةً بلا مكالمة**."""
    trip = await _trip(client, session_factory)
    caller = "driver" if callee == "rider" else "rider"
    call_id = await _start(client, trip, caller)
    await _age(session_factory, call_id, 10)

    async with ws_client() as sockets:
        async with aconnect_ws(f"{WS[callee]}?token={trip[callee]['token']}", client=sockets) as ws:
            await _receive(ws, "connected")
            ring = await _receive(ws, "incoming_call")

    # **الإطارُ نفسُه الذي يُبثّ عند البدء** — والمهلةُ ما بقي
    assert set(ring) == {
        "type", "ride_id", "call_id", "caller_role", "status", "end_reason", "recording", "ring_timeout_seconds"
    }
    assert ring["call_id"] == call_id and ring["caller_role"] == caller and ring["status"] == "ringing"
    assert 1 <= ring["ring_timeout_seconds"] <= 20
    _no_phone_in(ring)


async def test_the_ring_is_replayed_to_its_callee_alone_and_only_while_it_rings(
    client: AsyncClient, session_factory
) -> None:
    trip = await _trip(client, session_factory)
    call_id = await _start(client, trip)
    rider_id = uuid.UUID(trip["rider"]["user"]["id"])
    driver_id = uuid.UUID(trip["driver"]["user_id"])

    async def frame(user_id: uuid.UUID) -> dict | None:
        async with session_factory() as session:
            ride = await session.get(Ride, uuid.UUID(trip["ride"]["id"]))
            return await ride_calls.ringing_frame(session, ride, user_id)

    # **المتصلُ لا يرنّ عنده شيء**، والمتصَلُ به يصله إطارُه
    assert await frame(rider_id) is None
    assert (await frame(driver_id) or {}).get("call_id") == call_id
    # **ولا رحلةَ ولا رنين**
    async with session_factory() as session:
        assert await ride_calls.ringing_frame(session, None, driver_id) is None

    # **وما فاتت ثلاثونُه ليس رنيناً** وإن لم يكتبه أحدٌ بعد
    await _age(session_factory, call_id, 31)
    assert await frame(driver_id) is None


async def test_a_recorded_call_is_not_replayed_before_it_rings(client: AsyncClient, session_factory) -> None:
    """**مسجَّلةٌ متصلُها بعدُ أمام التنبيه لم ترنّ** — فلا يُعاد رنينٌ لم يقع، **ويُعاد بعد «متابعة»**."""
    async with session_factory() as session:
        session.add(ServiceSetting(country_code=CountryCode.JO, call_recording_enabled=True))
        await session.commit()
    trip = await _trip(client, session_factory)
    call_id = await _start(client, trip)
    driver_id = uuid.UUID(trip["driver"]["user_id"])

    async def frame() -> dict | None:
        async with session_factory() as session:
            ride = await session.get(Ride, uuid.UUID(trip["ride"]["id"]))
            return await ride_calls.ringing_frame(session, ride, driver_id)

    assert await frame() is None
    noticed = await client.post(f"/calls/{call_id}/recording-notice", headers=trip["rider"]["headers"])
    assert noticed.status_code == 200, noticed.text
    replayed = await frame()
    assert replayed is not None and replayed["call_id"] == call_id and replayed["recording"] is True
