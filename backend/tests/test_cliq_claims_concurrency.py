"""تزامنُ «حوّلتُ» — **والقفلُ يُقاس بحذفه** (2026-09-01).

**وملفٌّ باسمه**: `test_locks_have_tests` **لا يقرأ إلا `test_*concurrency*.py`**
— فاختبارٌ صحيحٌ في ملفٍّ لا يطابق الاسمَ **يمرّ ولا يُحسب**.

**وتشابكٌ مرتَّبٌ لا `gather` على بابين**: نداءان في `gather` يتشابكان فقط إن
شاءت حلقةُ الأحداث، **فيمرّ الاختبارُ لأن التزامنَ لم يقع لا لأن القفلَ عمل**.
"""

from __future__ import annotations

import asyncio

from httpx import AsyncClient
from sqlalchemy import select

from app.models.provider_order import ProviderOrder
from app.models.user import User
from app.services import cliq_claims
from tests.helpers import DRIVER, approved_driver, ensure_plan


async def test_two_simultaneous_presses_stamp_once(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**ضغطتان متشابكتان: ختمٌ واحدٌ ووقتٌ واحد.**

    **وبلا القفل تمرّان معاً**: كلتاهما تقرأ `declared_paid_at` فارغاً
    وكلتاهما تختم — **وهو ختمان لتحويلٍ واحد**، وأحدُهما يكتب وقتاً غيرَ
    الآخر **فيرتّب المشرفُ قائمتَه بوقتٍ لم يقع**.

    **وقِيس بحذف القفل**: نُزع `.with_for_update()` من `_locked_by_cart`
    **فمرّت الثانيةُ بلا انتظار** ولم تقف — وأُعيد فاخضرّ.
    """
    await ensure_plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    plans = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    opened = await client.post(
        "/subscriptions/cliq",
        json={"plan_id": plans[0]["id"]},
        headers=driver["headers"],
    )
    cart_id = opened.json()["cart_id"]

    async with session_factory() as first, session_factory() as second:
        owner_one = await first.scalar(
            select(User).where(User.phone == "+962792222222")
        )
        owner_two = await second.scalar(
            select(User).where(User.phone == "+962792222222")
        )

        # ── الأولى تختم **وتُبقي معاملتَها مفتوحة**
        await cliq_claims.declare_paid(first, cart_id=cart_id, user=owner_one)

        # ── والثانيةُ تبدأ فتقف على القفل
        blocked = asyncio.create_task(
            cliq_claims.declare_paid(second, cart_id=cart_id, user=owner_two)
        )
        await asyncio.sleep(0.3)
        assert not blocked.done(), (
            "الثانيةُ لم تقف على القفل — **وهذا هو العطبُ نفسُه**: قرأت "
            "الحقلَ فارغاً والأولى لم تودع بعد."
        )

        await first.commit()
        second_order = await blocked
        # **والوقتُ وقتُ الأولى** — والثانيةُ تجده مختوماً فلا تكتب
        assert second_order.declared_paid_at is not None
        await second.commit()

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(ProviderOrder).where(ProviderOrder.cart_id == cart_id)
            )
        )
    assert len(rows) == 1
