"""**اشتراكُ الكبتن الشهريُّ بالبطاقة في الأردن عبر Polar** (أمرُ المالك ٢٠٢٦-١١-١٤). **ما يُقاس هنا شروطُه بلفظها**:

- «verified webhook» — توقيعٌ مزوَّرٌ أو قديمٌ أو غائبٌ يُردّ ولا يحرّك شيئاً.
- «credit only on confirmed payment» — جلسةٌ مفتوحةٌ أو مؤكَّدةٌ قيدَ المعالجة لا تقيِّد؛ «paid» وحدَه يقيِّد.
- «idempotent, ledger» — المكرَّرُ قيدٌ واحدٌ في الدفتر القائم.
- «ship it OFF» — مطفأٌ مخفيّ، وللكباتن وحدَهم، والأردنُ وحدَه.
- «Don't use 100% discount codes» — لا رموزَ خصمٍ في الجلسة، **وطلبيّةٌ بخصمٍ أو بغير سعر المنتج لا تُعتمد**.
- والمبلغ: **سعرُ المنتج عند Polar بالدولار = سعرُ الخطّة بالدينار × الربط** سنتاً بسنت، وإلا لا يُفتح دفع.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة، بأشكال وثائق Polar المنشورة (`polar.sh/docs`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PaymentProviderKind
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_reasons, payment_requests
from app.services.payment_gateways import polar
from tests.helpers import RIDER, _enable_provider, approved_driver, enable_features, ensure_plan, rider_session

pytestmark = pytest.mark.asyncio

#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = "pat_" + secrets.token_hex(10)
HOOK_VALUE = "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()
PRODUCT = str(uuid.uuid4())
#: **60 ديناراً × 1.4104 = 84.624 ← 84.63 دولاراً** — كما ضُبط المنتجُ عند Polar
PLAN_PRICE = "60"
PRICE_CENTS = 8463


class PolarFake:
    """**Polar بلا شبكة** — منتجٌ بسعرٍ ثابت، وجلساتُ دفعٍ تُفتح، وحالُها وطلبيّاتُها مضبوطةٌ من الاختبار."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.status: dict[str, str] = {}
        self.orders: list[dict[str, Any]] = []
        self.price = PRICE_CENTS

    def pay(self, checkout: str, status: str = "paid", **extra: Any) -> None:
        self.status[checkout] = "succeeded"
        self.orders.append(
            {
                "id": f"ord_{len(self.orders) + 1}",
                "status": status,
                "paid": status == "paid",
                "checkout_id": checkout,
                "product_id": PRODUCT,
                "currency": "usd",
                "net_amount": PRICE_CENTS,
                "discount_amount": 0,
                "total_amount": PRICE_CENTS,
                "refunded_amount": 0,
                "billing_reason": "subscription_create",
            }
            | extra
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Bearer {API_VALUE}"
        assert request.url.host == "api.polar.sh"
        path = request.url.path
        if request.method == "GET" and path == f"/v1/products/{PRODUCT}":
            return httpx.Response(200, json={
                "id": PRODUCT, "is_archived": False, "is_recurring": True,
                "prices": [{"amount_type": "fixed", "price_amount": self.price, "price_currency": "usd", "is_archived": False}],
            })
        if request.method == "POST" and path == "/v1/checkouts/":
            body = json.loads(request.content)
            self.created.append(body)
            checkout = f"co_{len(self.created)}"
            self.status[checkout] = "open"
            return httpx.Response(201, json={"id": checkout, "url": f"https://buy.polar.sh/{checkout}", "status": "open"})
        if request.method == "GET" and path.startswith("/v1/checkouts/"):
            checkout = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"id": checkout, "status": self.status.get(checkout, "open")})
        if request.method == "GET" and path == "/v1/orders/":
            wanted = request.url.params.get("checkout_id")
            return httpx.Response(200, json={"items": [o for o in self.orders if o["checkout_id"] == wanted], "pagination": {}})
        return httpx.Response(404, json={"detail": f"unexpected {request.method} {path}"})


def _install(monkeypatch: pytest.MonkeyPatch) -> PolarFake:
    fake = PolarFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    return fake


async def _jordan_polar(session_factory, *, contract: bool = True, flag: bool = True) -> uuid.UUID:
    """**كما يضعها `0166`** — صفٌّ للاشتراك وحدَه، **والمفتاحُ مطفأٌ هناك** فيُشعل هنا بقدر الاختبار."""
    if contract:
        await _enable_provider(
            session_factory, "polar", {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "product_id": PRODUCT}, country="JO"
        )
    await enable_features(session_factory, "wallet_enabled")
    if flag:
        await enable_features(session_factory, "polar_card_enabled")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="polar_card",
            name="الدفع بالبطاقة المصرفية", integration="polar", enabled=True, for_topup=False, for_subscription=True,
            fee_bearer="taxo", sort_order=1, max_amount=Decimal("100.000"),
        )
        session.add(method)
        await session.commit()
        return method.id


def _hook(
    data: dict[str, Any], kind: str = "order.paid", *, secret: str = HOOK_VALUE, at: int | None = None
) -> tuple[bytes, dict[str, str]]:
    """**الإشعارُ كما يوقّعه Polar** (Standard Webhooks) — HMAC-SHA256 على «id.timestamp.body» بالسرّ كاملاً، base64 بعد `v1,`."""
    body = json.dumps({"type": kind, "timestamp": "2026-11-15T00:00:00Z", "data": data}).encode()
    stamp = str(at if at is not None else int(time.time()))
    msg_id = "msg_" + secrets.token_hex(4)
    sig = base64.b64encode(hmac.new(secret.encode(), f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    return body, {"webhook-id": msg_id, "webhook-timestamp": stamp, "webhook-signature": f"v1,{sig}", "content-type": "application/json"}


async def _deliver(client: AsyncClient, checkout: str, kind: str = "order.paid") -> dict:
    body, headers = _hook({"id": "ord_x", "checkout_id": checkout}, kind)
    response = await client.post("/payment-requests/webhook/polar", content=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _subscribe(client: AsyncClient, session_factory, headers: dict, method_id: uuid.UUID, price: str = PLAN_PRICE) -> httpx.Response:
    plan_id = await ensure_plan(session_factory, country="JO", name="TAXO X30 — شهري", price=price)
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "subscription", "amount": "1", "plan_id": str(plan_id)},
        headers=headers,
    )


async def _row(session_factory, request_id: str) -> PaymentRequest:
    async with session_factory() as session:
        return await session.get(PaymentRequest, uuid.UUID(request_id))


async def _entries(session_factory, request_id: str) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(WalletTransaction)
                .where(WalletTransaction.idempotency_key == f"payment_request:{request_id}")
            )
            or 0
        )


# ------------------------------------------------------------------ «paid» وحدَه يحرّك المال، ومكرَّرُه قيدٌ واحد


async def test_paid_activates_the_subscription_once_and_a_duplicate_webhook_changes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "polar_card")
    # **ما يُقال قبل الدفع صادق**: بالدولار بالربط، ومعالجُها Polar ورسمُه على TAXO — **ولا هويّةَ ولا أصلَ رقميّ**
    assert card["charge_currency"] == "USD"
    assert card["partner"] == "Polar" and card["partner_fee"] is None
    assert card["partner_kyc"] is False and card["settles_digital"] is False

    opened = await _subscribe(client, session_factory, captain["headers"], method_id)
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    assert opened.json()["checkout_url"] == "https://buy.polar.sh/co_1"
    # **ثمنُ الخطّة من الخادم** (المرسَلُ «1» يُتجاهل)
    assert opened.json()["request"]["amount"] == "60.000"
    sent = fake.created[0]
    # **منتجُنا وحدَه، ولا رموزَ خصم، ولا بيانات بطاقةٍ ولا اسمَ ولا هاتف** — مرجعُ طلبنا وحدَه
    assert sent["products"] == [PRODUCT] and sent["allow_discount_codes"] is False
    assert set(sent["metadata"]) == {"order_ref", "source"} and sent["metadata"]["order_ref"]

    # **مؤكَّدةٌ عند البنك ولم تكتمل** — لا شيء
    fake.status["co_1"] = "confirmed"
    assert (await _deliver(client, "co_1", "checkout.updated"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"

    fake.pay("co_1")
    assert (await _deliver(client, "co_1"))["applied"] == 1
    assert (await _deliver(client, "co_1"))["applied"] == 0
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert await _entries(session_factory, request_id) == 1
    assert row.gateway_message == "84.63 USD"


# ------------------------------------------------------------------ الإشعار: المزوَّرُ والقديمُ والغائبُ يُردّ


@pytest.mark.parametrize("forgery", ["wrong_secret", "stale", "no_signature"])
async def test_a_forged_or_stale_webhook_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    request_id = (await _subscribe(client, session_factory, captain["headers"], method_id)).json()["request"]["id"]
    fake.pay("co_1")

    data = {"id": "ord_1", "checkout_id": "co_1"}
    if forgery == "wrong_secret":
        body, headers = _hook(data, secret="whsec_" + secrets.token_hex(12))
    elif forgery == "stale":
        body, headers = _hook(data, at=int(time.time()) - polar.WEBHOOK_TOLERANCE_SECONDS - 60)
    else:
        body, headers = _hook(data)
        headers.pop("webhook-signature")
    refused = await client.post("/payment-requests/webhook/polar", content=body, headers=headers)
    assert refused.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ الخصمُ والسعرُ الآخرُ والمستردّ — بلا مال


@pytest.mark.parametrize(
    "change",
    [
        {"discount_amount": PRICE_CENTS, "net_amount": 0, "total_amount": 0},  # «100% discount»
        {"discount_amount": 1000, "net_amount": PRICE_CENTS - 1000},
        {"net_amount": PRICE_CENTS - 1},
        {"currency": "eur"},
        {"product_id": str(uuid.uuid4())},
    ],
    ids=["full_discount", "partial_discount", "short_by_a_cent", "other_currency", "other_product"],
)
async def test_an_order_off_the_product_price_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    request_id = (await _subscribe(client, session_factory, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("co_1", **change)
    assert (await _deliver(client, "co_1"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


@pytest.mark.parametrize("status", ["refunded", "partially_refunded"])
async def test_a_refunded_order_is_rejected_without_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    request_id = (await _subscribe(client, session_factory, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("co_1", status=status)
    await _deliver(client, "co_1", "order.refunded")
    row = await _row(session_factory, request_id)
    assert row.status.value == "rejected" and row.rejection_reason == payment_reasons.CARD_REFUNDED
    assert await _entries(session_factory, request_id) == 0


async def test_a_plan_price_that_differs_from_the_product_opens_no_payment(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**تبدّل سعرُ الخطّة في اللوحة ولم يُحدَّث المنتجُ عند Polar** — لا يُفتح دفعٌ بمبلغٍ غيرِ ما في الطلب."""
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    refused = await _subscribe(client, session_factory, captain["headers"], method_id, price="50")
    assert refused.status_code >= 400, refused.text
    assert fake.created == []


async def test_a_renewal_order_without_our_checkout_names_nothing() -> None:
    """**التجديدُ الشهريُّ الآليّ لا يُقيَّد آليّاً** (شرطٌ قبل الإشعال) — إشعارُه بلا جلسة دفعٍ عندنا لا يسمّي طلباً."""
    gateway = polar.build_polar({"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "product_id": PRODUCT})
    body, headers = _hook({"id": "ord_9", "checkout_id": None, "billing_reason": "subscription_cycle", "subscription_id": "sub_1"})
    assert gateway.webhook_ids(headers, body) == []


# ------------------------------------------------------------------ إشعارٌ فائت


async def test_a_missed_webhook_is_settled_once_by_the_fallback_check(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    request_id = (await _subscribe(client, session_factory, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("co_1")
    # **عودةُ التطبيق تسأل ولا تقيِّد** — والإشعارُ وحدَه أو المهلةُ بعده
    returned = await client.post(f"/payment-requests/{request_id}/refresh", headers=captain["headers"])
    assert returned.status_code == 200 and returned.json()["status"] == "pending"
    assert await _entries(session_factory, request_id) == 0

    later = datetime.now(UTC) + timedelta(seconds=payment_requests.WEBHOOK_GRACE_SECONDS + 120)
    for _ in range(3):
        async with session_factory() as session:
            await payment_requests.reconcile_gateway(session, now=later)
    assert (await _row(session_factory, request_id)).status.value == "approved"
    assert await _entries(session_factory, request_id) == 1
    assert (await _deliver(client, "co_1"))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ مطفأةٌ ومخفيّة — ومتى تُعرض ولمن


async def test_hidden_without_keys_or_switch_and_never_shown_to_riders(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_polar(session_factory, contract=False, flag=False)
    captain = await approved_driver(client, session_factory, subscribed=False)
    off = await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])
    assert "polar_card" not in [row["code"] for row in (off.json().get("methods") or [])] if off.status_code == 200 else True
    assert (await _subscribe(client, session_factory, captain["headers"], method_id)).status_code in (403, 409, 503)

    # **العقدُ وحدَه لا يكفي** — المفتاحُ مطفأٌ كما يُرفع
    await _enable_provider(
        session_factory, "polar", {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "product_id": PRODUCT}, country="JO"
    )
    still = await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])
    assert "polar_card" not in [row["code"] for row in (still.json().get("methods") or [])] if still.status_code == 200 else True
    assert fake.created == []

    await enable_features(session_factory, "polar_card_enabled")
    shown = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    assert "polar_card" in [row["code"] for row in shown["methods"]]
    # **ولا شحنَ محفظة** — الاشتراكُ وحدَه
    topup = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert "polar_card" not in [row["code"] for row in (topup.json().get("methods") or [])] if topup.status_code == 200 else True
    rider = await rider_session(client, RIDER)
    hidden = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert "polar_card" not in [row["code"] for row in (hidden.json().get("methods") or [])] if hidden.status_code == 200 else True


async def test_algeria_and_libya_are_locked_in_the_server(client: AsyncClient, admin_headers: dict) -> None:
    assert payment_gateways.switch_allowed("polar_card_enabled", CountryCode.JO)
    for country in (CountryCode.DZ, CountryCode.LY):
        assert not payment_gateways.switch_allowed("polar_card_enabled", country)
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": country, "feature_key": "polar_card_enabled", "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 422, refused.text


# ------------------------------------------------------------------ المحوِّلُ وحدَه


def test_the_product_price_is_the_plan_price_at_the_peg_rounded_up() -> None:
    assert polar.to_cents(polar.charge_amount(Decimal("60.000"), Decimal("1.4104"))) == PRICE_CENTS


def test_missing_contract_values_keep_the_method_hidden() -> None:
    for values in (
        {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE},
        {"api_key": API_VALUE, "product_id": PRODUCT, "webhook_secret": ""},
        {"webhook_secret": HOOK_VALUE, "product_id": PRODUCT},
    ):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            polar.build_polar(values)


def test_sandbox_uses_the_sandbox_api() -> None:
    live = polar.build_polar({"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "product_id": PRODUCT})
    assert live.base_url == polar.LIVE_BASE and live.test_mode is False
    sandbox = polar.build_polar({"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "product_id": PRODUCT, "sandbox": "true"})
    assert sandbox.base_url == polar.SANDBOX_BASE and sandbox.test_mode is True
