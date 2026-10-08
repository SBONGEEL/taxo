"""مكالمةُ الرحلة (SPEC §٦٦-ج/١٩) — **اختباراتُ المالك بنصّها**: لا مكالمةَ خارج نافذة الرحلة · لا رقمَ يمرّ · **التسجيلُ مطفأٌ
افتراضاً** · **وحين يُشعل يسبق التنبيهُ دائماً** · كلُّ استماعٍ مدقَّق. **ومعها**: غيرُ الطرفين ٤٠٤، والمفتاحُ المطفأُ برمزه،
والرنينُ الفائتُ كسولاً وبالكنس، وبياناتُ المُرحِّل المؤقّتة.

**ولا يُشعَل التسجيلُ إلا داخل الاختبار الذي يقيسه** — صفُّ سوقٍ في قاعدة الاختبار تُفرَّغ بعده (شرطُ المالك: «لا أشعل التسجيلَ أنا أبداً»).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core import storage
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode
from app.models.ride_call import RideCall
from app.models.service_setting import ServiceSetting
from app.services import ride_calls
from app.ws import events
from tests.conftest import _staff_headers
from tests.helpers import (
    DRIVER,
    OTHER_RIDER,
    RIDER,
    accepted_ride,
    approved_driver,
    bring_online,
    enable_features,
    enable_push_provider,
    inbox_of,
    pushes_to,
    register_device,
    rider_session,
    started_ride,
)

pytestmark = pytest.mark.usefixtures("jordan_settings")

#: رأسُ WebM (EBML) — ما يُخرجه `MediaRecorder`
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


async def _trip(client: AsyncClient, session_factory, *, started: bool = False, flags=("trip_chat_enabled", "ride_calls_enabled")) -> dict:
    if flags:
        await enable_features(session_factory, *flags)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await (started_ride if started else accepted_ride)(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride": ride, "rider_id": rider["user"]["id"]}


async def _start(client: AsyncClient, trip: dict, who: str = "rider"):
    return await client.post(f"/rides/{trip['ride']['id']}/calls", headers=trip[who]["headers"])


async def _call(session_factory, call_id: str) -> RideCall:
    async with session_factory() as session:
        call = await session.get(RideCall, uuid.UUID(call_id))
        assert call is not None
        return call


async def _drain(pubsub, seconds: float = 0.6) -> list[dict]:
    found: list[dict] = []
    deadline = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < deadline:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            found.append(json.loads(message["data"]))
    return found


async def _listen_to(*user_ids: str):
    pubsub = get_redis_client().pubsub()
    await pubsub.subscribe(*(events.user_channel(user_id) for user_id in user_ids))
    return pubsub


def _no_phone_in(blob: object) -> None:
    """**لا رقمَ يمرّ**: لا رقمُ الراكب ولا الكبتن — بأيِّ صيغةٍ مخزَّنة — في حمولة حدثٍ أو إشعار."""
    text = json.dumps(blob, ensure_ascii=False)
    for phone in (RIDER["phone"], DRIVER["phone"]):
        national = phone.lstrip("0")
        assert national not in text, text


async def _turn_recording_on(session_factory) -> None:
    """**التسجيلُ يُشعل هنا وحدَه** — صفُّ سوقٍ في قاعدة الاختبار، تُفرَّغ بعد الاختبار."""
    async with session_factory() as session:
        session.add(ServiceSetting(country_code=CountryCode.JO, call_recording_enabled=True))
        await session.commit()


# ═════════════════════════ ١) لا مكالمةَ خارج نافذة الرحلة


async def test_no_call_before_a_captain_accepts(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "ride_calls_enabled")
    rider = await rider_session(client)
    ride = (
        await client.post(
            "/rides",
            json={"pickup": {"lat": 31.9539, "lng": 35.9106}, "dropoff": {"lat": 31.98, "lng": 35.89}, "vehicle_category": "economy"},
            headers=rider["headers"],
        )
    ).json()
    refused = await client.post(f"/rides/{ride['id']}/calls", headers=rider["headers"])
    assert refused.status_code == 409 and refused.json()["code"] == "call_window_closed"


async def test_a_ringing_call_ends_with_the_ride_and_nothing_is_relayed_after(
    client: AsyncClient, session_factory
) -> None:
    trip = await _trip(client, session_factory)
    started = await _start(client, trip)
    assert started.status_code == 201, started.text
    call_id = started.json()["call_id"]

    pubsub = await _listen_to(trip["rider_id"], trip["driver"]["user_id"])
    cancelled = await client.post(
        f"/rides/{trip['ride']['id']}/cancel", json={"reason": "عطل"}, headers=trip["driver"]["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    ended = [event for event in await _drain(pubsub) if event["type"] == "call_ended"]
    await pubsub.aclose()
    # **الطرفان يُخبَران** — والسببُ «انتهت الرحلة»
    assert len(ended) == 2 and {event["end_reason"] for event in ended} == {"ride_ended"}

    call = await _call(session_factory, call_id)
    assert call.status.value == "ended" and call.end_reason.value == "ride_ended"

    answer = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    assert answer.status_code == 409 and answer.json()["code"] == "call_window_closed"
    signal = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "ice", "payload": {"candidate": "x"}}, headers=trip["rider"]["headers"]
    )
    assert signal.status_code == 409 and signal.json()["code"] == "call_not_active"
    again = await _start(client, trip)
    assert again.status_code == 409 and again.json()["code"] == "call_window_closed"


async def test_an_active_call_ends_when_the_ride_completes(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory, started=True)
    call_id = (await _start(client, trip, "driver")).json()["call_id"]
    answered = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["rider"]["headers"])
    assert answered.status_code == 200, answered.text

    done = await client.post(f"/rides/{trip['ride']['id']}/complete", headers=trip["driver"]["headers"])
    assert done.status_code == 200, done.text
    call = await _call(session_factory, call_id)
    assert call.status.value == "ended" and call.end_reason.value == "ride_ended"
    assert call.duration_seconds is not None and call.duration_seconds >= 0
    signal = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "offer", "payload": {"sdp": "v=0"}}, headers=trip["driver"]["headers"]
    )
    assert signal.status_code == 409 and signal.json()["code"] == "call_not_active"
    # **ويختفي زرُّ الاتصال** بعد الرحلة
    thread = (await client.get(f"/rides/{trip['ride']['id']}/chat", headers=trip["rider"]["headers"])).json()
    assert thread["can_call"] is False and thread["active_call"] is None


# ═════════════════════════ ٢) لا رقمَ يمرّ — في الحدث والإشعار والإشارة


async def test_the_call_flow_carries_no_number(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory)
    await enable_push_provider(session_factory)
    await register_device(client, trip["driver"]["headers"], device_id="driver-phone", token="fcm-driver")
    pubsub = await _listen_to(trip["rider_id"], trip["driver"]["user_id"])

    started = await _start(client, trip)
    assert started.status_code == 201, started.text
    body = started.json()
    # **بلا سرٍّ ولا عناوين لا مُرحِّل** — والطرفان على شبكتهما
    assert body["ice_servers"] == [] and body["recording"] is False and body["ring_timeout_seconds"] == 30
    call_id = body["call_id"]

    busy = await _start(client, trip, "driver")
    assert busy.status_code == 409 and busy.json()["code"] == "call_busy"

    answered = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    assert answered.status_code == 200, answered.text

    offer = {"type": "offer", "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\n"}
    relayed = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "offer", "payload": offer}, headers=trip["rider"]["headers"]
    )
    assert relayed.status_code == 204, relayed.text
    wrong = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "answer", "payload": {}}, headers=trip["rider"]["headers"]
    )
    assert wrong.status_code == 409 and wrong.json()["code"] == "call_signal_refused"
    ended = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])
    assert ended.status_code == 200 and ended.json()["end_reason"] == "completed"
    assert ended.json()["duration_seconds"] is not None
    twice = await client.post(f"/calls/{call_id}/end", json={}, headers=trip["driver"]["headers"])
    assert twice.status_code == 200 and twice.json()["end_reason"] == "completed"

    seen = await _drain(pubsub)
    await pubsub.aclose()
    by_type: dict[str, list[dict]] = {}
    for event in seen:
        by_type.setdefault(event["type"], []).append(event)
    [incoming] = by_type["incoming_call"]
    assert set(incoming) == {
        "type", "ride_id", "call_id", "caller_role", "status", "end_reason", "recording", "ring_timeout_seconds"
    }
    assert incoming["caller_role"] == "rider"
    # **الإشارةُ للطرف الآخر وحدَه** — والمرسِلُ لا تصله
    [signal] = by_type["call_signal"]
    assert signal["payload"] == offer and signal["from_role"] == "rider"
    assert len(by_type["call_answered"]) == 2 and len(by_type["call_ended"]) == 2
    _no_phone_in(seen)

    [push] = await pushes_to("fcm-driver")
    assert push["title"] == "مكالمةٌ من الراكب" and push["high_priority"] is True
    assert set(push["data"]) == {"type", "ride_id", "call_id", "caller_role", "recording"}
    _no_phone_in(push)


async def test_turn_credentials_are_time_limited_ours_and_outlive_a_call(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "turn-secret-for-this-test-only"
    monkeypatch.setattr(settings, "turn_shared_secret", secret)
    monkeypatch.setattr(settings, "turn_urls", "turn:turn.test:3478?transport=udp, turn:turn.test:3478?transport=tcp")
    trip = await _trip(client, session_factory)

    before = int(datetime.now(UTC).timestamp())
    [server] = (await _start(client, trip)).json()["ice_servers"]
    expiry, user_id = server["username"].split(":")
    assert user_id == trip["rider_id"]
    ttl = settings.turn_credential_ttl_seconds
    assert before + ttl - 10 <= int(expiry) <= before + ttl + 10
    # **أطولُ من أطول مكالمة** (قِيس ٢٠٢٦-١٠-٠٨): تجديدُ الحجز على coturn أثناء المكالمة يحمل الختمَ نفسَه، ولا بابَ يُصدر
    # غيرَه — **فعشرُ دقائق كانت تُسقط المكالمةَ عبر المُرحِّل في منتصفها**
    assert int(expiry) >= before + 2 * 3600
    expected = base64.b64encode(hmac.new(secret.encode(), server["username"].encode(), hashlib.sha1).digest()).decode()
    assert server["credential"] == expected
    assert server["urls"] == ["turn:turn.test:3478?transport=udp", "turn:turn.test:3478?transport=tcp"]


@pytest.mark.parametrize("who", ["rider", "driver"])
async def test_calling_again_ends_a_call_left_active(client: AsyncClient, session_factory, who: str) -> None:
    """**جاريةٌ تُركت بلا من ينهيها لا تحجب الرحلةَ كلَّها** (قِيس ٢٠٢٦-١٠-٠٨): تطبيقٌ سقط أو شبكةٌ انقطعت تتركها «جارية»، **وكانت
    كلُّ مكالمةٍ بعدها تُردّ `call_busy` حتى تنتهي الرحلة**. ومن يتّصل من جديد — المتصلُ أو المتصَلُ به — طرفٌ فيها وليس فيها الآن:
    **تُغلق `failed` ويُخبَر الطرفان، وترنّ الجديدة**."""
    trip = await _trip(client, session_factory)
    first = (await _start(client, trip)).json()["call_id"]
    answered = await client.post(f"/calls/{first}/answer", json={}, headers=trip["driver"]["headers"])
    assert answered.status_code == 200, answered.text

    pubsub = await _listen_to(trip["rider_id"], trip["driver"]["user_id"])
    again = await _start(client, trip, who)
    assert again.status_code == 201, again.text
    seen = await _drain(pubsub)
    await pubsub.aclose()

    old = await _call(session_factory, first)
    assert old.status.value == "ended" and old.end_reason.value == "failed"
    assert old.answered_at is not None and old.duration_seconds is not None
    new = await _call(session_factory, again.json()["call_id"])
    assert new.status.value == "ringing" and new.caller_role.value == who
    ended = [event for event in seen if event["type"] == "call_ended" and event["call_id"] == first]
    assert len(ended) == 2 and {event["end_reason"] for event in ended} == {"failed"}
    # **والرنينُ الذي لم تفُت ثلاثونُه ما زال يحجب** — الطرفُ الآخر يتّصل الآن
    busy = await _start(client, trip, "driver" if who == "rider" else "rider")
    assert busy.status_code == 409 and busy.json()["code"] == "call_busy"


async def test_declining_rings_off_both_sides(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory)
    call_id = (await _start(client, trip)).json()["call_id"]
    refused = await client.post(f"/calls/{call_id}/decline", json={}, headers=trip["rider"]["headers"])
    assert refused.status_code == 409 and refused.json()["code"] == "call_not_ringing"
    declined = await client.post(f"/calls/{call_id}/decline", json={}, headers=trip["driver"]["headers"])
    assert declined.status_code == 200 and declined.json()["end_reason"] == "declined"
    assert declined.json()["duration_seconds"] is None


# ═════════════════════════ ٣) الرنينُ ثلاثون ثانية — كسولاً وبالكنس


async def _age(session_factory, call_id: str, seconds: int) -> None:
    async with session_factory() as session:
        await session.execute(
            update(RideCall)
            .where(RideCall.id == uuid.UUID(call_id))
            .values(started_at=datetime.now(UTC) - timedelta(seconds=seconds))
        )
        await session.commit()


async def test_a_ring_past_thirty_seconds_is_missed(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory)
    call_id = (await _start(client, trip)).json()["call_id"]
    await _age(session_factory, call_id, 31)

    late = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    assert late.status_code == 409 and late.json()["code"] == "call_not_ringing"
    read = await client.get(f"/calls/{call_id}", headers=trip["driver"]["headers"])
    assert read.status_code == 200 and read.json()["status"] == "ended" and read.json()["end_reason"] == "no_answer"
    # **والفائتةُ تُقال في إشعارٍ عاديٍّ يبقى في الصندوق** (§٦٦-د/٤)
    kinds = [row.kind for row in await inbox_of(session_factory, trip["driver"]["user_id"])]
    assert "missed_call" in kinds

    # **ولا تحجب مكالمةً جديدة**
    second = await _start(client, trip)
    assert second.status_code == 201, second.text
    await _age(session_factory, second.json()["call_id"], 40)
    # **والكنسُ يُغلق ما لم يلمسه أحد**
    async with session_factory() as session:
        missed = await ride_calls.expire_ringing(session)
        await session.commit()
    assert [str(call.id) for call in missed] == [second.json()["call_id"]]
    assert (await _call(session_factory, second.json()["call_id"])).end_reason.value == "no_answer"


# ═════════════════════════ ٤) غيرُ الطرفين ٤٠٤ — والمفتاحُ المطفأ


async def test_a_third_user_gets_404(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    trip = await _trip(client, session_factory)
    call_id = (await _start(client, trip)).json()["call_id"]
    stranger = await rider_session(client, OTHER_RIDER)
    for headers in (stranger["headers"], admin_headers):
        assert (await client.get(f"/calls/{call_id}", headers=headers)).status_code == 404
        assert (await client.post(f"/calls/{call_id}/answer", json={}, headers=headers)).status_code == 404
        assert (await client.post(f"/calls/{call_id}/end", json={}, headers=headers)).status_code == 404
        signal = await client.post(
            f"/calls/{call_id}/signal", json={"kind": "ice", "payload": {}}, headers=headers
        )
        assert signal.status_code == 404
        assert (await client.post(f"/rides/{trip['ride']['id']}/calls", headers=headers)).status_code == 404
    assert (await _call(session_factory, call_id)).status.value == "ringing"


async def test_with_the_flag_off_there_is_no_call(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory, flags=("trip_chat_enabled",))
    refused = await _start(client, trip)
    assert refused.status_code == 403 and refused.json()["code"] == "ride_calls_disabled"
    thread = (await client.get(f"/rides/{trip['ride']['id']}/chat", headers=trip["rider"]["headers"])).json()
    assert thread["open"] is True and thread["can_call"] is False


# ═════════════════════════ ٥) التسجيل — مطفأٌ افتراضاً، والتنبيهُ يسبق دائماً، وكلُّ استماعٍ مدقَّق


async def test_recording_is_off_by_default(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    listed = (await client.get("/admin/settings/services", headers=admin_headers)).json()
    assert {row["country_code"]: row["call_recording_enabled"] for row in listed} == {"LY": False, "JO": False}
    # **وافتراضُ العمود في القاعدة نفسِها مطفأ** — صفٌّ يُدرج بسوقه وحدَه يخرج بلا تسجيل (ولا يُلتزم)
    async with session_factory() as session:
        row = ServiceSetting(country_code=CountryCode.LY)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        assert row.call_recording_enabled is False and row.call_recording_retention_days == 30
        assert row.chat_retention_days == 90
        await session.rollback()

    trip = await _trip(client, session_factory)
    started = (await _start(client, trip)).json()
    assert started["recording"] is False
    call_id = started["call_id"]
    await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])

    refused = await client.post(
        f"/calls/{call_id}/recording",
        files={"file": ("call.webm", WEBM_BYTES, "audio/webm")},
        headers=trip["rider"]["headers"],
    )
    assert refused.status_code == 409 and refused.json()["code"] == "call_recording_refused"
    call = await _call(session_factory, call_id)
    assert call.recorded is False and call.recording_path is None


async def test_when_recording_is_on_the_notice_always_comes_first(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _turn_recording_on(session_factory)
    trip = await _trip(client, session_factory)
    started = (await _start(client, trip)).json()
    assert started["recording"] is True
    call_id = started["call_id"]

    # **عرضُ المتصل لا يُمرَّر قبل إقراره**
    offer = {"type": "offer", "sdp": "v=0"}
    early = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "offer", "payload": offer}, headers=trip["rider"]["headers"]
    )
    assert early.status_code == 409 and early.json()["code"] == "call_recording_notice_required"

    # **وردُّ المتصَل به يُرفض بلا إقرار**
    bare = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    assert bare.status_code == 409 and bare.json()["code"] == "call_recording_notice_required"
    acked = await client.post(
        f"/calls/{call_id}/answer", json={"recording_notice_ack": True}, headers=trip["driver"]["headers"]
    )
    assert acked.status_code == 200, acked.text

    noticed = await client.post(f"/calls/{call_id}/recording-notice", headers=trip["rider"]["headers"])
    assert noticed.status_code == 200, noticed.text
    relayed = await client.post(
        f"/calls/{call_id}/signal", json={"kind": "offer", "payload": offer}, headers=trip["rider"]["headers"]
    )
    assert relayed.status_code == 204, relayed.text
    call = await _call(session_factory, call_id)
    assert call.caller_notice_at is not None and call.callee_notice_at is not None

    await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])

    # **التسجيلُ من جهاز المتصل وحدَه، صوتاً، ومرّةً واحدة**
    by_callee = await client.post(
        f"/calls/{call_id}/recording", files={"file": ("c.webm", WEBM_BYTES, "audio/webm")}, headers=trip["driver"]["headers"]
    )
    assert by_callee.status_code == 409
    not_audio = await client.post(
        f"/calls/{call_id}/recording", files={"file": ("c.webm", b"%PDF-1.7 not audio", "audio/webm")},
        headers=trip["rider"]["headers"],
    )
    assert not_audio.status_code == 422 and not_audio.json()["code"] == "unsupported_document"
    uploaded = await client.post(
        f"/calls/{call_id}/recording", files={"file": ("c.webm", WEBM_BYTES, "audio/webm")}, headers=trip["rider"]["headers"]
    )
    assert uploaded.status_code == 200, uploaded.text
    again = await client.post(
        f"/calls/{call_id}/recording", files={"file": ("c.webm", WEBM_BYTES, "audio/webm")}, headers=trip["rider"]["headers"]
    )
    assert again.status_code == 409
    call = await _call(session_factory, call_id)
    assert call.recording_path is not None
    remaining = call.recording_expires_at - datetime.now(UTC)
    assert timedelta(days=29, hours=23) < remaining <= timedelta(days=30)

    # **والاستماعُ صلاحيةٌ مستقلّة — لا يملكها المشرفُ الكامل افتراضاً — وكلُّ استماعٍ سطر**
    refused = await client.get(f"/admin/calls/{call_id}/recording", headers=admin_headers)
    assert refused.status_code == 403, refused.text
    listener_headers = await _staff_headers("admin", "+962790000051", "مستمعٌ مخوَّل")
    me = (await client.get("/auth/me", headers=listener_headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    await client.put(
        f"/admin/permissions/{me['id']}",
        json={"permissions": sorted(set(row["permissions"]) | {"call_recordings.listen"})},
        headers=admin_headers,
    )
    for _ in range(2):
        heard = await client.get(f"/admin/calls/{call_id}/recording", headers=listener_headers)
        assert heard.status_code == 200, heard.text
        assert heard.headers["content-type"].startswith("audio/webm") and heard.content == WEBM_BYTES
    async with session_factory() as session:
        audits = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "call_recording"))
        ).all()
    assert len(audits) == 2 and all(str(entry.actor_id) == me["id"] for entry in audits)
    log = (await client.get(f"/admin/rides/{trip['ride']['id']}/calls", headers=admin_headers)).json()
    assert log[0]["has_recording"] is True

    # **وما حلّ موعدُه لا يُسمع ولو لم يمرّ الكنسُ بعد** (قِيس ٢٠٢٦-١٠-٠٨) — ولا يُعرض في السجلّ قابلاً للسماع، ولا سطرَ تدقيق
    async with session_factory() as session:
        await session.execute(
            update(RideCall)
            .where(RideCall.id == uuid.UUID(call_id))
            .values(recording_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    expired = await client.get(f"/admin/calls/{call_id}/recording", headers=listener_headers)
    assert expired.status_code == 404, expired.text
    log = (await client.get(f"/admin/rides/{trip['ride']['id']}/calls", headers=admin_headers)).json()
    assert log[0]["has_recording"] is False
    async with session_factory() as session:
        audits = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "call_recording"))
        ).all()
    assert len(audits) == 2

    # **والحذفُ في موعده** — الملفُّ والمسار
    async with session_factory() as session:
        _, files = await ride_calls.purge_expired(session, now=datetime.now(UTC) + timedelta(days=31))
        await session.commit()
    assert files == [call.recording_path]
    for path in files:
        await storage.delete(path)
    assert (await _call(session_factory, call_id)).recording_path is None


async def test_no_recording_is_kept_unless_both_sides_saw_the_notice(
    client: AsyncClient, session_factory
) -> None:
    """**الرفعُ بابٌ مستقلٌّ يُنادى مباشرة** — فيشترط إقرارَ الطرفين هو أيضاً، لا الإشارةُ وحدَها (قِيس ٢٠٢٦-١٠-٠٨): متصلٌ لم يُقِرّ
    قط، ومكالمةٌ رُدّ عليها بإقرار المتصَل به وانتهت، **كان تسجيلُها يُقبل**."""
    await _turn_recording_on(session_factory)
    trip = await _trip(client, session_factory)
    call_id = (await _start(client, trip)).json()["call_id"]
    acked = await client.post(
        f"/calls/{call_id}/answer", json={"recording_notice_ack": True}, headers=trip["driver"]["headers"]
    )
    assert acked.status_code == 200, acked.text
    await client.post(f"/calls/{call_id}/end", json={}, headers=trip["rider"]["headers"])

    refused = await client.post(
        f"/calls/{call_id}/recording", files={"file": ("c.webm", WEBM_BYTES, "audio/webm")}, headers=trip["rider"]["headers"]
    )
    assert refused.status_code == 409 and refused.json()["code"] == "call_recording_refused", refused.text
    call = await _call(session_factory, call_id)
    assert call.caller_notice_at is None and call.callee_notice_at is not None
    assert call.recording_path is None and call.recording_expires_at is None


# ═════════════════════════ ٦) سجلُّ المكالمات للّوحة — بياناتٌ وصفيّةٌ وحدَها


async def test_the_admin_call_log_is_metadata_only(
    client: AsyncClient, session_factory, support_headers: dict
) -> None:
    trip = await _trip(client, session_factory)
    call_id = (await _start(client, trip)).json()["call_id"]
    await client.post(f"/calls/{call_id}/decline", json={}, headers=trip["driver"]["headers"])

    log = await client.get(f"/admin/rides/{trip['ride']['id']}/calls", headers=support_headers)
    assert log.status_code == 200, log.text
    [row] = log.json()
    assert row["caller_role"] == "rider" and row["end_reason"] == "declined"
    assert row["recorded"] is False and row["has_recording"] is False
    assert row["caller_name"] and row["callee_name"]
    _no_phone_in(row)
