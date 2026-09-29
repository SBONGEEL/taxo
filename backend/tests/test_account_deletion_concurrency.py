"""**سباقُ الشحن مع التجهيل** — في الاتجاهين (SPEC §59-د، `account_deletion`).

**ويسقط كلٌّ بحذف ما يحرسه** — وقِيس (٢٠٢٦-٠٩-٢٩): حارسُ `wallet.record` محذوفاً
يُسقط الأوّل، وقفلُ المحفظة في `account_deletion.process_one` محذوفاً يُسقط الثاني.

والتداخلُ **مرتَّبٌ عمداً لا متروكٌ للحظ**: الأوّلُ يمسك معاملتَه، والثاني يبدأ
وهي مفتوحة — ثمّ يُفلَت الأوّل. **والمهلةُ على السيناريو كلِّه**: جمودٌ يعلّق ولا يرفع.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.exceptions import AccountDeleted
from app.models.enums import WalletOwnerType, WalletTransactionType
from app.models.user import User
from app.services import account_deletion
from app.services import wallet as wallet_service
from tests.helpers import rider_session
from tests.test_account_deletion import _due_now, _ledger, _uid, _user

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")

RACE_TIMEOUT = 20

async def test_a_credit_waiting_on_the_anonymizer_is_refused(
    client: AsyncClient, session_factory
) -> None:
    """**التجهيلُ أوّلاً**: الشحنُ ينتظر القفل ثمّ يرى الحسابَ مجهَّلاً — فيُرفض.

    احذف الحارسَ من `wallet.record` فيدخل المالُ حساباً لا صاحبَ له ويسقط هذا.
    """
    rider = await rider_session(client)
    uid = _uid(rider)
    assert (await client.post("/account/deletion", json={}, headers=rider["headers"])).status_code == 201
    await _due_now(session_factory, uid)

    holding, release = asyncio.Event(), asyncio.Event()
    results: dict[str, object] = {}

    async def anonymize() -> None:
        async with session_factory() as session:
            try:
                results["outcome"] = await account_deletion.process_one(session, uid)
            finally:
                holding.set()
            await release.wait()
            await session.commit()

    async def credit() -> None:
        await holding.wait()
        async with session_factory() as session:
            owner = await session.get(User, uid)
            try:
                await wallet_service.record(
                    session, owner=owner, owner_type=WalletOwnerType.RIDER,
                    tx_type=WalletTransactionType.TOPUP, amount=Decimal("3.000"),
                    idempotency_key=f"race:{uuid.uuid4()}",
                )
                await session.commit()
                results["credit"] = "credited"
            except AccountDeleted:
                results["credit"] = "refused"

    async def scenario() -> None:
        tasks = [asyncio.create_task(anonymize()), asyncio.create_task(credit())]
        await holding.wait()
        await asyncio.sleep(0.5)  # الشحنُ الآن ينتظر قفلَ المحفظة
        release.set()
        await asyncio.gather(*tasks)

    # **والمهلةُ على السيناريو كلِّه** لا على آخره: جمودٌ يعلّق ولا يرفع
    await asyncio.wait_for(scenario(), RACE_TIMEOUT)

    assert results["outcome"].anonymized  # type: ignore[union-attr]
    assert results["credit"] == "refused"
    assert await _ledger(session_factory, uid) == (0, Decimal("0"))


async def test_an_anonymizer_waiting_on_a_credit_defers(
    client: AsyncClient, session_factory
) -> None:
    """**الشحنُ أوّلاً**: التجهيلُ ينتظر القفل ثمّ يرى رصيداً تغيّر — فيؤجّل.

    احذف `lock_wallet` من `process_one` فيقرأ الرصيدَ قبل ثبات الشحن ويجهّل
    حساباً دخله مال — ويسقط هذا.
    """
    rider = await rider_session(client)
    uid = _uid(rider)
    assert (await client.post("/account/deletion", json={}, headers=rider["headers"])).status_code == 201
    await _due_now(session_factory, uid)

    holding, release = asyncio.Event(), asyncio.Event()
    results: dict[str, object] = {}

    async def credit() -> None:
        async with session_factory() as session:
            owner = await session.get(User, uid)
            try:
                await wallet_service.record(
                    session, owner=owner, owner_type=WalletOwnerType.RIDER,
                    tx_type=WalletTransactionType.TOPUP, amount=Decimal("3.000"),
                    idempotency_key=f"race:{uuid.uuid4()}",
                )
            finally:
                holding.set()
            await release.wait()
            await session.commit()

    async def anonymize() -> None:
        await holding.wait()
        async with session_factory() as session:
            results["outcome"] = await account_deletion.process_one(session, uid)
            await session.commit()

    async def scenario() -> None:
        tasks = [asyncio.create_task(credit()), asyncio.create_task(anonymize())]
        await holding.wait()
        await asyncio.sleep(0.5)  # التجهيلُ الآن ينتظر قفلَ المحفظة
        release.set()
        await asyncio.gather(*tasks)

    await asyncio.wait_for(scenario(), RACE_TIMEOUT)

    outcome = results["outcome"]
    assert outcome is not None and not outcome.anonymized  # type: ignore[union-attr]
    assert outcome.deferred_reason == account_deletion.DEFER_RIDER_BALANCE  # type: ignore[union-attr]
    user = await _user(session_factory, uid)
    assert user.deleted_at is None and user.phone is not None
    assert await _ledger(session_factory, uid) == (1, Decimal("3.000"))
