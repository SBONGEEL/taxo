"""حمايةُ الدفع — الموجةُ الأولى بأمر المالك ٢٠٢٦-١٠-٢٨ (SPEC §٨٧) — **ما يُقاس هنا شروطُه بلفظها**.

- **قاطعُ الدائرة**: ثلاثُ إخفاقاتٍ متتاليةٍ تُخفي الطريقة ويُشعَر المالك وتظهر لافتةُ البدائل · نجاحٌ يقطع السلسلة · البابُ العامُّ لا يعيدها ·
  المالكُ وحدَه يعيدها بسبب.
- **الصحّة**: نسبةُ النجاح من المحسوم.
- **المطابقةُ اليوميّة**: دفعةٌ دُفعت ولم تُقيَّد تُكتب افتراقاً ويُشعَر بها — **ولا قيدَ ولا تغييرَ حال**.
- **توقيعُ SofizPay**: بلا توقيعٍ أو بتوقيعٍ معبوثٍ `401`.
- **دفترُ SofizPay**: المعاملاتُ لمن مُنح الصلاحية، والرصيدُ للمالك وحدَه، والتصديرُ CSV؛ **والمراقبةُ** توقظ الحسمَ حين يصل مال.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PaymentRequestStatus, UserRole
from app.models.payment_request import PaymentRequest, PayMethod
from app.models.wallet import WalletTransaction
from app.services import payment_protection
from tests.helpers import _enable_provider, rider_session
from tests.payment_fakes import (
    SOFIZPAY_LEDGER_ACCOUNT,
    HorizonFake,
    add_gateway_method,
    install_transport,
    sofizpay_signed,
)
from tests.test_dz_payments_82 import _kinds, _owner, _queued, _staff
from tests.test_payment_requests import ALGERIAN_RIDER, algeria_market

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _every_tap_is_a_new_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """**النقرتان صفحةٌ واحدة** (§٨٢-أ/٤) — وهنا كلُّ فتحٍ دفعةٌ مستقلّة، فتُطفأ نافذتُها."""
    from app.services import payment_requests

    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)


async def _open(client: AsyncClient, headers: dict, method_id: uuid.UUID, amount: str = "3000"):
    response = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": amount},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["request"]


async def _fail_once(client, chargily, rider, method_id) -> None:
    request = await _open(client, rider["headers"], method_id)
    chargily.status[request["reference"]] = "failed"
    refreshed = await client.post(f"/payment-requests/{request['id']}/refresh", headers=rider["headers"])
    assert refreshed.json()["status"] == "rejected", refreshed.text


async def _method(session_factory, method_id) -> PayMethod:
    async with session_factory() as session:
        return await session.get(PayMethod, method_id)


async def _admin(session_factory) -> dict:
    return (await _staff(session_factory, roles=[UserRole.ADMIN], name="مشرف الاختبار"))[0]


# ------------------------------------------------------------------ ١ — قاطعُ الدائرة


async def test_three_failures_in_a_row_hide_the_method_and_only_the_owner_brings_it_back(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _queued()

    await _fail_once(client, chargily, rider, method_id)
    await _fail_once(client, chargily, rider, method_id)
    assert (await _method(session_factory, method_id)).enabled is True
    await _fail_once(client, chargily, rider, method_id)

    hidden = await _method(session_factory, method_id)
    assert hidden.enabled is False and hidden.hidden_auto is True and "3" in (hidden.hidden_reason or "")
    assert "payment_method_hidden" in _kinds(await _queued())
    listed = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()
    assert all(m["id"] != str(method_id) for m in listed["methods"])
    assert listed["paused"] == ["الذهبية وCIB"]

    admin = await _admin(session_factory)
    refused = await client.patch(f"/admin/payment-methods/{method_id}", json={"enabled": True}, headers=admin)
    assert refused.status_code == 403
    assert (await client.post(f"/admin/payment-methods/{method_id}/restore", json={"reason": "أعده"}, headers=admin)).status_code == 403

    owner = await _owner(session_factory)
    assert (await client.patch(f"/admin/payment-methods/{method_id}", json={"enabled": True}, headers=owner)).status_code == 403
    back = await client.post(
        f"/admin/payment-methods/{method_id}/restore", json={"reason": "أجاب الدعمُ وأُصلح العطب"}, headers=owner
    )
    assert back.status_code == 200, back.text
    assert back.json()["enabled"] is True and back.json()["hidden_reason"] is None
    assert (await client.get("/payment-requests/methods", headers=rider["headers"])).json()["paused"] == []


async def test_a_success_breaks_the_streak(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _fail_once(client, chargily, rider, method_id)
    await _fail_once(client, chargily, rider, method_id)
    paid = await _open(client, rider["headers"], method_id)
    chargily.status[paid["reference"]] = "paid"
    from tests.test_dz_payments_82 import _deliver

    await _deliver(client, paid["reference"])
    await _fail_once(client, chargily, rider, method_id)
    method = await _method(session_factory, method_id)
    assert method.enabled is True and method.hidden_reason is None
    owner = await _owner(session_factory)
    rows = (await client.get("/admin/payment-methods", params={"country": "DZ"}, headers=owner)).json()
    assert next(r for r in rows if r["id"] == str(method_id))["failure_streak"] == 1


async def test_the_owner_hides_a_method_with_a_reason_and_staff_cannot(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    admin = await _admin(session_factory)
    assert (await client.post(f"/admin/payment-methods/{method_id}/hide", json={"reason": "عطلٌ"}, headers=admin)).status_code == 403
    owner = await _owner(session_factory)
    done = await client.post(f"/admin/payment-methods/{method_id}/hide", json={"reason": "الدعمُ لم يجب"}, headers=owner)
    assert done.status_code == 200 and done.json()["enabled"] is False and done.json()["hidden_auto"] is False


# ------------------------------------------------------------------ ٢ — الصحّة


async def test_health_counts_success_from_decided_payments(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _fail_once(client, chargily, rider, method_id)
    paid = await _open(client, rider["headers"], method_id)
    chargily.status[paid["reference"]] = "paid"
    from tests.test_dz_payments_82 import _deliver

    await _deliver(client, paid["reference"])
    await _open(client, rider["headers"], method_id, amount="1500")
    owner = await _owner(session_factory)
    body = (await client.get("/admin/payment-health", params={"country": "DZ"}, headers=owner)).json()
    row = next(m for m in body["methods"] if m["id"] == str(method_id))
    today = row["windows"]["today"]
    assert (today["opened"], today["paid"], today["failed"], today["pending"]) == (3, 1, 1, 1)
    assert today["success_rate"] == 50 and body["streak_limit"] == 3


# ------------------------------------------------------------------ ٣ — المطابقةُ اليوميّة


async def test_daily_reconciliation_reports_paid_but_not_credited_and_writes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request = await _open(client, rider["headers"], method_id)
    chargily.status[request["reference"]] = "paid"  # دُفع عند الوسيط، ولم يصل إشعارٌ ولم تجرِ تسوية
    await _queued()
    async with session_factory() as session:
        before = await session.scalar(select(func.count()).select_from(WalletTransaction))
        report = await payment_protection.reconcile_one(
            session, "chargily", CountryCode.DZ, now=datetime.now(UTC) + timedelta(hours=1)
        )
        assert (report.checked, report.matched, report.mismatched) == (1, 0, 1)
        assert report.details["items"][0]["kind"] == "paid_not_credited"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(WalletTransaction)) == before
        row = await session.get(PaymentRequest, uuid.UUID(request["id"]))
        assert row.status is PaymentRequestStatus.PENDING
    assert "reconciliation_mismatch" in _kinds(await _queued())
    owner = await _owner(session_factory)
    log = (await client.get("/admin/payment-health/reconciliations", params={"country": "DZ"}, headers=owner)).json()
    assert log[0]["mismatched"] == 1
    admin = await _admin(session_factory)
    assert (await client.post("/admin/payment-health/reconciliations/run", headers=admin)).status_code == 403


# ------------------------------------------------------------------ ٤ — توقيعُ SofizPay


async def test_sofizpay_webhook_without_or_with_a_bad_signature_is_refused(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    await add_gateway_method(session_factory, "sofizpay")
    notice = {"event": "cib.payment.updated", "payment_status": "success", "cib_transaction_id": "2517000001", "amount": 150000}
    assert (await client.post("/payment-requests/webhook/sofizpay", json=notice)).status_code == 401
    tampered = sofizpay_signed(notice) | {"cib_transaction_id": "2517000002"}
    tampered["message"] = tampered["message"].replace("2517000001", "2517000002")
    assert (await client.post("/payment-requests/webhook/sofizpay", json=tampered)).status_code == 401
    good = await client.post("/payment-requests/webhook/sofizpay", json=sofizpay_signed(notice, url_safe=False))
    assert good.status_code == 200


# ------------------------------------------------------------------ ٥ — دفترُ SofizPay والمراقبة


async def _ledger_contract(session_factory) -> None:
    await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_LEDGER_ACCOUNT}, country="DZ")


async def test_ledger_needs_the_permission_and_the_balance_is_the_owners(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    horizon = HorizonFake()
    install_transport(monkeypatch, horizon)
    await _ledger_contract(session_factory)
    from app.services import sofizpay_ledger

    horizon.balances[SOFIZPAY_LEDGER_ACCOUNT] = [
        {"asset_type": "credit_alphanum4", "asset_code": "DZT", "asset_issuer": sofizpay_ledger.ASSET_ISSUER, "balance": "4500.0000000"},
        {"asset_type": "native", "balance": "2.5"},
    ]
    horizon.pay(SOFIZPAY_LEDGER_ACCOUNT, amount="3000.0000000", memo="TAXO شحن", created_at="2026-10-27T09:00:00Z")
    horizon.pay(SOFIZPAY_LEDGER_ACCOUNT, amount="1500.0000000", memo="TAXO اشتراك", created_at="2026-10-28T09:00:00Z")
    horizon.pay(SOFIZPAY_LEDGER_ACCOUNT, amount="9.0000000", asset_code="XLM")

    admin = await _admin(session_factory)
    assert (await client.get("/admin/sofizpay/transactions", headers=admin)).status_code == 403
    assert (await client.get("/admin/sofizpay/balance", headers=admin)).status_code == 403

    owner = await _owner(session_factory)
    balance = (await client.get("/admin/sofizpay/balance", headers=owner)).json()
    assert balance["balance"] == "4500.000" and balance["asset_code"] == "DZT"
    listed = (await client.get("/admin/sofizpay/transactions", headers=owner)).json()
    assert [e["amount"] for e in listed["entries"]] == ["1500.000", "3000.000"]
    filtered = (await client.get("/admin/sofizpay/transactions", params={"search": "اشتراك"}, headers=owner)).json()
    assert [e["amount"] for e in filtered["entries"]] == ["1500.000"]
    dated = (await client.get("/admin/sofizpay/transactions", params={"until": "2026-10-27"}, headers=owner)).json()
    assert [e["amount"] for e in dated["entries"]] == ["3000.000"]
    exported = await client.get("/admin/sofizpay/transactions.csv", headers=owner)
    assert exported.status_code == 200 and "1500.000" in exported.text and exported.headers["content-type"].startswith("text/csv")


async def test_an_arriving_payment_wakes_the_pending_sofizpay_request(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    horizon = HorizonFake()
    _, sofizpay = install_transport(monkeypatch, horizon)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    await _ledger_contract(session_factory)  # الحسابُ نفسُه بمفتاحٍ عامٍّ صالح — والفحصُ يقارن به
    from app.models.user import User

    rider = await rider_session(client, ALGERIAN_RIDER)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        user.email = "rider@example.dz"
        await session.commit()
    request = await _open(client, rider["headers"], method_id, amount="1500")
    sofizpay.check[request["reference"]] |= {"orderStatus": 2, "respCode": "00"}
    horizon.payments[SOFIZPAY_LEDGER_ACCOUNT] = []
    async with session_factory() as session:
        assert await payment_protection.watch_sofizpay(session) == 0  # الدورةُ الأولى تضع المؤشّر
    horizon.pay(SOFIZPAY_LEDGER_ACCOUNT, amount="1500.0000000")
    async with session_factory() as session:
        assert await payment_protection.watch_sofizpay(session) == 1
    async with session_factory() as session:
        row = await session.get(PaymentRequest, uuid.UUID(request["id"]))
        assert row.status is PaymentRequestStatus.APPROVED
