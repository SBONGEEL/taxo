"""تزامنُ نظام الدفع الجديد (`services/payment_requests`، SPEC §٧٣-هـ/٦) — **الدفعةُ الواحدةُ لا تُحتسب مرّتين، ولا تُحسم مرّتين**.

**والثابتُ المقيس ما يملكه قفلُ الصفِّ وحدَه**: حالةُ الطلب متّسقةٌ مع الدفتر — معتمدٌ ⇔ قيدٌ واحد، ومرفوضٌ ⇔ لا قيد — **ونجاحٌ واحدٌ
من اثنين** بالرمز المحدّد للخاسر. **واعتمادان متزامنان يُقيَّدان مرّةً واحدةً ولو حُذف القفل** (مفتاحُ الدفتر يمنع الثاني) — فذلك لا
يُثبت القفل؛ **ما يثبته أن الثاني يخسر بـ٤٠٩ لا يربح بـ٢٠٠**، وأن اعتماداً ورفضاً متداخلين لا ينتهيان صفّاً «معتمداً» مرفوضاً.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.payment_request import PaymentRequest
from app.models.wallet import WalletTransaction
from app.services import wallet
from tests.helpers import rider_session
from tests.payment_fakes import ChargilyFake, add_gateway_method, install_transport
from tests.test_payment_requests import (
    ALGERIAN_RIDER,
    PNG_OTHER,
    SECOND_ALGERIAN,
    algeria_market,
    submit,
)


async def _entries(session_factory, request_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.idempotency_key == f"payment_request:{request_id}"
            )
        )


async def test_two_approvals_at_once_credit_once_and_the_second_loses(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(f"/admin/payment-requests/{request_id}/approve", json={}, headers=admin_headers)
                for _ in range(3)
            )
        ),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 1, 409: 2})
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"invalid_status_transition"}
    assert await _entries(session_factory, request_id) == 1


async def test_an_approval_and_a_rejection_interleaved_leave_a_coherent_request(
    client: AsyncClient, session_factory, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**تداخلٌ مرتَّبٌ عمداً**: الاعتمادُ يمسك معاملتَه بعد القيد، والرفضُ يبدأ في أثنائها.

    بلا القفل يقرأ الرفضُ `pending` فيكتب «مرفوض» ويُثبّت، ثمّ يُثبّت الاعتمادُ «معتمد» فوقه — **فينجح الاثنان (٢٠٠ و٢٠٠)** وصفٌّ
    يحمل سببَ رفضٍ وقيدَ شحن. وبالقفل ينتظر الرفضُ ويقرأ «معتمد» فيخسر بـ٤٠٩.
    """
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]

    real_record = wallet.record

    async def held_record(*args, **kwargs):
        entry = await real_record(*args, **kwargs)
        await asyncio.sleep(0.6)  # **المعاملةُ مفتوحةٌ بعد القيد** — والرفضُ يبدأ الآن
        return entry

    monkeypatch.setattr(wallet, "record", held_record)

    async def reject_later():
        await asyncio.sleep(0.2)
        return await client.post(
            f"/admin/payment-requests/{request_id}/reject", json={"reason": "تجربةُ تداخل"}, headers=admin_headers
        )

    approve, reject = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/admin/payment-requests/{request_id}/approve", json={}, headers=admin_headers),
            reject_later(),
        ),
        timeout=30,
    )
    assert approve.status_code == 200, approve.text
    assert reject.status_code == 409 and reject.json()["code"] == "invalid_status_transition"
    async with session_factory() as session:
        row = await session.get(PaymentRequest, uuid.UUID(request_id))
        assert row.status.value == "approved" and row.rejection_reason is None
    assert await _entries(session_factory, request_id) == 1


async def test_two_gateway_deliveries_at_once_credit_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**ثلاثةُ إشعاراتٍ موقَّعةٍ معاً لدفعةٍ واحدةٍ قال الوسيطُ إنها دُفعت** — قيدٌ واحد، **ونجاحٌ واحدٌ يُحسب** والباقيان يجدانها محسومة."""
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    algerian = await rider_session(client, ALGERIAN_RIDER)
    opened = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": "3000"},
        headers=algerian["headers"],
    )
    request_id = opened.json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"
    body, headers = ChargilyFake.signed("chk_0001")

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(client.post("/payment-requests/webhook/chargily", content=body, headers=headers) for _ in range(3))
        ),
        timeout=30,
    )
    assert [r.status_code for r in responses] == [200, 200, 200]
    assert sum(r.json()["applied"] for r in responses) == 1
    assert await _entries(session_factory, request_id) == 1
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(algerian["user"]["id"])
            )
        )
    assert Decimal(total) == Decimal("3000")


async def test_the_same_transfer_submitted_twice_at_once_is_accepted_once(
    client: AsyncClient, session_factory
) -> None:
    ids = await algeria_market(session_factory)
    first = await rider_session(client, ALGERIAN_RIDER)
    second = await rider_session(client, SECOND_ALGERIAN)
    responses = await asyncio.wait_for(
        asyncio.gather(
            submit(client, first["headers"], ids["baridimob"], "1500", reference="BM-RACE"),
            submit(client, second["headers"], ids["baridimob"], "1500", reference="bm-race", receipt=PNG_OTHER),
        ),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses) == Counter({201: 1, 409: 1})
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"payment_already_submitted"}
