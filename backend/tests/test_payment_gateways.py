"""الوسيطان الآليّان — المرحلة ٣ (SPEC §٧٣-هـ): **صفحةُ الوسيط، والإشعارُ يوقظ ولا يُصدَّق، والفحصُ المباشرُ يقرّر**.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة (`tests/payment_fakes.py`) بأشكال الوثائق المنشورة.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.models.payment_request import PaymentRequest
from app.models.wallet import WalletTransaction
from tests.helpers import RIDER, rider_session
from tests.money_format import offenders
from tests.payment_fakes import (
    CHARGILY_SECRET,
    SOFIZPAY_ACCOUNT,
    ChargilyFake,
    add_gateway_method,
    install_transport,
    sofizpay_signed,
)
from tests.test_payment_requests import ALGERIAN_RIDER, algeria_market, balance


async def open_checkout(client: AsyncClient, headers: dict, method_id: uuid.UUID, amount: str = "3000"):
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": amount},
        headers=headers,
    )


async def _entries(session_factory, request_id: str) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.idempotency_key == f"payment_request:{request_id}"
            )
        )


# ------------------------------------------------------------------ Chargily


async def test_a_chargily_checkout_sends_whole_dinars_and_who_pays_the_fees(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily", fee_bearer="user")
    rider = await rider_session(client, ALGERIAN_RIDER)

    methods = (await client.get("/payment-requests/methods", headers=rider["headers"])).json()["methods"]
    gateway = next(m for m in methods if m["id"] == str(method_id))
    assert gateway["gateway"] is True and gateway["requires_receipt"] is False

    opened = await open_checkout(client, rider["headers"], method_id)
    assert opened.status_code == 201, opened.text
    body = opened.json()
    assert body["checkout_url"].startswith("https://pay.chargily.dz/test/checkouts/")
    assert body["request"]["status"] == "pending" and body["request"]["amount"] == "3000"
    assert offenders(body["request"]) == []
    sent = chargily.created[0]
    assert sent["amount"] == 3000 and sent["currency"] == "dzd"
    assert sent["chargily_pay_fees_allocation"] == "customer"
    assert sent["webhook_endpoint"].endswith("/payment-requests/webhook/chargily")
    assert "/wallet/pay/return?r=" in sent["success_url"]
    # **ولا رصيدَ قبل أن يقول الوسيط**
    assert await balance(client, rider["headers"]) == "0"


async def test_the_webhook_wakes_and_the_direct_check_decides(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    opened = (await open_checkout(client, rider["headers"], method_id)).json()
    checkout_id = chargily.created and "chk_0001"
    request_id = opened["request"]["id"]

    forged_body, _ = ChargilyFake.signed(checkout_id)
    forged = await client.post("/payment-requests/webhook/chargily", content=forged_body,
                               headers={"signature": "0" * 64, "content-type": "application/json"})
    assert forged.status_code == 401

    # **إشعارٌ صحيحُ التوقيع والوسيطُ ما زال يقول «معلّق»** ⇐ لا قيد: الحمولةُ لا تُصدَّق
    body, headers = ChargilyFake.signed(checkout_id)
    early = await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)
    assert early.status_code == 200 and early.json()["applied"] == 0
    assert await balance(client, rider["headers"]) == "0"

    chargily.status[checkout_id] = "paid"
    for expected in (1, 0):
        delivered = await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)
        assert delivered.status_code == 200 and delivered.json()["applied"] == expected
    assert await balance(client, rider["headers"]) == "3000"
    assert await _entries(session_factory, request_id) == 1


async def test_a_different_amount_at_the_gateway_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await open_checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = "paid"
    chargily.amount["chk_0001"] = 300
    body, headers = ChargilyFake.signed("chk_0001")
    assert (await client.post("/payment-requests/webhook/chargily", content=body, headers=headers)).status_code == 200
    mine = (await client.get("/payment-requests/me", headers=rider["headers"])).json()[0]
    # **دُفع ⇐ لا يُرفض** (SPEC §٨٢-أ/٢): المالُ دخل بمبلغٍ آخر — «قيد المعالجة» بسببه، ولا قيدَ بتخمين، والمالكُ يُشعَر إن طال
    assert mine["id"] == request_id and mine["status"] == "pending" and mine["phase"] == "processing"
    assert "لا يطابق" in mine["outcome_note"]
    assert await balance(client, rider["headers"]) == "0"


@pytest.mark.parametrize(("status", "expected"), [("failed", "rejected"), ("canceled", "cancelled"), ("processing", "pending")])
async def test_refresh_reads_every_gateway_state(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, status: str, expected: str
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await open_checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    chargily.status["chk_0001"] = status
    refreshed = await client.post(f"/payment-requests/{request_id}/refresh", headers=rider["headers"])
    assert refreshed.status_code == 200 and refreshed.json()["status"] == expected


async def test_only_the_owner_refreshes(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await open_checkout(client, rider["headers"], method_id)).json()["request"]["id"]
    from tests.test_payment_requests import SECOND_ALGERIAN

    stranger = await rider_session(client, SECOND_ALGERIAN)
    assert (await client.post(f"/payment-requests/{request_id}/refresh", headers=stranger["headers"])).status_code == 404


# ------------------------------------------------------------------ SofizPay


async def test_sofizpay_is_decided_by_its_check_not_its_notice(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await rider_session(client, ALGERIAN_RIDER)
    async with session_factory() as session:
        from app.models.user import User

        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        if hasattr(user, "email"):
            user.email = "rider@example.dz"
        await session.commit()
    opened = await open_checkout(client, rider["headers"], method_id, "1500")
    assert opened.status_code == 201, opened.text
    sent = sofizpay.created[0]
    assert sent["account"] == SOFIZPAY_ACCOUNT and sent["amount"] == "1500" and sent["redirect"] == "no"
    cib_id = opened.json()["request"]["reference"]

    # **إشعارٌ موقَّعٌ بطريقة الـSDK** (§٨٧/٥) — يُقرأ معرّفُه وحدَه، والفحصُ يقول «معلّق» ⇐ لا شيء
    notice = sofizpay_signed({"event": "cib.payment.updated", "payment_status": "success", "cib_transaction_id": cib_id, "amount": 150000})
    assert (await client.post("/payment-requests/webhook/sofizpay", json=notice)).json()["applied"] == 0

    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00"}
    assert (await client.post("/payment-requests/webhook/sofizpay", json=notice)).json()["applied"] == 1
    assert await balance(client, rider["headers"]) == "1500"


async def test_sofizpay_money_to_another_account_is_refused(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    _, sofizpay = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "sofizpay")
    rider = await rider_session(client, ALGERIAN_RIDER)
    async with session_factory() as session:
        from app.models.user import User

        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        if hasattr(user, "email"):
            user.email = "rider@example.dz"
        await session.commit()
    opened = (await open_checkout(client, rider["headers"], method_id, "1500")).json()
    cib_id = opened["request"]["reference"]
    sofizpay.check[cib_id] |= {"orderStatus": 2, "respCode": "00", "destination_account": "GSOMEONEELSE"}
    refreshed = await client.post(f"/payment-requests/{opened['request']['id']}/refresh", headers=rider["headers"])
    assert refreshed.json()["status"] == "rejected" and await balance(client, rider["headers"]) == "0"


# ------------------------------------------------------------------ اللوحة


async def test_a_gateway_method_needs_its_contract_and_honest_fees(
    client: AsyncClient, session_factory, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_transport(monkeypatch)
    base = {"country_code": "DZ", "kind": "bank_transfer", "name": "الذهبية", "enabled": True}
    no_contract = await client.post("/admin/payment-methods", json=base | {"code": "chargily", "integration": "chargily"},
                                    headers=admin_headers)
    assert no_contract.status_code == 422 and no_contract.json()["field"] == "enabled"
    from tests.helpers import _enable_provider

    await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_ACCOUNT}, country="DZ")
    user_fees = await client.post("/admin/payment-methods",
                                  json=base | {"code": "sofizpay", "integration": "sofizpay", "fee_bearer": "user"},
                                  headers=admin_headers)
    assert user_fees.status_code == 422 and user_fees.json()["field"] == "fee_bearer"
    ok = await client.post("/admin/payment-methods", json=base | {"code": "sofizpay", "integration": "sofizpay"},
                           headers=admin_headers)
    assert ok.status_code == 201 and ok.json()["fee_bearer"] == "taxo" and ok.json()["integration"] == "sofizpay"
    manual = await client.post("/admin/payment-methods", json={
        "country_code": "DZ", "kind": "cash", "code": "office", "name": "كاش", "fee_bearer": "user"}, headers=admin_headers)
    assert manual.status_code == 422


async def test_the_contract_test_button_asks_chargily_for_its_balance(
    client: AsyncClient, session_factory, admin_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_transport(monkeypatch)
    from app.services import payment_gateways

    gateway = payment_gateways.build("chargily", {"secret_key": CHARGILY_SECRET, "test_mode": True})
    assert "يعمل" in await gateway.test_connection()
    sofizpay = payment_gateways.build("sofizpay", {"account": SOFIZPAY_ACCOUNT})
    assert "لم يُقَس" in await sofizpay.test_connection()


# ------------------------------------------------------------------ الوهميّ وحدودُه


async def test_the_mock_gateway_runs_the_whole_path_outside_production(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    from tests.helpers import _enable_provider

    await _enable_provider(session_factory, "chargily", {"secret_key": "x", "use_mock": True}, country="DZ")
    method_id = await add_gateway_method(session_factory, "chargily", contract=False)
    rider = await rider_session(client, ALGERIAN_RIDER)
    opened = (await open_checkout(client, rider["headers"], method_id)).json()
    external_id = opened["checkout_url"].rsplit("/", 1)[1]
    page = await client.get(f"/payment-requests/mock/{external_id}")
    assert page.status_code == 200 and "نجح الدفع" in page.text
    paid = await client.post(f"/payment-requests/mock/{external_id}/paid")
    assert paid.status_code == 303
    refreshed = await client.post(f"/payment-requests/{opened['request']['id']}/refresh", headers=rider["headers"])
    assert refreshed.json()["status"] == "approved"

    monkeypatch.setattr(settings, "environment", "production")
    assert (await client.get(f"/payment-requests/mock/{external_id}")).status_code == 404


async def test_jordan_sees_no_gateway(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    await algeria_market(session_factory)
    install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    jordanian = await rider_session(client, RIDER)
    refused = await open_checkout(client, jordanian["headers"], method_id)
    assert refused.status_code == 403
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentRequest)) == 0
