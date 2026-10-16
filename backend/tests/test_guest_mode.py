"""وضعُ الضيف (SPEC §٧٦-ن/أ، أمرُ المالك ٢٠٢٦-١٠-١٥).

**وما يُقاس هنا حدودُ الخادم لا المحاكاة** (المحاكاةُ في التطبيقين): المفتاحُ مطفأٌ افتراضاً ولكلِّ تطبيقٍ وحدَه · رمزُ الضيف لا يفتح
بابَ حسابٍ ولا محفظة · الحدُّ لكلِّ جهاز · «أرسل ملاحظة» تصل اللوحةَ موسومةً «ضيف» · **لا صفَّ في `users` ولا قيدَ في الدفتر** ·
والمحوُ بعد ٣٠ يوماً ومعه الملاحظات.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.feedback import AppFeedback
from app.models.guest import GuestSession
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import guest as guest_service

pytestmark = pytest.mark.asyncio


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _switch(client, admin_headers, **apps):
    answer = await client.put("/admin/guest-mode", json=apps, headers=admin_headers)
    assert answer.status_code == 200, answer.text
    return answer.json()


async def _start(client, app="rider", device="device-under-test-1"):
    return await client.post("/guest/sessions", json={"app": app, "device_id": device})


async def test_guest_mode_is_off_until_the_panel_turns_it_on(client, admin_headers, session_factory) -> None:
    config = (await client.get("/config")).json()
    assert config["guest_mode"] == {"rider": False, "driver": False}
    assert (await _start(client)).status_code == 404

    assert await _switch(client, admin_headers, rider=True) == {"rider": True, "driver": False}
    assert (await client.get("/config")).json()["guest_mode"] == {"rider": True, "driver": False}
    assert (await _start(client)).status_code == 201
    # **كلُّ تطبيقٍ بمفتاحه** — الكبتنُ مطفأٌ ما دام لم يُشعل
    assert (await _start(client, app="driver")).status_code == 404

    async with session_factory() as session:
        rows = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "guest_mode_settings"))
        ).all()
    assert rows and rows[-1].details["fields"] == ["rider_enabled"]


async def test_support_cannot_switch_it(client, support_headers) -> None:
    assert (await client.put("/admin/guest-mode", json={"rider": True}, headers=support_headers)).status_code == 403


async def test_a_guest_token_opens_no_account_door(client, admin_headers) -> None:
    """**نوعُه `guest` لا `access`** — لا حسابَ ولا محفظةَ ولا رحلة."""
    await _switch(client, admin_headers, rider=True, driver=True)
    token = (await _start(client)).json()["token"]
    for path in ("/auth/me", "/wallet/me", "/rides/me"):
        assert (await client.get(path, headers=_bearer(token))).status_code == 401, path


async def test_guest_creation_is_limited_per_device(client, admin_headers) -> None:
    await _switch(client, admin_headers, rider=True)
    codes = [(await _start(client, device="same-device-0001")).status_code for _ in range(guest_service.PER_DEVICE_PER_DAY + 1)]
    assert codes[:-1] == [201] * guest_service.PER_DEVICE_PER_DAY
    assert codes[-1] == 429
    # جهازٌ آخر لا يدفع ثمنَ الأوّل
    assert (await _start(client, device="other-device-002")).status_code == 201


async def test_guest_feedback_reaches_the_panel_marked_guest(client, admin_headers) -> None:
    await _switch(client, admin_headers, driver=True)
    token = (await _start(client, app="driver")).json()["token"]
    sent = await client.post(
        "/guest/feedback", data={"app": "driver", "message": "تجربةُ ضيف — الشريطُ واضح"}, headers=_bearer(token)
    )
    assert sent.status_code == 201, sent.text
    assert (await client.post("/guest/feedback", data={"app": "driver", "message": "x"})).status_code == 401

    listed = (await client.get("/admin/feedback", headers=admin_headers)).json()
    mine = [item for item in listed["items"] if item["message"].startswith("تجربةُ ضيف")]
    assert len(mine) == 1
    assert mine[0]["is_guest"] is True
    assert mine[0]["user_id"] is None and mine[0]["user_name"] is None


async def test_a_guest_writes_no_user_and_no_ledger_entry(client, admin_headers, session_factory) -> None:
    """**لا يُعدّ في أيِّ مقياس ولا يمسّ مالاً** — بالبناء: لا صفَّ في `users` ولا في الدفتر."""
    async with session_factory() as session:
        users_before = await session.scalar(select(func.count()).select_from(User))
        ledger_before = await session.scalar(select(func.count()).select_from(WalletTransaction))
    await _switch(client, admin_headers, rider=True)
    token = (await _start(client)).json()["token"]
    await client.post("/guest/feedback", data={"app": "rider", "message": "ملاحظة"}, headers=_bearer(token))
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == users_before
        assert await session.scalar(select(func.count()).select_from(WalletTransaction)) == ledger_before
        assert await session.scalar(select(func.count()).select_from(GuestSession)) == 1


async def test_guest_data_is_gone_after_thirty_days(client, admin_headers, session_factory) -> None:
    await _switch(client, admin_headers, rider=True)
    old = (await _start(client, device="old-device-0001")).json()["token"]
    fresh = (await _start(client, device="new-device-0001")).json()["token"]
    for token in (old, fresh):
        await client.post("/guest/feedback", data={"app": "rider", "message": "ملاحظة"}, headers=_bearer(token))
    async with session_factory() as session:
        rows = (await session.scalars(select(GuestSession).order_by(GuestSession.created_at))).all()
        rows[0].created_at = datetime.now(UTC) - timedelta(days=guest_service.RETENTION_DAYS + 1)
        await session.commit()
    async with session_factory() as session:
        await guest_service.expired(session)
        await session.commit()
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(GuestSession)) == 1
        assert await session.scalar(
            select(func.count()).select_from(AppFeedback).where(AppFeedback.guest_session_id.is_not(None))
        ) == 1
    # **وجلسةٌ مُحيت لا تكتب بعدها**
    gone = await client.post("/guest/feedback", data={"app": "rider", "message": "x"}, headers=_bearer(old))
    assert gone.status_code == 401


async def test_the_network_region_is_published_raw(client) -> None:
    """**خارجَ أسواقنا** (SPEC §٧٦-ن/٦): الحرفان كما هما — و`XX` ليس بلداً."""
    assert (await client.get("/config", headers={"CF-IPCountry": "eg"})).json()["network_region"] == "EG"
    assert (await client.get("/config", headers={"CF-IPCountry": "XX"})).json()["network_region"] is None
    assert (await client.get("/config")).json()["network_region"] is None
