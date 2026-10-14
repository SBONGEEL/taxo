"""قفلُ `feedback.set_handled` — **ما يملكه وحدَه**: موظّفان يعلّمان ملاحظةً «عولجت» معاً، **فيبقى ختمُ الأوّل ولا يكتب الثاني فوقه**.

**بتداخلٍ مرتَّبٍ عمداً** (نمطُ `test_stage8_concurrency.py`): الأوّلُ يمسك معاملته مفتوحةً والثاني يبدأ. **بالقفل** ينتظر الثاني ثمّ يقرأ
الختمَ فيتركه؛ **وبلا قفل** يقرأ ما قبل التزام الأوّل («لم تُعالَج») فيكتب نفسَه فوقه — **ويسقط هذا الاختبار** (قِيس بحذف القفل).
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.feedback import AppFeedback
from app.models.user import User
from app.services import feedback
from tests.helpers import RIDER, auth, register

pytestmark = pytest.mark.asyncio


async def test_two_staff_marking_at_once_keep_the_first_stamp(
    client: AsyncClient, session_factory, admin_headers, support_headers
) -> None:
    rider = auth(await register(client, RIDER))
    sent = await client.post("/feedback", data={"app": "rider", "message": "ملاحظة"}, headers=rider)
    assert sent.status_code == 201, sent.text

    async with session_factory() as session:
        feedback_id = await session.scalar(select(AppFeedback.id))
        first = await session.scalar(select(User).where(User.phone == "+962790000001"))
        second = await session.scalar(select(User).where(User.phone == "+962790000002"))

    async with session_factory() as session_a, session_factory() as session_b:
        row_a = await feedback.set_handled(session_a, feedback_id, admin=first, handled=True)
        stamp_a = row_a.handled_at

        async def _second() -> None:
            await feedback.set_handled(session_b, feedback_id, admin=second, handled=True)
            await session_b.commit()

        waiting = asyncio.create_task(_second())
        await asyncio.sleep(0.5)
        assert not waiting.done(), "الثاني لم ينتظر — لا قفلَ يمسك الصفّ"
        await session_a.commit()
        await asyncio.wait_for(waiting, timeout=10)

    async with session_factory() as session:
        row = await session.get(AppFeedback, feedback_id)
    assert row.handled_by == first.id, "كتب الثاني فوق ختم الأوّل"
    assert row.handled_at == stamp_a
