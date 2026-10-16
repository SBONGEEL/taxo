"""مفتاحُ وضع الضيف تحت التزامن (SPEC §٧٦-ن/٤) — **ما يملكه قفلُ `guest.update`**.

مشرفان يشعلان مفتاحَ الراكب في اللحظة نفسِها: **تغييرٌ واحدٌ وسطرُ تدقيقٍ واحد**. وبلا القفل يقرأ كلاهما «مطفأ» فيكتب كلٌّ «تغيّر» ويُسجَّل
تغييران لتغييرٍ واحد. **والتداخلُ مرتَّبٌ لا متروكٌ للحظّ**: الأوّلُ يقف بعد قراءته المقفلة حتى يبدأ الثاني.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.services import guest as guest_service

pytestmark = pytest.mark.asyncio


async def test_two_admins_switching_at_once_write_one_change(client, admin_headers, session_factory, monkeypatch) -> None:
    # الصفُّ موجودٌ مطفأً (كما تكتبه الترحيلة)
    async with session_factory() as session:
        await guest_service.update(session, rider=False, driver=False)
        await session.commit()

    real = guest_service._locked_row
    read = asyncio.Event()
    calls = 0

    async def held(session):
        nonlocal calls
        row = await real(session)
        calls += 1
        if calls == 1:
            read.set()
            await asyncio.sleep(1.5)
        return row

    monkeypatch.setattr(guest_service, "_locked_row", held)

    first = asyncio.create_task(client.put("/admin/guest-mode", json={"rider": True}, headers=admin_headers))
    await asyncio.wait_for(read.wait(), timeout=15)
    second = asyncio.create_task(client.put("/admin/guest-mode", json={"rider": True}, headers=admin_headers))
    answers = await asyncio.wait_for(asyncio.gather(first, second), timeout=30)
    assert [a.status_code for a in answers] == [200, 200]

    async with session_factory() as session:
        lines = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.entity_type == "guest_mode_settings")
        )
    assert lines == 1
