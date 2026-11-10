"""**تزامنُ معالجة حالة الطوارئ** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٧) — `services/emergency.handle`.

**ما يملكه القفل**: `handle` يقفل صفَّ الحالة **قبل** أن يقرأ حالَها. وبلا القفل يقرأ مشرفان «مفتوحة» معاً فيكتب كلٌّ ملاحظتَه فوق
الأخرى — سطرا تدقيقٍ لقرارٍ واحدٍ، **وملاحظةُ من اتّصل فعلاً تضيع تحت ملاحظة من لم يتّصل**. **فالثابتُ**: الأوّلُ ينجح والثاني
يُردّ بـ«عولجت قبلك»، وسطرُ تدقيقٍ واحد.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.user import User
from tests.helpers import rider_session

pytestmark = pytest.mark.asyncio


async def test_a_second_handler_waits_and_then_sees_it_handled(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.core.exceptions import InvalidInput
    from app.services import emergency

    rider = (await rider_session(client))["headers"]
    pressed = await client.post("/emergency", json={"app": "rider"}, headers=rider)
    assert pressed.status_code == 200, pressed.text
    alert_id = uuid.UUID(pressed.json()["id"])
    me = (await client.get("/auth/me", headers=admin_headers)).json()
    admin_id = uuid.UUID(me["id"] if "id" in me else me["user"]["id"])

    async with session_factory() as first, session_factory() as second:
        actor_a = await first.get(User, admin_id)
        await emergency.handle(first, alert_id=alert_id, actor=actor_a, note="اتّصلتُ بالراكب")
        actor_b = await second.get(User, admin_id)
        late = asyncio.create_task(emergency.handle(second, alert_id=alert_id, actor=actor_b, note="وأنا أيضاً"))
        await asyncio.sleep(0.5)
        assert not late.done(), "الثاني لم ينتظر قفلَ الأوّل — قرأ «مفتوحة» من صفٍّ لم يُلتزم بعد"
        await first.commit()
        with pytest.raises(InvalidInput):
            await asyncio.wait_for(late, timeout=10)
        await second.rollback()

    async with session_factory() as session:
        audits = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(
                AdminAuditLog.entity_type == "emergency_alert", AdminAuditLog.entity_id == alert_id
            )
        )
    assert audits == 1
