"""**وسيطان مزيّفان بلا شبكة** — `httpx.MockTransport` يجيب بأشكال الوثائق المنشورة حرفاً (SPEC §٧٣-هـ المرحلة ٣).

**المحوِّلُ الحقيقيُّ هو المُختبَر** (`ChargilyGateway` · `SofizPayGateway`) — المزيَّفُ هنا الشبكةُ وحدَها: ما يُرسَل يُقرأ ويُقاس، وما يعود
بأشكال `dev.chargily.com` و`docs.sofizpay.com`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

import httpx

from app.models.enums import CountryCode, PaymentProviderKind
from app.models.payment_request import PayMethod
from app.services import payment_gateways
from tests.helpers import _enable_provider

CHARGILY_SECRET = "test_sk_taxo_fake"
SOFIZPAY_ACCOUNT = "GTAXOFAKEACCOUNT0000000000000000000000000000000000000000"


class ChargilyFake:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}
        self.amount: dict[str, int] = {}
        self.created: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {CHARGILY_SECRET}"
        path = request.url.path
        if request.method == "POST" and path.endswith("/checkouts"):
            body = json.loads(request.content)
            checkout_id = f"chk_{len(self.created) + 1:04d}"
            self.created.append(body)
            self.status[checkout_id] = "pending"
            self.amount[checkout_id] = body["amount"]
            return httpx.Response(200, json={
                "id": checkout_id, "entity": "checkout", "amount": body["amount"], "currency": "dzd", "status": "pending",
                "checkout_url": f"https://pay.chargily.dz/test/checkouts/{checkout_id}/pay",
            })
        if request.method == "GET" and "/checkouts/" in path:
            checkout_id = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={
                "id": checkout_id, "entity": "checkout", "status": self.status.get(checkout_id, "pending"),
                "amount": self.amount.get(checkout_id), "currency": "dzd",
            })
        if request.method == "GET" and path.endswith("/balance"):
            return httpx.Response(200, json={"entity": "balance", "livemode": False, "wallets": []})
        return httpx.Response(404, json={"message": "not found"})

    @staticmethod
    def signed(checkout_id: str, event: str = "checkout.paid", *, key: str = CHARGILY_SECRET) -> tuple[bytes, dict[str, str]]:
        """**إشعارٌ موقَّعٌ كما تقول الوثائق**: `HMAC-SHA256` للجسم الخام بالمفتاح السرّيّ في ترويسة `signature`."""
        body = json.dumps({"id": "evt_1", "entity": "event", "type": event, "data": {"id": checkout_id, "status": "paid"}}).encode()
        return body, {"signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest(), "content-type": "application/json"}


class SofizPayFake:
    def __init__(self) -> None:
        self.check: dict[str, dict[str, Any]] = {}
        self.created: list[dict[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/make-cib-transaction/"):
            params = dict(request.url.params)
            self.created.append(params)
            cib_id = f"25170{len(self.created):05d}"
            self.check[cib_id] = {"order_number": cib_id, "orderStatus": 0, "respCode": "", "destination_account": params["account"],
                                  "Amount": f"{params['amount']}.00"}
            return httpx.Response(200, json={
                "success": True, "transaction_id": str(uuid.uuid4()), "cib_transaction_id": cib_id,
                "payment_url": f"https://cib.satim.dz/payment/{cib_id}", "amount": params["amount"],
                "status": "pending_user_transfer_start",
            })
        if path.endswith("/cib-transaction-check/"):
            order = request.url.params["order_number"]
            return httpx.Response(200, json=self.check.get(order, {"order_number": order, "orderStatus": 0}))
        return httpx.Response(404, json={"status": "error", "message": "Invalid or missing parameters."})


class Router:
    """**نقلٌ واحدٌ للوسيطين** — يوجّه بالمضيف."""

    def __init__(self, chargily: ChargilyFake, sofizpay: SofizPayFake) -> None:
        self.chargily, self.sofizpay = chargily, sofizpay

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "pay.chargily.net":
            return self.chargily.handler(request)
        if request.url.host == "sofizpay.com":
            return self.sofizpay.handler(request)
        return httpx.Response(599)


def install_transport(monkeypatch) -> tuple[ChargilyFake, SofizPayFake]:
    chargily, sofizpay = ChargilyFake(), SofizPayFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(Router(chargily, sofizpay)))
    return chargily, sofizpay


async def add_gateway_method(session_factory, integration: str, *, fee_bearer: str = "taxo", contract: bool = True) -> uuid.UUID:
    """**عقدُ الوسيط في صفحة العقود** (بالخدمة نفسِها) **وطريقتُه مفعَّلةً في نظام الدفع**."""
    if contract and integration == "chargily":
        await _enable_provider(session_factory, "chargily", {"secret_key": CHARGILY_SECRET, "test_mode": True}, country="DZ")
    if contract and integration == "sofizpay":
        await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_ACCOUNT, "sandbox": True}, country="DZ")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.DZ, kind=PaymentProviderKind.BANK_TRANSFER, code=integration,
            name={"chargily": "الذهبية وCIB", "sofizpay": "CIB عبر SofizPay"}[integration],
            integration=integration, enabled=True, fee_bearer=fee_bearer, sort_order=3,
        )
        session.add(method)
        await session.commit()
        return method.id
