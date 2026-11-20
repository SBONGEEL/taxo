"""«تعديل الوجهة» تحت التزامن (SPEC §١٠٩-أ) — `destination_change.confirm` يقفل الرحلةَ ثمّ صفَّ العرض قبل أن يقرأ حالَه.

**ما يملكه القفلُ وحدَه**: أن يُطبَّق العرضُ مرّةً واحدة — قيدُ تدقيقٍ واحدٌ وإشعارٌ واحد — مهما وصل من تأكيداتٍ معاً (زرٌّ ضُغط
مرّتين، أو إعادةٌ بعد انقطاع الشبكة تسبق جوابَ الأولى). **وقِيس بحذفه**: ثلاثةُ قيودٍ لا واحد (`assert 3 == 1`).
"""

from __future__ import annotations

import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from tests.helpers import RIDER, auth, enable_features, register, request_ride

SEARCHING = "destination_change_searching"
NEW_TARGET = {"lat": 31.9700, "lng": 35.8700, "address": "دوار الداخلية"}


async def _confirm(client: AsyncClient, headers: dict, ride_id: str, change_id: str):
    return await client.post(f"/rides/{ride_id}/destination/{change_id}/confirm", headers=headers)


async def _audits(session_factory, ride_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(
                AdminAuditLog.entity_type == "ride", AdminAuditLog.entity_id == uuid.UUID(ride_id)
            )
        )


async def test_two_confirms_at_once_apply_once(
    client: AsyncClient, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**التزامن**: تأكيداتٌ في اللحظة نفسِها — قفلُ الرحلة يجعل ما بعد الأوّل يرى «مؤكَّداً» فيردّ ولا يطبّق.

    **والتشابكُ مقصودٌ لا موكولٌ للحظّ**: الأوّلُ يُمسك معاملتَه مفتوحةً بعد أن قرأ (تأخيرٌ في قيد التدقيق) فيدخل الآخرون وهو لم
    يودع. **وحذفُ `with_for_update` من `confirm`** يجعلهم يقرؤون `quoted` معاً فتُكتب قيودٌ لا قيدٌ واحد."""
    from app.services import destination_change as service

    original = service.audit.record

    async def slow_record(*args, **kwargs):
        await asyncio.sleep(0.4)
        return await original(*args, **kwargs)

    monkeypatch.setattr(service.audit, "record", slow_record)
    await enable_features(session_factory, SEARCHING)
    rider = auth(await register(client, RIDER))
    ride = await request_ride(client, rider)
    quote = (await client.post(f"/rides/{ride['id']}/destination/quote", json=NEW_TARGET, headers=rider)).json()

    results = await asyncio.wait_for(
        asyncio.gather(*(_confirm(client, rider, ride["id"], quote["id"]) for _ in range(3))), timeout=30
    )
    assert [r.status_code for r in results] == [200, 200, 200]
    assert await _audits(session_factory, ride["id"]) == 1
