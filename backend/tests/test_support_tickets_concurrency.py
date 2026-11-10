"""**تزامنُ حسم الطلب** (البندان ٨ و٩) — `support_tickets.decide` يقفل الصفَّ قبل فحص الانتقال.

**يسقط بحذف القفل**: بلا `with_for_update` في `support_tickets._locked` يقرأ الحسمُ الثلاثةُ «open» معاً فيمرّون كلُّهم (`Counter({200: 3})`)
ويُبلَّغ صاحبُ الطلب ثلاثَ مرّاتٍ بقراراتٍ متناقضة.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter

from httpx import AsyncClient
from sqlalchemy import select

from app.models.support_ticket import SupportTicket
from tests.helpers import inbox_of, rider_session


async def test_two_concurrent_decisions_one_wins(client: AsyncClient, session_factory, admin_headers: dict, monkeypatch) -> None:
    """**القفلُ يملك الحال**: بلا `with_for_update` يقرأ الحسمان «open» معاً فيكتب الثاني فوق الأوّل ويُبلَّغ صاحبُها مرّتين."""
    rider = await rider_session(client)
    opened = await client.post("/support/tickets", data={"app": "rider", "kind": "support", "body": "سؤال"}, headers=rider["headers"])
    ticket_id = opened.json()["id"]

    # **تداخلٌ مقصود**: كلُّ حسمٍ يُمسك معاملتَه مفتوحةً بعد الفحص وقبل الالتزام — فبلا القفل يقرأ الثاني «open» والأوّلُ لم يلتزم
    from app.services import audit

    original = audit.record

    async def slow_record(*args, **kwargs):
        await asyncio.sleep(0.4)
        return await original(*args, **kwargs)

    monkeypatch.setattr(audit, "record", slow_record)

    async def decide(status: str):
        return await client.patch(
            f"/admin/support/tickets/{ticket_id}", json={"status": status, "reason": f"قرار {status}"}, headers=admin_headers
        )

    results = await asyncio.wait_for(asyncio.gather(decide("resolved"), decide("rejected"), decide("resolved")), timeout=30)
    codes = Counter(r.status_code for r in results)
    assert codes == Counter({200: 1, 409: 2}), codes
    assert all(r.json()["code"] == "support_ticket_transition" for r in results if r.status_code == 409)
    async with session_factory() as session:
        row = await session.scalar(select(SupportTicket).where(SupportTicket.id == uuid.UUID(ticket_id)))
        assert row is not None and row.status in ("resolved", "rejected")
    status_notes = [
        n for n in await inbox_of(session_factory, uuid.UUID(rider["user"]["id"])) if n.data.get("ticket_id") == ticket_id
    ]
    assert len(status_notes) == 1
