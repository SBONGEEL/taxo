"""**الدفعُ بالعملات الرقميّة عبر MoonPay Commerce في الأردن** (أمرُ المالك ٢٠٢٦-١١-١٤). **ما يُقاس هنا شروطُه بلفظها**:

- «verified webhook; credit only on a confirmed payment; idempotent, with a fallback status check» — توقيعٌ مزوَّرٌ يُردّ، و«SUCCESS» وحدَه
  يحرّك المال، والمكرَّرُ قيدٌ واحد، والفائتُ تحسمه التسويةُ الدوريّة.
- «PENDING/APPROVED and the existing ledger; tests for every state» — INITIATED/PENDING معلَّق، FAILED/CANCELED مرفوضٌ بلا مال،
  SUCCESS/SETTLED قيدٌ واحد.
- «driver subscription and dues; rider fixed-value credit packages» — ثمنُ الخطّة من الخادم، والمستحقّاتُ تُسدَّد، والراكبُ بباقةٍ وحدَها.
- «Algeria and Libya locked off» · «turn the switch OFF immediately» عند توقيعٍ لا يطابق أو مبلغٍ مختلف أو إخفاقاتٍ متتالية.
- «No card data on our servers» — لا يُرسل إلى MoonPay إلا السعرُ بالدولار ومرجعُ طلبنا.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة، بأشكال وثائق MoonPay Commerce المنشورة وما قِيس بمفاتيح المالك.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    Currency,
    DriverDebtSource,
    DriverDebtStatus,
    PaymentProviderKind,
)
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_reasons, payment_requests, settings_service
from app.services.payment_gateways import moonpay
from tests.helpers import (
    RIDER,
    _enable_provider,
    approved_driver,
    enable_features,
    ensure_plan,
    rider_session,
)


#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = "pk" + secrets.token_hex(10)
SECRET_VALUE = "sk" + secrets.token_hex(16)
HOOK_VALUE = "wh" + secrets.token_hex(16)
PAYLINK = secrets.token_hex(12)


def _contract(**extra: str) -> dict[str, str]:
    return {"api_key": API_VALUE, "secret_key": SECRET_VALUE, "webhook_secret": HOOK_VALUE, "paylink_id": PAYLINK,
            "rider_packages": "5,10,20"} | extra


class MoonpayFake:
    """**MoonPay Commerce بلا شبكة** — `POST /v1/charge/api-key` يعيد صفحةً برمزٍ، و`GET /v1/charge/api-key/{token}` حالَها المضبوطة."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.charges: dict[str, dict[str, Any]] = {}

    def token(self, n: int = 1) -> str:
        return f"0000000{n}-aaaa-bbbb-cccc-000000000000"

    def pay(self, token: str, status: str = "SUCCESS", *, paid: str | None = None) -> None:
        """**دفعٌ بحاله** — والمبلغُ المدفوعُ بأصغر وحدات USDC؛ افتراضاً ما طُلب بالضبط."""
        charge = self.charges[token]
        charge["paylinkTx"] = {
            "id": "tx_" + token[:8],
            "meta": {
                "transactionStatus": status,
                "totalAmount": paid if paid is not None else charge["requestAmount"],
                "currency": {"symbol": "USDC", "decimals": 6},
            },
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Bearer {SECRET_VALUE}"
        assert request.url.params.get("apiKey") == API_VALUE
        path = request.url.path
        if request.method == "POST" and path == "/v1/charge/api-key":
            body = json.loads(request.content)
            self.created.append(body)
            token = self.token(len(self.created))
            units = str(int(Decimal(body["requestAmount"]) * 1_000_000))
            self.charges[token] = {"id": f"c{len(self.created)}", "requestAmount": units, "currencySymbol": "USD", "paylinkTx": None}
            return httpx.Response(201, json={"id": f"c{len(self.created)}", "pageUrl": f"https://app.hel.io/charge/{token}"})
        if request.method == "GET" and path.startswith("/v1/charge/api-key/"):
            token = path.rsplit("/", 1)[-1]
            if token not in self.charges:
                return httpx.Response(404, json={"message": "not found", "code": 404})
            return httpx.Response(200, json=self.charges[token])
        if request.method == "GET" and path == "/v1/wallet/all":
            return httpx.Response(200, json=[{"id": "w1", "type": "TURNKEY"}])
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})


def _install(monkeypatch: pytest.MonkeyPatch) -> MoonpayFake:
    fake = MoonpayFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    return fake


async def _jordan(session_factory, *, contract: bool = True, flags: tuple[str, ...] = ("moonpay_driver_enabled", "moonpay_rider_enabled"),
                  **extra: str) -> tuple[uuid.UUID, uuid.UUID]:
    """**كما يضعها `0165`** — صفّا الطريقة، **والمفتاحان مطفآن هناك** فيُشعلان هنا بقدر الاختبار؛ والعقدُ بالخدمة نفسِها."""
    if contract:
        await _enable_provider(session_factory, "moonpay", _contract(**extra), country="JO")
    await enable_features(session_factory, "wallet_enabled", *flags)
    async with session_factory() as session:
        driver_row = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="moonpay_driver",
            name="الدفع بالعملات الرقمية", integration="moonpay", enabled=True, for_topup=True, for_subscription=True,
            fee_bearer="taxo", sort_order=0, max_amount=Decimal("100.000"),
        )
        rider_row = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="moonpay_rider",
            name="شحن المحفظة بالعملات الرقمية", integration="moonpay", enabled=True, for_topup=True,
            for_subscription=False, fee_bearer="taxo", sort_order=0,
        )
        session.add_all([driver_row, rider_row])
        await session.commit()
        return driver_row.id, rider_row.id


def _hook(token: str, *, secret: str = HOOK_VALUE) -> tuple[bytes, dict[str, str]]:
    """**الإشعارُ كما يوقّعه MoonPay Commerce** — HMAC-SHA256 بالست عشريّ على الجسم الخامّ بـ`sharedToken`."""
    payload = {"event": "CREATED", "chargeToken": token, "transactionObject": {"id": "tx1", "meta": {"transactionStatus": "SUCCESS"}}}
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"x-signature": sig, "content-type": "application/json"}


async def _deliver(client: AsyncClient, token: str) -> dict:
    body, headers = _hook(token)
    response = await client.post("/payment-requests/webhook/moonpay", content=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _open(client: AsyncClient, headers: dict, method_id: uuid.UUID, **body: Any) -> httpx.Response:
    return await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "wallet_topup", "amount": "10"} | body,
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


async def _switches(session_factory) -> tuple[bool, bool]:
    async with session_factory() as session:
        return (
            await settings_service.is_feature_enabled(session, CountryCode.JO, "moonpay_driver_enabled"),
            await settings_service.is_feature_enabled(session, CountryCode.JO, "moonpay_rider_enabled"),
        )


# ------------------------------------------------------------------ الكبتن: «SUCCESS» وحدَه يحرّك المال، ومكرَّرُه قيدٌ واحد


@pytest.mark.asyncio
async def test_success_activates_the_subscription_once_and_a_duplicate_webhook_changes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _rider_row = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory, country="JO", name="خطةُ MoonPay", price="10")

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    method = next(row for row in listed["methods"] if row["code"] == "moonpay_driver")
    # **ما يُقال قبل الدفع صادق**: عملاتٌ رقميّةٌ لا بطاقة — فلا حقلَ بطاقة؛ والسعرُ بالدولار بربط الدينار، ورسمُ المعالج على TAXO
    assert method["crypto"] is True and method["charge_currency"] is None and method["charge_rate"] is None
    assert method["crypto_rate"] == "1.4104" and method["packages"] == []
    assert method["partner"] == "MoonPay Commerce" and method["fee_payer"] == "taxo"

    opened = await _open(client, captain["headers"], driver_row, purpose="subscription", amount="1", plan_id=str(plan_id))
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    token = fake.token(1)
    assert opened.json()["checkout_url"] == f"https://app.hel.io/charge/{token}"
    # **ثمنُ الخطّة من الخادم** (المرسَلُ «1» يُتجاهل) — ١٠ دنانير = ١٤٫١١ دولاراً (١٤٫١٠٤ مقرَّبةً للأعلى)
    assert opened.json()["request"]["amount"] == "10.000"
    created = fake.created[0]
    assert created["paymentRequestId"] == PAYLINK and created["requestAmount"] == "14.11"
    assert created["successRedirectUrl"].endswith(f"r={request_id}")
    # **لا بيانات دفعٍ ولا اسمَ ولا هاتف** — مرجعُ طلبنا وحدَه
    extra = json.loads(created["prepareRequestBody"]["customerDetails"]["additionalJSON"])
    assert set(extra) == {"order_ref", "source"} and extra["order_ref"]

    # **ما دام لم يُؤكَّد على السلسلة** — INITIATED وPENDING لا يحرّكان شيئاً
    for waiting in ("INITIATED", "PENDING"):
        fake.pay(token, waiting)
        assert (await _deliver(client, token))["applied"] == 0
        assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0

    fake.pay(token, "SUCCESS")
    assert (await _deliver(client, token))["applied"] == 1
    assert (await _deliver(client, token))["applied"] == 0
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert await _entries(session_factory, request_id) == 1
    assert row.gateway_message == "14.11 USDC"
    assert await _switches(session_factory) == (True, True)


@pytest.mark.asyncio
async def test_settled_counts_as_paid(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    fake.pay(fake.token(1), "SETTLED")
    assert (await _deliver(client, fake.token(1)))["applied"] == 1
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ الإشعار: المزوَّرُ يُردّ ويُطفئ


@pytest.mark.asyncio
async def test_a_forged_webhook_is_refused_moves_nothing_and_switches_the_method_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    fake.pay(fake.token(1))

    # **بلا ترويسة التوقيع** — يُردّ، **ولا يُطفئ شيئاً** (طرقُ بابٍ لا إشعارٌ مزوَّر)
    body, headers = _hook(fake.token(1))
    headers.pop("x-signature")
    assert (await client.post("/payment-requests/webhook/moonpay", content=body, headers=headers)).status_code == 401
    assert await _switches(session_factory) == (True, True)

    body, headers = _hook(fake.token(1), secret="wh-" + secrets.token_hex(8))
    refused = await client.post("/payment-requests/webhook/moonpay", content=body, headers=headers)
    assert refused.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0
    # **«a webhook fails verification ⇐ turn the switch OFF»**
    assert await _switches(session_factory) == (False, False)
    gone = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert gone.status_code == 403 or all(row["code"] != "moonpay_driver" for row in gone.json()["methods"])


# ------------------------------------------------------------------ الفاشلُ والملغى والمنتهي — بلا مال


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["FAILED", "CANCELED"])
async def test_a_failed_or_cancelled_payment_is_rejected_without_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    fake.pay(fake.token(1), status)
    await _deliver(client, fake.token(1))
    row = await _row(session_factory, request_id)
    assert row.status.value == "rejected" and row.rejection_reason == payment_reasons.GATEWAY_FAILED
    assert await _entries(session_factory, request_id) == 0
    # **إخفاقٌ واحدٌ لا يُطفئ** — الثلاثةُ المتتاليةُ تُطفئ (أدناه)
    assert await _switches(session_factory) == (True, True)


@pytest.mark.asyncio
async def test_three_failures_in_a_row_switch_the_method_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    for n in (1, 2, 3):
        assert (await _open(client, captain["headers"], driver_row)).status_code == 201
        fake.pay(fake.token(n), "FAILED")
        await _deliver(client, fake.token(n))
        assert await _switches(session_factory) == ((True, True) if n < 3 else (False, False))


@pytest.mark.asyncio
async def test_an_unpaid_page_is_cancelled_by_the_sweep_without_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    async with session_factory() as session:
        await payment_requests.expire_stale(session, now=datetime.now(UTC) + timedelta(days=1))
    row = await _row(session_factory, request_id)
    assert row.status.value == "cancelled" and row.cancel_reason == payment_requests.EXPIRED_REASON
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ مبلغٌ لا يطابق: لا قيد، ويُطفئ


@pytest.mark.asyncio
async def test_an_underpayment_is_not_credited_and_switches_the_method_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    # ١٠ دنانير = ١٤٫١١ دولاراً؛ وصل ٧ وحدَها
    fake.pay(fake.token(1), paid="7000000")
    await _deliver(client, fake.token(1))
    row = await _row(session_factory, request_id)
    assert row.status.value == "pending" and row.outcome_note
    assert await _entries(session_factory, request_id) == 0
    assert await _switches(session_factory) == (False, False)


@pytest.mark.asyncio
async def test_an_overpayment_is_credited_at_the_requested_amount(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**وصل أكثرُ ممّا طُلب** (رسمُ شبكةٍ دفعه زائداً) — يُقيَّد المطلوبُ بالدينار، ولا يُطفأ شيء."""
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    fake.pay(fake.token(1), paid="14200000")
    assert (await _deliver(client, fake.token(1)))["applied"] == 1
    assert (await _row(session_factory, request_id)).status.value == "approved"
    assert await _switches(session_factory) == (True, True)


# ------------------------------------------------------------------ إشعارٌ فائت


@pytest.mark.asyncio
async def test_a_missed_webhook_is_settled_once_by_the_fallback_check(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], driver_row)).json()["request"]["id"]
    fake.pay(fake.token(1))
    # **عودةُ التطبيق تسأل ولا تقيِّد** — والإشعارُ وحدَه أو المهلةُ بعده
    returned = await client.post(f"/payment-requests/{request_id}/refresh", headers=captain["headers"])
    assert returned.status_code == 200 and returned.json()["status"] == "pending"
    later = datetime.now(UTC) + timedelta(seconds=payment_requests.WEBHOOK_GRACE_SECONDS + 120)
    for _ in range(3):
        async with session_factory() as session:
            await payment_requests.reconcile_gateway(session, now=later)
    assert (await _row(session_factory, request_id)).status.value == "approved"
    assert await _entries(session_factory, request_id) == 1
    assert (await _deliver(client, fake.token(1)))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ المستحقّات


@pytest.mark.asyncio
async def test_paying_dues_clears_them_and_lifts_the_block(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory)
    async with session_factory() as session:
        session.add(DriverDebt(
            driver_id=captain["driver_id"], country_code=CountryCode.JO, source=DriverDebtSource.RIDE_COMMISSION,
            amount=Decimal("6.500"), collected=Decimal("0"), currency=Currency.JOD, status=DriverDebtStatus.OUTSTANDING,
        ))
        driver = await session.get(Driver, captain["driver_id"])
        driver.debt_blocked = True
        await session.commit()
    request_id = (await _open(client, captain["headers"], driver_row, amount="6.500")).json()["request"]["id"]
    fake.pay(fake.token(1))
    assert (await _deliver(client, fake.token(1)))["applied"] == 1
    async with session_factory() as session:
        debt = await session.scalar(select(DriverDebt).where(DriverDebt.driver_id == captain["driver_id"]))
        driver = await session.get(Driver, captain["driver_id"])
        assert debt.status is DriverDebtStatus.SETTLED and driver.debt_blocked is False
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ الراكب: باقاتٌ ثابتة، ولكلٍّ صفُّه


@pytest.mark.asyncio
async def test_a_rider_buys_a_fixed_package_and_each_audience_keeps_its_own_row(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row, rider_row = await _jordan(session_factory)
    rider = await rider_session(client, RIDER)
    captain = await approved_driver(client, session_factory)

    seen = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])).json()
    assert [row["code"] for row in seen["methods"]] == ["moonpay_rider"]
    assert seen["methods"][0]["packages"] == ["5.000", "10.000", "20.000"]
    seen = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    assert [row["code"] for row in seen["methods"]] == ["moonpay_driver"]
    # **لا يعبر أحدٌ إلى صفِّ غيره** ولو أرسل معرّفَه بيده
    assert (await _open(client, rider["headers"], driver_row)).status_code == 422
    assert (await _open(client, captain["headers"], rider_row)).status_code == 422
    # **الباقةُ وحدَها** — مبلغٌ خارجها يُردّ قبل أن تُفتح صفحة
    off_menu = await _open(client, rider["headers"], rider_row, amount="7")
    assert off_menu.status_code == 422 and fake.created == []

    opened = await _open(client, rider["headers"], rider_row, amount="20")
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    assert fake.created[0]["requestAmount"] == "28.21"
    fake.pay(fake.token(1))
    assert (await _deliver(client, fake.token(1)))["applied"] == 1
    assert (await _deliver(client, fake.token(1)))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1
    assert (await _row(session_factory, request_id)).status.value == "approved"


@pytest.mark.asyncio
async def test_each_switch_governs_its_own_audience(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    _driver_row, rider_row = await _jordan(session_factory, flags=("moonpay_driver_enabled",))
    rider = await rider_session(client, RIDER)
    off = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert off.status_code == 403 or off.json()["methods"] == []
    assert (await _open(client, rider["headers"], rider_row, amount="5")).status_code == 403


# ------------------------------------------------------------------ مخفيّةٌ بلا عقد، ومقفلةٌ خارج الأردن


@pytest.mark.asyncio
async def test_hidden_without_keys(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)
    driver_row, _ = await _jordan(session_factory, contract=False)
    captain = await approved_driver(client, session_factory)
    listed = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert listed.status_code == 403, listed.text
    assert (await _open(client, captain["headers"], driver_row)).status_code in (409, 503)


@pytest.mark.asyncio
async def test_algeria_and_libya_are_locked_in_the_server(client: AsyncClient, admin_headers: dict) -> None:
    for key in ("moonpay_driver_enabled", "moonpay_rider_enabled"):
        assert payment_gateways.switch_allowed(key, CountryCode.JO)
        for country in (CountryCode.DZ, CountryCode.LY):
            assert not payment_gateways.switch_allowed(key, country)
            refused = await client.put(
                "/admin/settings/feature-flags",
                json={"country_code": country, "feature_key": key, "enabled": True},
                headers=admin_headers,
            )
            assert refused.status_code == 422, refused.text
    # **ولا تعبث بمفاتيح Whop** — مالكُ كلِّ مفتاحٍ وسيطُه
    assert payment_gateways.SWITCH_OWNER["whop_rider_topup_enabled"] == "whop"
    assert payment_gateways.SWITCH_OWNER["moonpay_rider_enabled"] == "moonpay"


# ------------------------------------------------------------------ وحدات: التوقيعُ والمبلغ


def test_the_signature_is_hex_hmac_over_the_raw_body() -> None:
    gateway = moonpay.build_moonpay(_contract())
    body, headers = _hook("12345678-aaaa-bbbb-cccc-000000000000")
    assert gateway.webhook_ids(headers, body) == ["12345678-aaaa-bbbb-cccc-000000000000"]
    with pytest.raises(payment_gateways.WebhookSignatureInvalid):
        gateway.webhook_ids(headers, body + b" ")
    unrelated = json.dumps({"event": "PAYLINK_DEPOSIT_UNDERPAID"}).encode()
    signed = {"x-signature": hmac.new(HOOK_VALUE.encode(), unrelated, hashlib.sha256).hexdigest()}
    assert gateway.webhook_ids(signed, unrelated) == []


def test_the_charge_is_the_jordanian_peg_rounded_up_to_the_cent() -> None:
    assert moonpay.charge_amount(Decimal("10.000"), Decimal("1.4104")) == Decimal("14.11")
    assert moonpay.charge_amount(Decimal("6.500"), Decimal("1.4104")) == Decimal("9.17")
    assert moonpay.charge_amount(Decimal("0.700"), Decimal("1.4104")) == Decimal("0.99")


def test_missing_keys_keep_it_hidden() -> None:
    for missing in ("api_key", "secret_key", "webhook_secret", "paylink_id"):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            moonpay.build_moonpay(_contract(**{missing: ""}))


def test_jordan_orders_crypto_first_in_the_migration() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "alembic/versions/0165_moonpay_commerce.py").read_text(encoding="utf-8")
    assert "'[\\\"crypto\\\"]'::jsonb || payment_method_order" in text and "country_code = 'JO'" in text


# ------------------------------------------------------------------ الترتيب: «crypto» أوّلاً ولا يتغيّر ما تقرؤه النسخُ المثبَّتة


@pytest.mark.asyncio
async def test_crypto_first_is_its_own_field_so_installed_apps_keep_card_first(client: AsyncClient, admin_headers: dict) -> None:
    saved = await client.patch(
        "/admin/settings/payments/JO",
        json={"payment_method_order": ["crypto", "card", "wallet", "cliq", "cash"]},
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["payment_method_order"] == ["crypto", "card", "wallet", "cliq", "cash"]
    published = {c["country_code"]: c for c in (await client.get("/config")).json()["countries"]}
    # **ما تقرؤه النسخُ المثبَّتة هو هو** — «card» أوّلُه فترسم البطاقةَ أوّلاً كما كانت
    assert published["JO"]["payment_method_order"] == ["card", "wallet", "cliq", "cash"]
    assert published["JO"]["crypto_first"] is True
    moved = await client.patch(
        "/admin/settings/payments/JO", json={"payment_method_order": ["card", "crypto", "wallet"]}, headers=admin_headers
    )
    assert moved.status_code == 200, moved.text
    published = {c["country_code"]: c for c in (await client.get("/config")).json()["countries"]}
    assert published["JO"]["payment_method_order"] == ["card", "wallet"] and published["JO"]["crypto_first"] is False
    for other in ("DZ", "LY"):
        if other in published:
            assert published[other]["crypto_first"] is False
