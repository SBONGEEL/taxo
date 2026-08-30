"""اختبارات تزامن حقيقية على دفتر المحفظة (SPEC القسم 4/14).

بقية الاختبارات تُرسل طلباً ثم تنتظر جوابه، فلا تمر أبداً بالمسار الذي كُتب
القفل الاستشاري من أجله. هذه تُطلق الطلبات معاً بـ `asyncio.gather` على نفس
حلقة الأحداث: كل طلب يأخذ جلسته ومعاملته واتصاله من المجمّع، فينتظر أحدهما
قفلَ الآخر في القاعدة فعلاً لا نظرياً.

الثابت المُختبَر واحد في كلها: **مجموع ما نجح لا يتجاوز الرصيد**، ولا ينتهي
سباقٌ برصيدٍ سالب ولا بـ `balance_after` كاذب. الاختبار صحيح حتى لو لم
يتداخل الطلبان في تشغيلةٍ ما — لكنه لا يمر أبداً إن كان القفل مكسوراً.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from httpx import AsyncClient, Response
from sqlalchemy import func, select

from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    OTHER_RIDER,
    RIDER,
    approved_driver,
    auth,
    register,
    topup_wallet,
    wallet_of,
)


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


def _statuses(responses: list[Response]) -> Counter:
    return Counter(response.status_code for response in responses)


async def _ledger_sum(session_factory, user_id: str) -> str:
    """الرصيد مقروءاً من القاعدة مباشرة — لا من الـ API الذي قد يخطئ معه."""
    import uuid as _uuid

    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == _uuid.UUID(user_id)
            )
        )
    return str(total)


# ------------------------------------------------------------------ التحويل


async def test_concurrent_transfers_cannot_overdraw_the_wallet(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """خمسة تحويلات معاً من رصيدٍ يكفي ثلاثة — ينجح ثلاثة لا أكثر."""
    sender = await _rider(client)
    recipient = await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "10.000")

    responses = await asyncio.gather(
        *(
            client.post(
                "/wallet/me/transfers",
                json={
                    "recipient_phone": OTHER_RIDER["phone"],
                    "amount": "3.000",
                    # مفاتيح مختلفة عمداً: هذا سباقٌ على الرصيد لا تكرارُ عملية
                    "idempotency_key": f"race-transfer-{index}",
                },
                headers=sender["headers"],
            )
            for index in range(5)
        )
    )

    counts = _statuses(responses)
    assert counts[200] == 3, counts
    assert counts[409] == 2, counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "insufficient_balance"
    }

    assert (await wallet_of(client, sender["headers"]))["balance"] == "1.000"
    assert (await wallet_of(client, recipient["headers"]))["balance"] == "9.000"
    # ولا قيدَ خلّف رصيداً سالباً في لقطته
    assert await _ledger_sum(session_factory, sender["user_id"]) == "1.000"

    async with session_factory() as session:
        lowest = await session.scalar(select(func.min(WalletTransaction.balance_after)))
    assert lowest >= 0


async def test_same_idempotency_key_under_race_debits_once(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """نفس المفتاح من خمسة طلبات متزامنة = قيدٌ واحد (SPEC القسم 14).

    الفحص يقع بعد أخذ القفل لا قبله، فيتسلسل المتسابقون ويجد التالي قيدَ
    الأول بدل أن يصطدم بالقيد الفريد.
    """
    sender = await _rider(client)
    await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "40.000")

    payload = {
        "recipient_phone": OTHER_RIDER["phone"],
        "amount": "7.000",
        "idempotency_key": "one-and-only-key",
    }
    responses = await asyncio.gather(
        *(
            client.post("/wallet/me/transfers", json=payload, headers=sender["headers"])
            for _ in range(5)
        )
    )

    assert _statuses(responses) == Counter({200: 5})
    assert len({response.json()["id"] for response in responses}) == 1
    assert (await wallet_of(client, sender["headers"]))["balance"] == "33.000"

    async with session_factory() as session:
        transfers = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == "transfer_out"
            )
        )
    assert transfers == 1


async def test_transfers_in_opposite_directions_do_not_deadlock(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    """أ→ب وب→أ معاً: الترتيب الثابت للقفلين يمنع الجمود."""
    first = await _rider(client)
    second = await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, first["user_id"], "20.000")
    await topup_wallet(client, admin_headers, second["user_id"], "20.000")

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                "/wallet/me/transfers",
                json={
                    "recipient_phone": OTHER_RIDER["phone"],
                    "amount": "5.000",
                    "idempotency_key": "cross-a-to-b",
                },
                headers=first["headers"],
            ),
            client.post(
                "/wallet/me/transfers",
                json={
                    "recipient_phone": RIDER["phone"],
                    "amount": "8.000",
                    "idempotency_key": "cross-b-to-a",
                },
                headers=second["headers"],
            ),
        ),
        # جمودٌ حقيقي لا ينكشف بخطأ بل بتعليقٍ إلى الأبد — فالمهلة هي الحكم
        timeout=20,
    )

    assert _statuses(list(responses)) == Counter({200: 2})
    assert (await wallet_of(client, first["headers"]))["balance"] == "23.000"
    assert (await wallet_of(client, second["headers"]))["balance"] == "17.000"


# -------------------------------------------------------------------- السحب


async def test_concurrent_withdrawals_cannot_reserve_the_same_money(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """أربعة طلبات سحبٍ معاً بكامل الرصيد — يُقبل واحد فقط."""
    driver = await approved_driver(client, session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "60.000")

    responses = await asyncio.gather(
        *(
            client.post(
                "/wallet/me/withdrawals",
                json={"amount": "60.000", "method": "bank"},
                headers=driver["headers"],
            )
            for _ in range(4)
        )
    )

    counts = _statuses(responses)
    assert counts[201] == 1, counts
    assert counts[409] == 3, counts

    wallet = (await client.get("/wallet/me/driver", headers=driver["headers"])).json()
    assert wallet["balance"] == "60.000"
    assert wallet["available_for_withdrawal"] == "0.000"


async def test_concurrent_paid_marks_debit_only_once(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """ضغطتان متزامنتان على «مدفوع» لا تخصمان مرتين."""
    driver = await approved_driver(client, session_factory, DRIVER)
    await topup_wallet(client, admin_headers, driver["user_id"], "60.000")

    created = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "25.000", "method": "bank"},
        headers=driver["headers"],
    )
    request_id = created.json()["id"]
    await client.post(f"/admin/withdrawals/{request_id}/approve", headers=admin_headers)

    responses = await asyncio.gather(
        *(
            client.post(
                f"/admin/withdrawals/{request_id}/paid",
                json={"reference": "TRX-RACE"},
                headers=admin_headers,
            )
            for _ in range(3)
        )
    )

    # الرابح واحد والباقون يرتدّون عن آلة الحالات نفسها — لا عن مفتاح عدم
    # التكرار وحده. القفل على صف الطلب هو ما يجعل الحارسين يعملان معاً.
    counts = _statuses(responses)
    assert counts == Counter({200: 1, 409: 2}), counts
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {
        "invalid_status_transition"
    }
    assert (await wallet_of(client, driver["headers"]))["balance"] == "35.000"

    async with session_factory() as session:
        debits = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == "withdrawal"
            )
        )
    assert debits == 1


# -------------------------------------------------------------------- الشحن


async def test_concurrent_topup_confirmations_credit_once(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """تأكيدان متزامنان لنفس طلب الشحن — رصيدٌ يزيد مرة واحدة."""
    rider = await _rider(client)
    created = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "18.000", "reference": "CLQ-RACE"},
        headers=rider["headers"],
    )
    request_id = created.json()["id"]

    responses = await asyncio.gather(
        *(
            client.post(
                f"/admin/topups/{request_id}/confirm", json={}, headers=admin_headers
            )
            for _ in range(3)
        )
    )

    counts = _statuses(list(responses))
    assert counts == Counter({200: 1, 409: 2}), counts
    assert (await wallet_of(client, rider["headers"]))["balance"] == "18.000"
    async with session_factory() as session:
        topup_entries = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.type == "topup"
            )
        )
    assert topup_entries == 1
