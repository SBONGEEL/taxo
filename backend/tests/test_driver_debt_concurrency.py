"""تزامنُ سدادِ دَينِ الكبتن — `debts` و`cliq_debts` (الترحيلة `0061`).

**وما يملكه القفلُ هنا ليس مبلغاً مضاعفاً بل حالاً متماسكة.**

`debts.apply_settlement` يقرأ `collected` ثم يكتبه. **وبلا `with_for_update`
يقرأ تأكيدان متزامنان القيمةَ نفسَها**، فيكتب كلٌّ منهما `collected` محسوباً من
قراءةٍ قديمة — **ويُعلن كلٌّ منهما أنه طبّق المبلغَ كاملاً**. فيقرأ المشرفُ
تأكيدين ناجحين، **والدَّينُ نقص مرّةً واحدة**، ولا شيءَ يفشل.

**وقيدُ القاعدة لا يمسك هذا**: `collected <= amount` يمنع الفيضَ ولا يمنع
**الكتابةَ فوق كتابة**.

**ويقيس هذا الملفُّ الخدمتين معاً بابٌ واحد**: `cliq_debts.confirm_payment`
يقفل صفَّ المطالبة ثم ينادي `debts.apply_settlement` الذي يقفل صفوفَ الدَّين.
**فمساران متزامنان على المطالبة نفسِها يمرّان بالقفلين**.

**وما لا يفحصه**: أنّ الاختبارَ يسقط بحذف القفل — **قِيس بيد**: بنزع
`with_for_update` من `debts.outstanding_rows` يصير المطبَّقُ `0.800 + 0.800`
والدَّينُ نقص `0.800` وحدَه.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.debt import DriverDebt
from app.models.enums import DriverDebtStatus
from tests.helpers import (
    completed_ride,
    pay_ride,
    set_commission,
)
from tests.test_payments import _only, _online_driver, _rider

pytestmark = pytest.mark.asyncio


async def _driver_with_debt(client: AsyncClient, session_factory) -> dict:
    """كبتنٌ عليه مستحقٌّ واحد — من رحلةِ كاشٍ بعمولةٍ ورصيدٍ صفر."""
    await set_commission(session_factory, "10")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    assert (
        await client.post(
            f"/payments/{payment['id']}/confirm", headers=driver["headers"]
        )
    ).status_code == 200
    return driver


async def _outstanding(session_factory, driver_id) -> Decimal:
    async with session_factory() as session:
        rows = list(
            (
                await session.scalars(
                    select(DriverDebt).where(DriverDebt.driver_id == driver_id)
                )
            ).all()
        )
    return sum((row.amount - row.collected for row in rows), Decimal("0"))


async def test_two_confirmations_of_one_claim_reduce_the_debt_once(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**تأكيدان متزامنان على مطالبةٍ واحدة**: واحدٌ يمرّ والدَّينُ ينقص مرّةً.

    **والخاسرُ يُردّ بحالٍ لا بمهلة**: `InvalidStatusTransition` — المطالبةُ
    لم تعد `created`.
    """
    driver = await _driver_with_debt(client, session_factory)
    due = await _outstanding(session_factory, driver["driver_id"])
    assert due == Decimal("0.800")

    claim = await client.post(
        "/drivers/me/debt/cliq",
        json={"amount": str(due)},
        headers=driver["headers"],
    )
    assert claim.status_code == 201, claim.text
    claim_id = claim.json()["id"]

    # **معاً على نفس الصفّ** — جلستان ومعاملتان، فإحداهما تنتظر قفلَ الأخرى
    results = await asyncio.wait_for(
        asyncio.gather(
            *[
                client.post(
                    f"/admin/drivers/debts/claims/{claim_id}/confirm",
                    json={"credited": str(due)},
                    headers=admin_headers,
                )
                for _ in range(2)
            ],
            return_exceptions=True,
        ),
        # **المهلةُ هي ما يُفشل الجمود**: الجمودُ يعلّق ولا يرفع استثناءً
        timeout=30.0,
    )
    codes = Counter(
        r.status_code for r in results if not isinstance(r, BaseException)
    )
    assert codes[200] == 1, f"لم يمرّ واحدٌ بالضبط — {codes}"
    assert sum(codes.values()) == 2 and codes[200] == 1, codes

    assert await _outstanding(session_factory, driver["driver_id"]) == Decimal("0"), (
        "الدَّينُ لم يبلغ صفراً — أو نقص مرّتين"
    )
    async with session_factory() as session:
        rows = list(
            (
                await session.scalars(
                    select(DriverDebt).where(
                        DriverDebt.driver_id == driver["driver_id"]
                    )
                )
            ).all()
        )
    assert len(rows) == 1
    assert rows[0].status is DriverDebtStatus.SETTLED
    assert rows[0].collected == rows[0].amount


async def test_the_block_lifts_only_when_the_debt_reaches_zero(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """**سدادان جزئيّان متتاليان**: المنعُ يبقى حتى الصفر، ثم يُرفع.

    **ويُقاس هنا لا في اختبارِ الوحدة** لأن `refresh_block` تقع داخل المعاملة
    التي يقفلها التأكيد — **ورفعُ المنع بعد المعاملة يترك نافذةً** يقرأ فيها
    التوزيعُ كبتناً ممنوعاً وقد سدّد.
    """
    from app.models.driver import Driver

    driver = await _driver_with_debt(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.debt_blocked = True
        await session.commit()

    for part in ("0.300", "0.500"):
        claim = await client.post(
            "/drivers/me/debt/cliq",
            json={"amount": part},
            headers=driver["headers"],
        )
        assert claim.status_code == 201, claim.text
        confirmed = await client.post(
            f"/admin/drivers/debts/claims/{claim.json()['id']}/confirm",
            json={"credited": part},
            headers=admin_headers,
        )
        assert confirmed.status_code == 200, confirmed.text

        async with session_factory() as session:
            row = await session.get(Driver, driver["driver_id"])
            still = await _outstanding(session_factory, driver["driver_id"])
        if still > 0:
            assert row.debt_blocked is True, "رُفع المنعُ قبل الصفر"

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
    assert await _outstanding(session_factory, driver["driver_id"]) == Decimal("0")
    assert row.debt_blocked is False, "بلغ الصفرَ ولم يُرفع المنع"
