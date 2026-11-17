"""**Dpay — بوّابةُ الدفع الليبيّة** (أمرُ المالك ٢٠٢٦-١١-١٧). **ما يُقاس هنا شروطُه بلفظها**:

- «hosted page, no card data on our servers» — الصفحةُ صفحةُ Dpay، ولا يُرسل إليها إلا المبلغُ ومرجعُ طلبنا ووسيلةُ الصفّ.
- «verified webhook» — توقيعٌ مزوَّرٌ أو قديمٌ («late») أو غائبٌ يُردّ ولا يحرّك شيئاً.
- «credit only on a confirmed payment, idempotent» — «paid» وحدَه يقيِّد، والمكرَّرُ («repeated») قيدٌ واحدٌ في الدفتر القائم.
- «failed» — محاولةٌ فشلت والجلسةُ مفتوحةٌ لا تحرّك شيئاً؛ وجلسةٌ انتهت تُرفض بلا مال.
- «fallback status check» — إشعارٌ فات تحسمه التسويةُ الدوريّة مرّةً واحدة.
- «each with its own panel switch» — الشحنُ لا يُفتح بمفتاح الاشتراك ولا العكس؛ وكلُّها مطفأةٌ مخفيّة.
- الأردن: ثمنُ الخطّة بالأردنيّ × سعرُ العقد = الليبيُّ المطلوبُ من Dpay، مختوماً ومطابَقاً.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة، بأشكال توثيق Dpay المنشور (`dpay.ly/docs/api`).
"""

from __future__ import annotations

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
from app.models.feature_flag import FeatureFlag
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_requests
from app.services.payment_gateways import dpay
from tests.helpers import _enable_provider, approved_driver, enable_features, ensure_plan, register, auth

pytestmark = pytest.mark.asyncio

#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = "42|" + secrets.token_hex(12)
HOOK_VALUE = "whsec_" + secrets.token_hex(16)
LY_RIDER = {"phone": "0912345678", "name": "راكب طرابلس", "password": "SuperSecret123", "country_code": "LY", "role": "rider"}
#: **60 ديناراً أردنيّاً × 6.85 = 411.00 ديناراً ليبيّاً** — سعرٌ للاختبار لا للسوق
LYD_PER_JOD = "6.85"


class DpayFake:
    """**Dpay بلا شبكة** — جلساتٌ تُفتح، وحالُها ودفعتُها مضبوطةٌ من الاختبار."""

    def __init__(self, *, live: bool = True) -> None:
        self.created: list[dict[str, Any]] = []
        self.keys: list[str | None] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.live = live

    def pay(self, session_id: str, method: str | None = None, **extra: Any) -> None:
        row = self.sessions[session_id]
        row["status"] = "paid"
        amount = Decimal(row["amount"])
        row["payment"] = {
            "session_id": 22,
            "pay_method": method or (row.get("allowed_methods") or ["edfali"])[0],
            "tx_id": "txn_" + secrets.token_hex(6),
            "amount_charged": str(amount + Decimal("0.05")),
            "fee_amount": "0.050",
        }
        row.update(extra)

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Bearer {API_VALUE}"
        assert request.url.host == "dpay.ly"
        path = request.url.path
        if request.method == "POST" and path == "/api/v2/checkout-sessions":
            body = json.loads(request.content)
            self.created.append(body)
            self.keys.append(request.headers.get("idempotency-key"))
            session_id = f"cs_{len(self.created)}"
            self.sessions[session_id] = {
                "id": session_id, "url": f"https://dpay.ly/pay/{session_id}", "status": "open", "live": self.live,
                "amount": body["amount"], "currency": body.get("currency", "LYD"), "reference": body.get("reference"),
                "metadata": body.get("metadata") or {}, "allowed_methods": body.get("allowed_methods"),
                "payment": None, "attempts": [],
            }
            return httpx.Response(201, json={"data": self.sessions[session_id], "meta": {}})
        if request.method == "GET" and path.startswith("/api/v2/checkout-sessions/"):
            session_id = path.rsplit("/", 1)[1]
            if session_id not in self.sessions:
                return httpx.Response(404, json={"title": "Not Found", "status": 404})
            return httpx.Response(200, json={"data": self.sessions[session_id], "meta": {}})
        if request.method == "GET" and path == "/api/v2/checkout-sessions":
            return httpx.Response(200, json={"data": [], "meta": {}})
        return httpx.Response(404, json={"detail": f"unexpected {request.method} {path}"})


def _install(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> DpayFake:
    fake = DpayFake(**kwargs)
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    return fake


async def _flags(session_factory, country: str, *keys: str) -> None:
    async with session_factory() as session:
        for key in keys:
            session.add(FeatureFlag(country_code=CountryCode(country), feature_key=key, enabled=True))
        await session.commit()


async def _method(session_factory, country: str, code: str, *, topup: bool, subscription: bool) -> uuid.UUID:
    """**كما يضعها `0170`** — صفٌّ لكلِّ وسيلة؛ **والمفاتيحُ مطفأةٌ هناك** فتُشعل هنا بقدر الاختبار."""
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode(country), kind=PaymentProviderKind.BANK_TRANSFER, code=code,
            name=f"{code} (Dpay)", integration="dpay", enabled=True, for_topup=topup, for_subscription=subscription,
            fee_bearer="user", sort_order=20, max_amount=Decimal("100.000") if country == "JO" else None,
        )
        session.add(method)
        await session.commit()
        return method.id


async def _libya(session_factory, *, contract: bool = True, flags: tuple[str, ...] = ("dpay_topup_enabled",)) -> uuid.UUID:
    if contract:
        await _enable_provider(session_factory, "dpay", {"api_token": API_VALUE, "webhook_secret": HOOK_VALUE}, country="LY")
    await _flags(session_factory, "LY", "wallet_enabled", *flags)
    return await _method(session_factory, "LY", "dpay_edfali", topup=True, subscription=True)


def _hook(session_id: str, event: str = "checkout.completed", *, secret: str = HOOK_VALUE, at: int | None = None) -> tuple[bytes, dict]:
    """**الإشعارُ كما يوقّعه Dpay** — HMAC-SHA256 ستّ عشريٌّ على «timestamp.body» بالسرّ كاملاً."""
    body = json.dumps({"event": event, "live": True, "checkout_session_id": session_id, "status": "paid"}).encode()
    stamp = str(at if at is not None else int(time.time()))
    signature = hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return body, {"x-dpay-timestamp": stamp, "x-dpay-event": event, "x-dpay-signature": signature, "content-type": "application/json"}


async def _deliver(client: AsyncClient, session_id: str, event: str = "checkout.completed") -> dict:
    body, headers = _hook(session_id, event)
    response = await client.post("/payment-requests/webhook/dpay", content=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _topup(client: AsyncClient, headers: dict, method_id: uuid.UUID, amount: str = "20") -> httpx.Response:
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": amount},
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


async def _rider(client: AsyncClient) -> dict:
    return auth(await register(client, LY_RIDER))


# ------------------------------------------------------------------ «paid» وحدَه يحرّك المال، ومكرَّرُه قيدٌ واحد


async def test_paid_tops_up_once_and_a_repeated_webhook_changes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _libya(session_factory)
    headers = await _rider(client)

    listed = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=headers)).json()
    assert [row["code"] for row in listed["methods"]] == ["dpay_edfali"]

    opened = await _topup(client, headers, method_id)
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    assert opened.json()["checkout_url"] == "https://dpay.ly/pay/cs_1"
    sent = fake.created[0]
    # **الصفحةُ محصورةٌ بوسيلة الصفّ، بالليبيّ وبمنزلتين** — ولا هاتفَ ولا اسمَ ولا بطاقة: مرجعُ طلبنا والمبلغُ المختوم
    assert sent["allowed_methods"] == ["edfali"] and sent["currency"] == "LYD" and sent["amount"] == "20.00"
    assert "customer" not in sent and set(sent["metadata"]) == {"order_ref", "source", "charge_lyd", "method"}
    assert fake.keys[0] and fake.keys[0].startswith("taxo:")

    # **محاولةٌ فشلت والجلسةُ مفتوحة** — لا شيء
    assert (await _deliver(client, "cs_1", "payment.failed"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"

    fake.pay("cs_1")
    assert (await _deliver(client, "cs_1"))["applied"] == 1
    assert (await _deliver(client, "cs_1"))["applied"] == 0
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.amount == Decimal("20.000")
    assert await _entries(session_factory, request_id) == 1
    assert row.fee_payer == "user"


# ------------------------------------------------------------------ الإشعار: المزوَّرُ والمتأخّرُ والغائبُ يُردّ


@pytest.mark.parametrize("forgery", ["wrong_secret", "late", "no_signature"])
async def test_a_forged_or_late_webhook_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _libya(session_factory)
    headers = await _rider(client)
    request_id = (await _topup(client, headers, method_id)).json()["request"]["id"]
    fake.pay("cs_1")

    if forgery == "wrong_secret":
        body, hook = _hook("cs_1", secret="whsec_" + secrets.token_hex(12))
    elif forgery == "late":
        body, hook = _hook("cs_1", at=int(time.time()) - dpay.WEBHOOK_TOLERANCE_SECONDS - 60)
    else:
        body, hook = _hook("cs_1")
        hook.pop("x-dpay-signature")
    refused = await client.post("/payment-requests/webhook/dpay", content=body, headers=hook)
    assert refused.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ انتهت · لا تطابق · بيئةٌ أخرى — بلا مال


async def test_an_expired_session_is_rejected_without_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _libya(session_factory)
    headers = await _rider(client)
    request_id = (await _topup(client, headers, method_id)).json()["request"]["id"]
    fake.sessions["cs_1"]["status"] = "expired"
    await _deliver(client, "cs_1", "checkout.expired")
    assert (await _row(session_factory, request_id)).status.value == "rejected"
    assert await _entries(session_factory, request_id) == 0


@pytest.mark.parametrize(
    "change",
    [{"amount": "19.00"}, {"currency": "USD"}, {"live": False}, {"reference": "someone-else"}],
    ids=["other_amount", "other_currency", "sandbox_session_on_live_contract", "other_reference"],
)
async def test_a_paid_session_that_does_not_match_what_we_opened_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, change: dict
) -> None:
    fake = _install(monkeypatch)
    method_id = await _libya(session_factory)
    headers = await _rider(client)
    request_id = (await _topup(client, headers, method_id)).json()["request"]["id"]
    fake.pay("cs_1", **change)
    assert (await _deliver(client, "cs_1"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


async def test_a_third_decimal_opens_no_page() -> None:
    with pytest.raises(payment_gateways.GatewayError):
        dpay.two_places(Decimal("20.005"))
    assert dpay.two_places(Decimal("20.500")) == "20.50"


# ------------------------------------------------------------------ إشعارٌ فات


async def test_a_missed_webhook_is_settled_once_by_the_fallback_check(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _libya(session_factory)
    headers = await _rider(client)
    request_id = (await _topup(client, headers, method_id)).json()["request"]["id"]

    fake.pay("cs_1")
    # **المرورُ الأوّلُ يختم «دُفع» ولا يقيِّد** (ينتظر الإشعارَ الموقَّع مهلتَه)، **والذي بعد المهلة يقيِّد مرّةً** ولو تكرّر
    first = datetime.now(UTC)
    async with session_factory() as session:
        await payment_requests.reconcile_gateway(session, now=first)
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0
    later = first + timedelta(seconds=payment_requests.WEBHOOK_GRACE_SECONDS + 120)
    for _ in range(3):
        async with session_factory() as session:
            await payment_requests.reconcile_gateway(session, now=later)
    assert (await _row(session_factory, request_id)).status.value == "approved"
    assert await _entries(session_factory, request_id) == 1
    assert (await _deliver(client, "cs_1"))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ مطفأةٌ ومخفيّة — ومفتاحٌ لكلِّ استعمال


async def test_hidden_until_contract_and_its_own_switch(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    # **مفتاحُ الاشتراك وحدَه مشتعل** — فلا شحنَ محفظة
    method_id = await _libya(session_factory, contract=False, flags=("dpay_subscription_enabled",))
    headers = await _rider(client)
    off = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=headers)
    assert "dpay_edfali" not in [row["code"] for row in (off.json().get("methods") or [])] if off.status_code == 200 else True
    assert (await _topup(client, headers, method_id)).status_code in (403, 409, 503)

    await _enable_provider(session_factory, "dpay", {"api_token": API_VALUE, "webhook_secret": HOOK_VALUE}, country="LY")
    still = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=headers)
    assert "dpay_edfali" not in [row["code"] for row in (still.json().get("methods") or [])] if still.status_code == 200 else True
    assert (await _topup(client, headers, method_id)).status_code in (403, 409, 503)
    assert fake.created == []

    # **ومفتاحُ دفع الرحلة يفتح الشحنَ** (الرحلةُ تُدفع شحناً بقيمتها ثمّ من المحفظة)
    await _flags(session_factory, "LY", "dpay_trip_enabled")
    shown = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=headers)).json()
    assert "dpay_edfali" in [row["code"] for row in shown["methods"]]


async def test_switches_are_locked_to_their_countries(client: AsyncClient, admin_headers: dict) -> None:
    assert payment_gateways.switch_allowed("dpay_topup_enabled", CountryCode.LY)
    assert payment_gateways.switch_allowed("dpay_subscription_enabled", CountryCode.JO)
    for key, country in (
        ("dpay_topup_enabled", CountryCode.JO),
        ("dpay_trip_enabled", CountryCode.JO),
        ("dpay_subscription_enabled", CountryCode.DZ),
        ("dpay_topup_enabled", CountryCode.DZ),
    ):
        assert not payment_gateways.switch_allowed(key, country)
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": country, "feature_key": key, "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 422, refused.text


# ------------------------------------------------------------------ الأردن: الاشتراكُ بالبطاقة الدوليّة — بالليبيّ بسعر العقد


async def test_jordan_subscription_asks_dpay_in_libyan_dinars_at_the_contract_rate(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    await _enable_provider(
        session_factory, "dpay", {"api_token": API_VALUE, "webhook_secret": HOOK_VALUE, "lyd_per_jod": LYD_PER_JOD}, country="JO"
    )
    await enable_features(session_factory, "wallet_enabled", "dpay_subscription_enabled")
    method_id = await _method(session_factory, "JO", "dpay_mpgs_jo", topup=False, subscription=True)
    captain = await approved_driver(client, session_factory, subscribed=False)

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "dpay_mpgs_jo")
    assert card["charge_currency"] == "USD" and card["partner"] == "Dpay"

    plan_id = await ensure_plan(session_factory, country="JO", name="TAXO X30 — شهري", price="60")
    opened = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "subscription", "amount": "1", "plan_id": str(plan_id)},
        headers=captain["headers"],
    )
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    assert opened.json()["request"]["amount"] == "60.000"
    sent = fake.created[0]
    assert sent["amount"] == "411.00" and sent["allowed_methods"] == ["mpgs"] and sent["metadata"]["charge_lyd"] == "411.00"

    fake.pay("cs_1", method="mpgs")
    assert (await _deliver(client, "cs_1"))["applied"] == 1
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ المحوِّلُ وحدَه


def test_a_jordan_row_needs_the_rate_and_a_libyan_row_refuses_one() -> None:
    libya = dpay.build_dpay({"api_token": API_VALUE, "webhook_secret": HOOK_VALUE})
    jordan = dpay.build_dpay({"api_token": API_VALUE, "webhook_secret": HOOK_VALUE, "lyd_per_jod": LYD_PER_JOD})
    assert libya.for_method("dpay_sadad").method == "sadad"
    with pytest.raises(payment_gateways.GatewayUnavailable):
        libya.for_method("dpay_mpgs_jo")
    with pytest.raises(payment_gateways.GatewayUnavailable):
        jordan.for_method("dpay_sadad")
    with pytest.raises(payment_gateways.GatewayUnavailable):
        libya.for_method("dpay_unknown")
    assert jordan.for_method("dpay_mpgs_jo").method == "mpgs"


def test_missing_contract_values_keep_the_methods_hidden() -> None:
    for values in ({"api_token": API_VALUE}, {"webhook_secret": HOOK_VALUE}, {"api_token": API_VALUE, "webhook_secret": HOOK_VALUE,
                                                                               "lyd_per_jod": "zero"}):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            dpay.build_dpay(values)


def test_a_sandbox_token_is_test_mode_by_itself() -> None:
    assert dpay.build_dpay({"api_token": "sb_tk_" + secrets.token_hex(6), "webhook_secret": HOOK_VALUE}).test_mode is True
    assert dpay.build_dpay({"api_token": API_VALUE, "webhook_secret": HOOK_VALUE}).test_mode is False
    assert dpay.to_lyd(Decimal("60.000"), Decimal("6.851")) == Decimal("411.06")
