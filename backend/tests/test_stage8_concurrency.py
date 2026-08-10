"""تزامنُ المسارين الماليين اللذين أضافتهما المرحلة 8.

كل مسارٍ يحرّك مالاً في هذا المشروع يُختبر تحت التزامن لا بالتتابع: الاختبار
المتتابع لا يدخل المسار الذي وُجد القفل من أجله أصلاً، فيمر أخضرَ على كودٍ
بلا قفل. الطلبات تُطلق معاً بـ `asyncio.gather` على نفس `client` (جلسةٌ
ومعاملةٌ لكل طلب، فينتظر أحدهما قفل الآخر في postgres فعلاً)، والحكمُ على
**الثابت** لا على الترتيب: كم نجح، وبأي رمزٍ سقط الباقي، وما مجموع الدفتر
مقروءاً من القاعدة.

التحقق من الاختبارين: بحذف القفل يسقطان.
- `cliq_topups.apply_state` بلا `for_update` → قيدا شحنٍ لطلبٍ واحد.
- `withdrawals.pay_via_provider` بلا قفل الطلب → حوالتان وقيدا سحب.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.enums import WalletTransactionType
from app.models.wallet import WalletTransaction
from tests.helpers import (
    COMPANY_CLIQ_ALIAS,
    approved_driver,
    enable_cliq_provider,
    enable_features,
    enable_payout_provider,
    rider_session,
    set_cliq_alias,
    topup_wallet,
    wallet_of,
)

TOPUP_AMOUNT = "25.000"
BALANCE = "80.000"
WITHDRAWAL_AMOUNT = "30.000"

# مهلةٌ تحرس من الجمود: الجمود يعلّق ولا يرفع استثناءً، فلا يكشفه إلا انتهاؤها
DEADLOCK_TIMEOUT = 20.0


async def _ledger_sum(session_factory, owner_id: str) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(owner_id)
            )
        )
    return Decimal(total)


async def _entries(session_factory, owner_id: str, tx_type) -> list:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(owner_id),
                    WalletTransaction.type == tx_type,
                )
            )
        )


async def test_concurrent_cliq_checks_credit_the_wallet_once(
    client: AsyncClient, session_factory
) -> None:
    """ثلاثة استعلامات متزامنة على حوالةٍ واحدة = قيدُ شحنٍ واحد."""
    from app.services.cliq.mock import MockCliqProvider

    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)
    me = (await client.get("/auth/me", headers=rider["headers"])).json()

    created = await client.post(
        "/wallet/me/topups/cliq",
        json={"amount": TOPUP_AMOUNT},
        headers=rider["headers"],
    )
    cart_id = created.json()["cart_id"]
    await MockCliqProvider(
        get_redis_client(), company_alias=COMPANY_CLIQ_ALIAS
    ).set_outcome(cart_id, "paid")

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.get(
                    f"/wallet/me/topups/cliq/{cart_id}", headers=rider["headers"]
                )
                for _ in range(3)
            )
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    # كلها تنجح — الاستعلام المتأخر يجد الطلب محسوماً فلا يقيّد شيئاً ثانياً
    assert Counter(response.status_code for response in responses) == {200: 3}
    assert {response.json()["status"] for response in responses} == {"paid"}

    entries = await _entries(
        session_factory, me["id"], WalletTransactionType.TOPUP
    )
    assert len(entries) == 1
    assert await _ledger_sum(session_factory, me["id"]) == Decimal(TOPUP_AMOUNT)
    assert (await wallet_of(client, rider["headers"]))["balance"] == TOPUP_AMOUNT


async def test_two_provider_answers_at_once_leave_a_coherent_order(
    client: AsyncClient, session_factory
) -> None:
    """جوابان متضاربان من المزود في آنٍ واحد — وهذا ما يحرسه قفل الصف.

    الاختبار السابق يمر بلا قفلٍ أصلاً: مفتاح عدم التكرار في الدفتر والقفل
    الاستشاري للمحفظة يمنعان الشحن مرتين وحدهما. أما **حالة الطلب** فلا يحرسها
    إلا القفل: بغيره يقرأ المساران `created` معاً فيكتب أحدهما `failed`
    والآخر `paid` — فيبقى طلبٌ ساقطٌ وقد قُيّد ماله، أو مدفوعٌ بلا قيد.

    فالثابت المُختبَر هو الاقتران لا العدد: `paid` ⇔ قيدٌ واحد، و`failed` ⇔
    لا قيد. وبحذف `for_update` من `apply_state` يسقط هذا الاختبار.
    """
    from app.services import cliq_topups
    from app.services.cliq import CliqChargeState

    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await rider_session(client)
    me = (await client.get("/auth/me", headers=rider["headers"])).json()

    created = await client.post(
        "/wallet/me/topups/cliq",
        json={"amount": TOPUP_AMOUNT},
        headers=rider["headers"],
    )
    cart_id = created.json()["cart_id"]
    provider_ref = f"mock-cliq-{cart_id}"

    def _state(paid: bool) -> CliqChargeState:
        return CliqChargeState(
            provider_ref=provider_ref,
            settled=True,
            paid=paid,
            status_text="paid" if paid else "لم تصل الحوالة",
            amount=Decimal(TOPUP_AMOUNT) if paid else None,
        )

    # التداخل مُرتَّب عمداً لا متروكٌ للحظ: الأول يقرأ ويكتب ولا يُثبّت بعد،
    # والثاني يبدأ وهو مفتوح. بالقفل ينتظر الثاني حتى يرى `paid` فينصرف؛
    # بغيره يقرأ `created` فيكتب `failed` فوق طلبٍ قُيّد مالُه.
    async def _apply_paid_holding_the_transaction() -> None:
        async with session_factory() as session:
            await cliq_topups.apply_state(
                session, cart_id=cart_id, state=_state(True)
            )
            await asyncio.sleep(0.3)
            await session.commit()

    async def _apply_failed_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            await cliq_topups.apply_state(
                session, cart_id=cart_id, state=_state(False)
            )
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(
            _apply_paid_holding_the_transaction(), _apply_failed_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    async with session_factory() as session:
        final = await cliq_topups.get_order(session, cart_id)
    entries = await _entries(session_factory, me["id"], WalletTransactionType.TOPUP)

    if final.status.value == "paid":
        assert len(entries) == 1
        assert final.transaction_id is not None
        assert await _ledger_sum(session_factory, me["id"]) == Decimal(TOPUP_AMOUNT)
    else:
        assert final.status.value == "failed"
        assert entries == []
        assert final.transaction_id is None


async def test_concurrent_payouts_transfer_once(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """ضغطتان متزامنتان على «حوّل آلياً» = حوالةٌ واحدة وقيدُ سحبٍ واحد."""
    await enable_payout_provider(session_factory)
    driver = await approved_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"])
    await topup_wallet(client, admin_headers, driver["user_id"], BALANCE)

    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": WITHDRAWAL_AMOUNT, "method": "cliq"},
        headers=driver["headers"],
    )
    request_id = created.json()["id"]
    await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(
                    f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
                )
                for _ in range(3)
            )
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    codes = Counter(response.status_code for response in responses)
    assert codes == {200: 1, 409: 2}, codes
    losers = [r for r in responses if r.status_code == 409]
    assert {r.json()["code"] for r in losers} == {"invalid_status_transition"}

    entries = await _entries(
        session_factory, driver["user_id"], WalletTransactionType.WITHDRAWAL
    )
    assert len(entries) == 1
    assert entries[0].balance_after >= 0
    assert await _ledger_sum(session_factory, driver["user_id"]) == Decimal(
        BALANCE
    ) - Decimal(WITHDRAWAL_AMOUNT)


async def test_concurrent_cliq_topup_and_payout_do_not_deadlock(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_wallet
) -> None:
    """مساران يأخذان أقفالاً مختلفة على نفس المحفظة في آنٍ واحد.

    القفل الاستشاري للمحفظة يأتي **آخراً** في الترتيب عند كليهما، فلا يقابل
    أحدُهما الآخر — والمهلة هي ما يكشف خلاف ذلك، إذ الجمود يعلّق ولا يرفع.
    """
    from app.services.cliq.mock import MockCliqProvider

    # `jordan_wallet` يرفع `wallet_enabled` سلفاً، وتفعيلُ عقد كليك يرفع مفتاحه
    await enable_cliq_provider(session_factory)
    await enable_payout_provider(session_factory)

    driver = await approved_driver(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"])
    await topup_wallet(client, admin_headers, driver["user_id"], BALANCE)

    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": WITHDRAWAL_AMOUNT, "method": "cliq"},
        headers=driver["headers"],
    )
    request_id = created.json()["id"]
    await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )

    topup = await client.post(
        "/wallet/me/topups/cliq",
        json={"amount": TOPUP_AMOUNT},
        headers=driver["headers"],
    )
    cart_id = topup.json()["cart_id"]
    await MockCliqProvider(
        get_redis_client(), company_alias=COMPANY_CLIQ_ALIAS
    ).set_outcome(cart_id, "paid")

    checked, paid = await asyncio.wait_for(
        asyncio.gather(
            client.get(
                f"/wallet/me/topups/cliq/{cart_id}", headers=driver["headers"]
            ),
            client.post(
                f"/admin/withdrawals/{request_id}/payout", headers=admin_headers
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert checked.status_code == 200, checked.text
    assert paid.status_code == 200, paid.text
    expected = Decimal(BALANCE) + Decimal(TOPUP_AMOUNT) - Decimal(WITHDRAWAL_AMOUNT)
    assert await _ledger_sum(session_factory, driver["user_id"]) == expected
