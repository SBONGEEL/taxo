"""تزامنُ محادثة الرحلة (`services/trip_chat`) — **ما يملكه القفلُ وحدَه، مقيساً بتداخلٍ مرتَّبٍ لا متروكٍ للحظ**.

١) **إرسالٌ يسابق إنهاءَ الرحلة لا يقع بعده أبداً**: الإنهاءُ يمسك معاملتَه مفتوحةً وصفُّ الرحلة مقفول، والإرسالُ يبدأ وهو مفتوح.
   بالقفل ينتظر الإرسالُ فيجد الرحلةَ منتهيةً فيُردّ `chat_closed`؛ **وبحذف `with_for_update` من `trip_chat.lock_ride`** يقرأ
   `in_progress` ويُدرج رسالةً تلتزم بعد الإنهاء — فيسقط هذا الاختبار (مقيسٌ بالحذف، انظر التقرير).
٢) **معالجتان لبلاغٍ واحد**: الأولى تمسك صفَّه، والثانيةُ تجده معالَجاً فتُردّ — **وبغير القفل تكتب معالِجاً ثانياً فوق الأوّل**.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.driver import Driver
from app.models.ride import Ride
from app.models.trip_chat import RideMessage
from app.models.user import User
from app.services import rides as rides_service
from app.services import trip_chat
from tests.conftest import _staff_headers
from tests.helpers import (
    accepted_ride,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    started_ride,
)

pytestmark = pytest.mark.usefixtures("jordan_settings")

#: جمودٌ لا يرفع استثناءً بل يعلّق — فالمهلةُ وحدَها تُسقطه
DEADLOCK_TIMEOUT = 15


async def _trip(client: AsyncClient, session_factory, *, started: bool) -> dict:
    await enable_features(session_factory, "trip_chat_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await (started_ride if started else accepted_ride)(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride": ride}


async def test_a_send_racing_completion_never_lands_after_it(client: AsyncClient, session_factory) -> None:
    trip = await _trip(client, session_factory, started=True)
    ride_id = uuid.UUID(trip["ride"]["id"])

    async def _complete_holding_the_ride() -> None:
        async with session_factory() as session:
            ride = await rides_service.get_ride(session, ride_id)
            driver = await session.get(Driver, trip["driver"]["driver_id"])
            await rides_service.complete_ride(session, ride, driver)
            await asyncio.sleep(0.4)
            await session.commit()

    async def _send_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(
            f"/rides/{ride_id}/chat", json={"body": "هل وصلنا؟"}, headers=trip["rider"]["headers"]
        )

    _, response = await asyncio.wait_for(
        asyncio.gather(_complete_holding_the_ride(), _send_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "chat_closed"
    async with session_factory() as session:
        ride = await session.get(Ride, ride_id)
        messages = (await session.scalars(select(RideMessage).where(RideMessage.ride_id == ride_id))).all()
    assert ride is not None and ride.completed_at is not None
    # **والثابتُ نفسُه بصيغته العامّة**: لا رسالةَ بعد الانتهاء
    assert all(message.created_at <= ride.completed_at for message in messages)
    assert messages == []


async def test_two_handlings_of_one_report_leave_one_handler(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    trip = await _trip(client, session_factory, started=False)
    ride_id = trip["ride"]["id"]
    sent = await client.post(
        f"/rides/{ride_id}/chat", json={"body": "كلامٌ مسيء"}, headers=trip["driver"]["headers"]
    )
    report = (
        await client.post(
            f"/rides/{ride_id}/chat/{sent.json()['id']}/report",
            json={"reason": "abuse"},
            headers=trip["rider"]["headers"],
        )
    ).json()

    readers = []
    for phone, name in (("+962790000041", "معالِجٌ أوّل"), ("+962790000042", "معالِجٌ ثانٍ")):
        headers = await _staff_headers("admin", phone, name)
        me = (await client.get("/auth/me", headers=headers)).json()
        rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
        row = next(item for item in rows if item["user_id"] == me["id"])
        granted = await client.put(
            f"/admin/permissions/{me['id']}",
            json={"permissions": sorted(set(row["permissions"]) | {"trip_chats.read"})},
            headers=admin_headers,
        )
        assert granted.status_code == 200, granted.text
        readers.append({"headers": headers, "id": uuid.UUID(me["id"])})

    async def _handle_holding_the_row() -> None:
        async with session_factory() as session:
            actor = await session.get(User, readers[0]["id"])
            await trip_chat.handle_report(
                session, report_id=uuid.UUID(report["id"]), actor=actor, note="الأوّل"
            )
            await asyncio.sleep(0.4)
            await session.commit()

    async def _handle_meanwhile():
        await asyncio.sleep(0.1)
        return await client.post(
            f"/admin/chat-reports/{report['id']}/handle", json={"note": "الثاني"}, headers=readers[1]["headers"]
        )

    _, response = await asyncio.wait_for(
        asyncio.gather(_handle_holding_the_row(), _handle_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "chat_report_already_handled"

    async with session_factory() as session:
        handled = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "ride_message_report")
            )
        ).all()
        from app.models.trip_chat import RideMessageReport

        row = await session.get(RideMessageReport, uuid.UUID(report["id"]))
    assert row is not None and row.handled_by == readers[0]["id"] and row.handled_note == "الأوّل"
    assert len(handled) == 1
