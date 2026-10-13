"""تصفيرُ ما قبل الإطلاق (SPEC §٧٤-ح) — **يُقاس على شرط المالك بلفظه، وكلُّ شرطٍ يسقط بحذف ما يحرسه**.

١) **التصديرُ قبل الكتابة**، والمعاينةُ لا تكتب.
٢) **كلُّ محفظةٍ إلى الصفر بقيد تصحيحٍ واحدٍ موسوم** «تصفير ما قبل الإطلاق» — **ولا يُحذف قيد** (عددُ القيود يزيد ولا ينقص).
٣) **المستحقُّ والسلفةُ يُشطبان بالسبب نفسِه** — ولا قيدَ لهما في الدفتر.
٤) **الاشتراكُ لا يُمسّ**، **و`--keep` يُبقي ما قرّر المالكُ إبقاءه**.
٥) **معلَّقٌ لم يكن حين قِيس يوقف كلَّ شيء** — ولا يُلغى من هنا.
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.advance import DriverAdvance
from app.models.debt import DriverDebt
from app.models.enums import AdvanceStatus, DriverDebtStatus, WalletOwnerType, WalletTransactionType
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import wallet
from scripts import prelaunch_reset_74 as script
from tests.helpers import OTHER_RIDER, SECOND_DRIVER, register, set_cliq_alias, set_commission
from tests.test_advances import _enable, _ready_driver
from tests.test_driver_debt import _cash_ride_settled

pytestmark = pytest.mark.asyncio


async def _credit(session_factory, user_id: str, owner_type: WalletOwnerType, amount: str) -> None:
    """**رصيدٌ بتصحيحٍ إداريّ** — كرصيد الكبتن «ج» على الإنتاج (تصحيحٌ لجولة قياس)."""
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_id))
        await wallet.record(
            session, owner=user, owner_type=owner_type, tx_type=WalletTransactionType.ADJUSTMENT,
            amount=Decimal(amount), reference="تصحيحُ جولة قياس",
        )
        await session.commit()


async def _balances(session_factory) -> dict[tuple[uuid.UUID, str], Decimal]:
    async with session_factory() as session:
        rows = await session.execute(
            select(WalletTransaction.owner_id, WalletTransaction.owner_type, func.sum(WalletTransaction.amount)).group_by(
                WalletTransaction.owner_id, WalletTransaction.owner_type
            )
        )
        return {(owner, str(kind)): Decimal(total) for owner, kind, total in rows.all()}


async def test_everything_goes_to_zero_by_marked_entries_and_subscriptions_stay(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, tmp_path: Path
) -> None:
    # ── العالمُ كما قِيس على الإنتاج: مستحقُّ عمولة · سلفةٌ قائمة · رصيدُ تصحيح · وراكبٌ يقرّر المالكُ إبقاءه ──
    await set_commission(session_factory, "15")
    debtor, _ = await _cash_ride_settled(client, session_factory)
    await _enable(session_factory)
    borrower = await _ready_driver(client, session_factory, payload=SECOND_DRIVER, plate_number="AMM-7777")
    taken = await client.post("/drivers/me/advances", json={"amount": "2.000"}, headers=borrower["headers"])
    assert taken.status_code == 201, taken.text
    await _credit(session_factory, str(debtor["user_id"]), WalletOwnerType.DRIVER, "35.000")
    kept = await register(client, {**OTHER_RIDER, "phone": "0790000888"})
    await _credit(session_factory, kept["user"]["id"], WalletOwnerType.RIDER, "5.000")

    async with session_factory() as session:
        subscriptions_before = sorted(
            (row.id, row.status, row.expires_at) for row in await session.scalars(select(DriverSubscription))
        )
        entries_before = await session.scalar(select(func.count()).select_from(WalletTransaction))
    assert subscriptions_before, "كبتنٌ مشتركٌ واحدٌ على الأقلّ — وإلا لم يُقس أن الاشتراكَ لا يُمسّ"
    balances_before = await _balances(session_factory)
    nonzero_before = {key for key, value in balances_before.items() if value != 0}
    assert len(nonzero_before) >= 3

    # ── المعاينة: تصديرٌ بإذن 600، ولا شيءَ يتغيّر ──
    preview = tmp_path / "preview.json"
    await script.main_async(export=preview, write=False, keep=set(), session_factory=session_factory)
    assert stat.S_IMODE(os.stat(preview).st_mode) == 0o600
    exported = json.loads(preview.read_text(encoding="utf-8"))
    assert len(exported["debts"]) == 1 and len(exported["advances"]) == 1
    assert {row["balance"] for row in exported["wallets"]} >= {"5.000"}
    assert "phone" not in preview.read_text(encoding="utf-8") and "name" not in exported["wallets"][0]
    assert await _balances(session_factory) == balances_before

    # ── الكتابة ──
    keep = {uuid.UUID(kept["user"]["id"])}
    await script.main_async(export=tmp_path / "reset.json", write=True, keep=keep, session_factory=session_factory)

    after = await _balances(session_factory)
    for key, value in after.items():
        assert value == (Decimal("5.000") if key[0] in keep else 0), key
    async with session_factory() as session:
        marked = list(
            await session.scalars(select(WalletTransaction).where(WalletTransaction.reference == script.RESET_MARK))
        )
        assert len(marked) == len(nonzero_before) - 1, "قيدٌ واحدٌ لكلِّ محفظةٍ صُفِّرت — والمُبقاةُ بلا قيد"
        assert all(row.type is WalletTransactionType.ADJUSTMENT for row in marked)
        assert await session.scalar(select(func.count()).select_from(WalletTransaction)) == entries_before + len(marked)

        debt = await session.scalar(select(DriverDebt))
        assert (debt.status, debt.writeoff_reason, debt.written_off_by) == (DriverDebtStatus.WRITTEN_OFF, script.RESET_MARK, None)
        advance = await session.scalar(select(DriverAdvance))
        assert (advance.status, advance.writeoff_reason) == (AdvanceStatus.WRITTEN_OFF, script.RESET_MARK)

        assert sorted(
            (row.id, row.status, row.expires_at) for row in await session.scalars(select(DriverSubscription))
        ) == subscriptions_before


async def test_keep_spares_a_captains_wallet_and_advance_together(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, tmp_path: Path
) -> None:
    """**مالُ كبتنٍ يقرّر المالكُ أنه حقيقيّ** يُبقى كلُّه — رصيدُه وسلفتُه معاً، **لا الرصيدُ وحدَه وسلفتُه تُشطب من تحته**."""
    await _enable(session_factory)
    borrower = await _ready_driver(client, session_factory)
    taken = await client.post("/drivers/me/advances", json={"amount": "2.000"}, headers=borrower["headers"])
    assert taken.status_code == 201, taken.text
    before = await _balances(session_factory)

    await script.main_async(
        export=tmp_path / "keep.json", write=True, keep={uuid.UUID(str(borrower["user_id"]))}, session_factory=session_factory
    )
    assert await _balances(session_factory) == before
    async with session_factory() as session:
        assert (await session.scalar(select(DriverAdvance))).status is AdvanceStatus.OUTSTANDING


async def test_a_pending_item_that_was_not_there_stops_everything(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, tmp_path: Path
) -> None:
    """**سحبٌ ينتظر** ظهر بعد القياس ⇒ يقف بنصٍّ يسمّيه، **ولا يُكتب قيدٌ واحد**."""
    await _enable(session_factory)
    driver = await _ready_driver(client, session_factory)
    await _credit(session_factory, str(driver["user_id"]), WalletOwnerType.DRIVER, "40.000")
    await set_cliq_alias(session_factory, driver["driver_id"])
    asked = await client.post("/wallet/me/withdrawals", json={"amount": "20.000", "method": "cliq"}, headers=driver["headers"])
    assert asked.status_code in (200, 201), asked.text
    before = await _balances(session_factory)

    async with session_factory() as session:
        with pytest.raises(script.ResetRefused, match="withdrawal_requests"):
            await script.reset(session, keep=set())
        await session.rollback()
    assert await _balances(session_factory) == before
