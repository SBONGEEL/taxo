"""تزامنُ مكالمة الرحلة (`services/ride_calls`) — **ردٌّ يسابق إنهاءً أو رفضاً يترك حالاً واحدةً متّسقة**.

**والتداخلُ مرتَّبٌ لا متروكٌ للحظ** (نمطُ `test_stage8_concurrency.py`): الإنهاءُ (أو الرفضُ) يمسك معاملتَه مفتوحةً وصفُّ المكالمة
مقفول، والردُّ يبدأ وهو مفتوح. **بالقفل** ينتظر الردُّ فيجدها منتهيةً فيُردّ `call_not_ringing`، والصفُّ منتهٍ بلا وقتِ ردّ.
**وبحذف `with_for_update` من `_lock_call`** يقرأ الردُّ «ترنّ» ويكتب «جارية» فوق «منتهية» — فيرتدّ قيدُ القاعدة
(`ride_call_ended_complete`) خطأً لا رمزاً، أو يبقى صفٌّ مُجاباً ملغىً: **ويسقط هذا الاختبار** (مقيسٌ بالحذف، انظر التقرير).

**وثلاثةٌ تملكها أقفالٌ أخرى، كلٌّ باختباره** (أُضيفت ٢٠٢٦-١٠-٠٨ — كان الأوّلُ أخضرَ بلا قفل، والآخران بلا اختبار):

- **قفلُ الرحلة في البدء** — بدءان معاً يرنّان مرّةً، والثاني `call_busy` لا `call_start_raced`.
- **قفلُ الرحلة في الردّ والبدء أمام إنهاء الرحلة** — `call_window_closed`، والمكالمةُ `ride_ended` بلا ردّ.
- **`FOR UPDATE` في `end_for_ride`** — إنهاءُ الرحلة لا يكتب `ride_ended` فوق مكالمةٍ أنهاها طرفُها للتوّ.
- **`FOR UPDATE` في `erase_recording`** (§٧١-ب/٧) — حذفان معاً لتسجيلٍ واحد: حذفٌ واحدٌ وسطرُ تدقيقٍ واحد.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import NotFound
from app.core.redis_client import get_redis_client
from app.models.audit import AdminAuditLog
from app.models.driver import Driver
from app.models.ride_call import RideCall
from app.models.user import User
from app.services import ride_calls
from app.services import rides as rides_service
from tests.helpers import (
    accepted_ride,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    started_ride,
)

pytestmark = pytest.mark.usefixtures("jordan_settings")

DEADLOCK_TIMEOUT = 15


async def _ringing(client: AsyncClient, session_factory) -> dict:
    await enable_features(session_factory, "ride_calls_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)
    started = await client.post(f"/rides/{ride['id']}/calls", headers=rider["headers"])
    assert started.status_code == 201, started.text
    return {
        "rider": rider,
        "driver": driver,
        "call_id": uuid.UUID(started.json()["call_id"]),
    }


async def _race(session_factory, client: AsyncClient, trip: dict, *, holder_id: str, decline: bool):
    async def _hang_up_holding_the_row() -> None:
        async with session_factory() as session:
            actor = await session.get(User, uuid.UUID(holder_id))
            await ride_calls.hang_up(session, call_id=trip["call_id"], user=actor, decline=decline)
            await asyncio.sleep(0.4)
            await session.commit()

    async def _answer_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(
            f"/calls/{trip['call_id']}/answer", json={}, headers=trip["driver"]["headers"]
        )

    _, response = await asyncio.wait_for(
        asyncio.gather(_hang_up_holding_the_row(), _answer_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )
    async with session_factory() as session:
        call = await session.get(RideCall, trip["call_id"])
    assert call is not None
    return response, call


def _coherent(call: RideCall) -> None:
    """**حالٌ واحدةٌ متّسقة**: منتهيةٌ ⇔ وقتُ انتهاءٍ وسبب، وجاريةٌ ⇔ وقتُ ردٍّ بلا انتهاء، ومدّةٌ لما رُدّ عليه وحدَه."""
    if call.status.value == "ended":
        assert call.ended_at is not None and call.end_reason is not None
        assert (call.answered_at is None) == (call.duration_seconds is None)
        if call.end_reason.value in ("cancelled", "declined", "no_answer"):
            assert call.answered_at is None
    else:
        assert call.status.value == "active" and call.answered_at is not None and call.ended_at is None


async def test_answer_racing_the_callers_end_leaves_one_coherent_status(
    client: AsyncClient, session_factory
) -> None:
    trip = await _ringing(client, session_factory)
    response, call = await _race(session_factory, client, trip, holder_id=trip["rider"]["user"]["id"], decline=False)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "call_not_ringing"
    assert call.status.value == "ended" and call.end_reason.value == "cancelled"
    _coherent(call)


async def test_answer_racing_a_decline_leaves_one_coherent_status(
    client: AsyncClient, session_factory
) -> None:
    trip = await _ringing(client, session_factory)
    response, call = await _race(session_factory, client, trip, holder_id=trip["driver"]["user_id"], decline=True)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "call_not_ringing"
    assert call.status.value == "ended" and call.end_reason.value == "declined"
    _coherent(call)


async def _trip(client: AsyncClient, session_factory, *, started: bool = False) -> dict:
    """راكبٌ وكبتنٌ في رحلةٍ قُبلت (أو بدأت) والمكالمةُ مشتعلة — بلا مكالمةٍ بعد."""
    await enable_features(session_factory, "ride_calls_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await (started_ride if started else accepted_ride)(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride_id": uuid.UUID(ride["id"])}


async def _calls_of(session_factory, ride_id: uuid.UUID) -> list[RideCall]:
    async with session_factory() as session:
        return list((await session.scalars(select(RideCall).where(RideCall.ride_id == ride_id))).all())


async def test_two_starts_at_once_ring_once(client: AsyncClient, session_factory) -> None:
    """**مكالمتان معاً على رحلةٍ واحدة** — الأولى تمسك معاملتَها مفتوحةً وصفُّ الرحلة مقفول، والثانيةُ تبدأ وهي مفتوحة.

    **بالقفل** تنتظر الثانيةُ قفلَ الرحلة فتجد الأولى ترنّ ⇒ `call_busy`. **وبحذف `with_for_update` من `trip_chat.lock_ride`**
    لا ترى الأولى (لم تلتزم)، فتُدرج وتنتظر الفهرسَ الفريد ثمّ يرتدّ قيدُه ⇒ `call_start_raced` — **رمزٌ غيرُ `call_busy` عمداً**،
    وكان الفرعُ يردّ `call_busy` نفسَه فيبقى هذا الاختبارُ أخضرَ بلا قفل (قِيس ٢٠٢٦-١٠-٠٨).
    """
    trip = await _trip(client, session_factory)

    async def _start_holding_the_ride() -> None:
        async with session_factory() as session:
            actor = await session.get(User, uuid.UUID(trip["rider"]["user"]["id"]))
            await ride_calls.start(session, get_redis_client(), ride_id=trip["ride_id"], user=actor)
            await asyncio.sleep(0.4)
            await session.commit()

    async def _start_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(f"/rides/{trip['ride_id']}/calls", headers=trip["driver"]["headers"])

    _, refused = await asyncio.wait_for(
        asyncio.gather(_start_holding_the_ride(), _start_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "call_busy"
    [call] = await _calls_of(session_factory, trip["ride_id"])
    assert call.status.value == "ringing" and call.caller_role.value == "rider"


async def test_answer_and_start_racing_completion_find_the_window_closed(
    client: AsyncClient, session_factory
) -> None:
    """**لا تصير مكالمةٌ جاريةً ولا تولد بعد انتهاء الرحلة** — الإنهاءُ يمسك معاملتَه مفتوحةً وصفُّ الرحلة مقفول، والردُّ والبدءُ يبدآن
    وهي مفتوحة.

    **بالقفل** ينتظران قفلَ الرحلة فيجدانها منتهيةً ⇒ `call_window_closed` كلاهما، **والمكالمةُ منتهيةٌ `ride_ended` بلا وقتِ ردّ**.
    **وبحذف `with_for_update` من `trip_chat.lock_ride`** يقرآن «جارية» فيمضيان: الردُّ ينتظر صفَّ المكالمة فيجدها منتهيةً
    (`call_not_ringing`)، **والبدءُ لا يرى حيّةً فيُدرج مكالمةً ترنّ بعد انتهاء الرحلة** — فيسقط هذا الاختبار.
    """
    trip = await _trip(client, session_factory, started=True)
    started = await client.post(f"/rides/{trip['ride_id']}/calls", headers=trip["rider"]["headers"])
    assert started.status_code == 201, started.text
    call_id = started.json()["call_id"]

    async def _complete_holding_the_ride() -> None:
        async with session_factory() as session:
            ride = await rides_service.get_ride(session, trip["ride_id"])
            driver = await session.get(Driver, trip["driver"]["driver_id"])
            await rides_service.complete_ride(session, ride, driver)
            await asyncio.sleep(0.4)
            await session.commit()

    async def _answer_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])

    async def _start_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(f"/rides/{trip['ride_id']}/calls", headers=trip["driver"]["headers"])

    _, answer, start = await asyncio.wait_for(
        asyncio.gather(_complete_holding_the_ride(), _answer_meanwhile(), _start_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )
    assert answer.status_code == 409 and answer.json()["code"] == "call_window_closed", answer.text
    assert start.status_code == 409 and start.json()["code"] == "call_window_closed", start.text

    [call] = await _calls_of(session_factory, trip["ride_id"])
    assert str(call.id) == call_id
    assert call.status.value == "ended" and call.end_reason.value == "ride_ended"
    assert call.answered_at is None and call.duration_seconds is None
    _coherent(call)


async def test_completion_racing_a_hang_up_keeps_the_hang_ups_reason(
    client: AsyncClient, session_factory
) -> None:
    """**`FOR UPDATE` في `end_for_ride` يملك هذا وحدَه**: الإنهاءُ من أحد الطرفين يقفل صفَّ المكالمة وحدَه (لا الرحلة)، فقفلُ الرحلة
    لا يرتّبه مع إنهاء الرحلة.

    الطرفُ ينهي المكالمةَ ويمسك معاملتَه مفتوحة، وإنهاءُ الرحلة يبدأ وهي مفتوحة. **بالقفل** ينتظر `end_for_ride` صفَّ المكالمة ثمّ
    يجدها منتهيةً فلا يلمسها ⇒ تبقى `completed` بمدّتها. **وبحذفه** يقرأ «جارية» من النسخة الملتزمة ويكتب `ride_ended` فوق
    `completed` بعد أن يلتزم الإنهاء — فيسقط هذا الاختبار.
    """
    trip = await _trip(client, session_factory, started=True)
    call_id = uuid.UUID(
        (await client.post(f"/rides/{trip['ride_id']}/calls", headers=trip["rider"]["headers"])).json()["call_id"]
    )
    answered = await client.post(f"/calls/{call_id}/answer", json={}, headers=trip["driver"]["headers"])
    assert answered.status_code == 200, answered.text

    async def _hang_up_holding_the_row() -> None:
        async with session_factory() as session:
            actor = await session.get(User, uuid.UUID(trip["rider"]["user"]["id"]))
            await ride_calls.hang_up(session, call_id=call_id, user=actor, decline=False)
            await asyncio.sleep(0.4)
            await session.commit()

    async def _complete_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(f"/rides/{trip['ride_id']}/complete", headers=trip["driver"]["headers"])

    _, done = await asyncio.wait_for(
        asyncio.gather(_hang_up_holding_the_row(), _complete_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )
    assert done.status_code == 200, done.text
    async with session_factory() as session:
        call = await session.get(RideCall, call_id)
    assert call is not None
    assert call.status.value == "ended" and call.end_reason.value == "completed"
    _coherent(call)


async def test_two_erases_at_once_erase_once(client: AsyncClient, session_factory) -> None:
    """**`FOR UPDATE` في `erase_recording`** (§٧١-ب/٧): حذفان معاً لتسجيلٍ واحد — **حذفٌ واحدٌ وسطرُ تدقيقٍ واحد**، والثاني
    `NotFound`. الأوّلُ يمسك معاملتَه مفتوحةً بعد الحذف، والثاني يبدأ وهي مفتوحة. **وبحذف القفل** يقرأ الثاني المسارَ قائماً
    (لم يُلتزم الأوّلُ بعد) فيكتب سطرَ «حذف» ثانياً لملفٍّ محاه غيرُه، ويعيد مساراً ممحوّاً — **ويسقط هذا الاختبار**."""
    trip = await _ringing(client, session_factory)
    async with session_factory() as session:
        call = await session.get(RideCall, trip["call_id"])
        call.recorded = True
        call.recording_path = "call-recordings/race.webm"
        call.recording_expires_at = datetime.now(UTC) + timedelta(days=90)
        await session.commit()

    async def _erase_holding_the_row() -> str:
        async with session_factory() as session:
            await ride_calls.erase_recording(session, call_id=trip["call_id"], actor=None, reason="تسجيلُ تجربةٍ انتهت")
            await asyncio.sleep(0.4)
            await session.commit()
            return "erased"

    async def _erase_meanwhile() -> str:
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            try:
                await ride_calls.erase_recording(session, call_id=trip["call_id"], actor=None, reason="تسجيلُ تجربةٍ انتهت")
            except NotFound:
                return "not_found"
            await session.commit()
            return "erased"

    outcomes = await asyncio.wait_for(
        asyncio.gather(_erase_holding_the_row(), _erase_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )
    assert sorted(outcomes) == ["erased", "not_found"]
    async with session_factory() as session:
        audits = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "call_recording", AdminAuditLog.entity_id == trip["call_id"]
                )
            )
        ).all()
        call = await session.get(RideCall, trip["call_id"])
    assert len(audits) == 1 and call.recording_path is None
