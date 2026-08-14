"""سلفتان في اللحظة نفسِها (البند ١٥) — وهذا هو المكانُ الذي يخرج منه المال.

**والسباقُ واقعيٌّ لا مفتعل**: ضغطتان على زرٍّ بطيءٍ في شبكةٍ ضعيفة — وهو ما
يفعله كلُّ من ينتظر مالاً. وما يقع بغير حارسٍ ليس خطأً مرئياً بل **ضِعفُ السقف
يخرج من المنصّة**، والسقفُ هو الحماية الوحيدة التي أقرّها المالك («الحمايةُ في
الحجم لا في التحصيل»).

**وثلاثةُ حرّاسٍ هنا، وقياسُهم بالحذف صحّح ما ظننتُه قبله** — نفسُ درسِ البقشيش
(12-و) حرفياً:

- **الفهرسُ الجزئي** (`uq_advance_outstanding`) يملك **الصرف** وحدَه: بحذف
  القفلين معاً يبقى `test_two_requests_at_once_disburse_exactly_one` أخضر. فما
  يحرس المالَ من الخروج مرتين ليس قفلاً بل صفٌّ لا يمكن أن يُكتب مرتين.
- **وقفلُ صفِّ الكبتن في الراوتر** و**قفلُ صفِّ السلفة في الخدمة** يملكان
  **السداد** — وكلٌّ منهما يكفي وحدَه: بحذف أحدهما يبقى الاختبار أخضر، وبحذفهما
  معاً يصير `Counter({200: 2})` (مقيسٌ لا مفترَض): سدادان يقرآن «٢٫٠٠٠ باقية»
  معاً فيخصمان ٤٫٠٠٠ من محفظةٍ فيها ١٠. **ولا استثناءَ يُرفع ولا سطرَ لوج**:
  رصيدٌ ينقص ضعفَ الدَّين، وكشفٌ فيه سدادان لسلفةٍ واحدة.

فالقفلُ الثاني ليس تكراراً بل **ترتيبُ أقفال**: الراوترُ يقفل صفَّ الكبتن كما
يفعل مسارُ الاشتراك، والخدمةُ تقفل صفَّها هي لأن `deduct_from_earning` تُنادى
من `payments.settle` بلا مرورٍ بذلك الراوتر أصلاً.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.advance import DriverAdvance
from app.models.enums import AdvanceStatus, WalletTransactionType
from app.models.wallet import WalletTransaction

from tests.helpers import DRIVER, approved_driver, topup_wallet
from tests.test_advances import _enable, _qualify

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")

DEADLOCK_TIMEOUT = 20.0


async def _driver(client, session_factory, phone: str, plate: str) -> dict:
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": phone, "name": "كبتنُ التزامن"},
        plate_number=plate,
        subscribed=False,
    )
    await _qualify(session_factory, driver["driver_id"])
    return driver


async def test_two_requests_at_once_disburse_exactly_one(
    client: AsyncClient, session_factory
) -> None:
    """**سلفةٌ واحدةٌ تُصرف، والثانيةُ تُرفض** — والدفترُ يحمل قيداً واحداً.

    والحكمُ على الدفتر لا على الردود: ردّان بـ201 وقيدٌ واحدٌ حالةٌ ممكنةٌ
    أسوأُ من رفضٍ صريح، لأن المنصّة تظنّ أنها صرفت مرتين.
    """
    await _enable(session_factory)
    driver = await _driver(client, session_factory, "0796662001", "AMM-2001")

    async def take() -> int:
        response = await client.post(
            "/drivers/me/advances",
            json={"amount": "2.000"},
            headers=driver["headers"],
        )
        return response.status_code

    codes = Counter(
        await asyncio.wait_for(
            asyncio.gather(take(), take(), return_exceptions=False),
            timeout=DEADLOCK_TIMEOUT,
        )
    )
    assert codes[201] == 1, f"صُرفت أكثرُ من سلفةٍ على سقفٍ واحد: {codes}"
    assert sum(codes.values()) == 2

    async with session_factory() as session:
        rows = list(await session.scalars(select(DriverAdvance)))
        assert len(rows) == 1, "صفّان لكبتنٍ واحد — الفهرسُ الجزئيّ لم يحرس"
        credits = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"])),
                WalletTransaction.type == WalletTransactionType.ADVANCE,
            )
        )
        assert credits == 1, "مالٌ خرج مرتين على دَينٍ واحد"


async def test_a_second_repayment_finds_nothing_to_take(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**هذا ما يملكه القفلُ وحدَه**: المتبقّي بين قراءته وخصمه.

    والفهرسُ لا يرى هذا أصلاً — الصفُّ قائمٌ وواحد، والسدادان يقعان عليه هو.
    بحذف `with_for_update` من `outstanding_for` يقرأ النداءان «٢٫٠٠٠ باقية»
    معاً فيخصمان ٤٫٠٠٠ من محفظةٍ فيها ١٠ — **ولا استثناءَ يُرفع**: رصيدٌ ينقص
    ضعفَ الدَّين، وسلفةٌ مسدَّدةٌ مرتين في كشفِ صاحبها.
    """
    await _enable(session_factory)
    driver = await _driver(client, session_factory, "0796662002", "AMM-2002")
    taken = await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )
    assert taken.status_code == 201, taken.text
    await topup_wallet(client, admin_headers, driver["user_id"], "10.000")

    async def repay() -> int:
        response = await client.post(
            "/drivers/me/advances/repay", headers=driver["headers"]
        )
        return response.status_code

    codes = Counter(
        await asyncio.wait_for(
            asyncio.gather(repay(), repay(), return_exceptions=False),
            timeout=DEADLOCK_TIMEOUT,
        )
    )
    assert codes[200] == 1 and codes[404] == 1, f"سدادان مرّا معاً: {codes}"

    async with session_factory() as session:
        repayments = list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"])),
                    WalletTransaction.type
                    == WalletTransactionType.ADVANCE_REPAYMENT,
                )
            )
        )
        assert len(repayments) == 1, "خُصم السدادُ مرتين من محفظةٍ حقيقية"
        assert repayments[0].amount == Decimal("-2.000")

        advance = await session.scalar(select(DriverAdvance))
        assert advance is not None and advance.status is AdvanceStatus.REPAID

        # والدفترُ يبقى موجباً ومتّسقاً مع نفسه — كأيّ اختبار مالٍ في المشروع
        rows = list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"]))
                )
            )
        )
        assert all(row.balance_after >= 0 for row in rows)
        assert sum(row.amount for row in rows) == Decimal("10.000")
