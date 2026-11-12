"""**الدفعُ بالبطاقة المصرفية للكبتن في الأردن عبر Whop** (أمرُ المالك ٢٠٢٦-١١-١٣). **ما يُقاس هنا شروطُه بلفظها**:

- «verified webhook, credit only on a confirmed payment, idempotent, fallback status check» — توقيعٌ مزوَّرٌ أو قديمٌ يُردّ، و«paid» وحدَه
  يحرّك المال، والمكرَّرُ قيدٌ واحد، والفائتُ تحسمه التسويةُ الدوريّة.
- «PENDING/APPROVED states and the existing ledger» — الطلبُ معلّقٌ حتى يُعتمد، والاعتمادُ قيدٌ واحدٌ في الدفتر القائم.
- «the method OFF and hidden from all drivers» — بلا مفاتيحَ مخفيّة، ومفتاحُها مطفأٌ مخفيّة، وللكباتن وحدَهم، والأردنُ وحدَه.
- «No card data on our servers» — لا يُرسل إلى Whop إلا السعرُ ومرجعُ طلبنا.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة، بأشكال وثائق Whop المنشورة (`docs.whop.com`).
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
from app.services import payment_gateways, payment_reasons, payment_requests
from app.services.payment_gateways import whop
from tests.helpers import (
    RIDER,
    _enable_provider,
    approved_driver,
    enable_features,
    ensure_plan,
    request_ride,
    rider_session,
    wallet_of,
)

pytestmark = pytest.mark.asyncio

#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = "apik_" + secrets.token_hex(10)
HOOK_VALUE = "ws_" + secrets.token_hex(16)
COMPANY = "biz_" + secrets.token_hex(7)


class WhopFake:
    """**Whop بلا شبكة** — `POST /checkout_configurations` يعيد `ch_…` ورابطاً نسبيّاً، و`GET /payments` يعيد الدفعاتِ المضبوطة."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.payments: list[dict[str, Any]] = []

    def pay(self, config: str, status: str = "paid", substatus: str = "succeeded", **extra: Any) -> None:
        self.payments.append(
            {
                "id": f"pay_{len(self.payments) + 1}",
                "status": status,
                "substatus": substatus,
                "checkout_configuration_id": config,
                "account_id": COMPANY,
                "currency": "jod",
                "total": {"amount": "10.000", "currency": "jod"},
            }
            | extra
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Bearer {API_VALUE}"
        path = request.url.path
        if request.method == "POST" and path.endswith("/checkout_configurations"):
            body = json.loads(request.content)
            self.created.append(body)
            config = f"ch_{len(self.created)}"
            return httpx.Response(200, json={"id": config, "purchase_url": f"/checkout/{config}/", "mode": "payment"})
        if request.method == "GET" and path.endswith("/payments"):
            assert request.url.params.get("account_id") == COMPANY
            first = int(request.url.params.get("first") or 10)
            return httpx.Response(
                200, json={"data": self.payments[:first], "page_info": {"has_next_page": False, "end_cursor": None}}
            )
        return httpx.Response(404, json={"error": {"message": f"unexpected {request.method} {path}"}})


def _install(monkeypatch: pytest.MonkeyPatch) -> WhopFake:
    fake = WhopFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    return fake


async def _jordan_whop(session_factory, *, contract: bool = True, flag: bool = True) -> uuid.UUID:
    """**كما يضعها `0160`** — صفُّ الطريقة، **والمفتاحُ مطفأٌ هناك** فيُشعل هنا بقدر الاختبار؛ والعقدُ بقيم المالك (بالخدمة نفسِها)."""
    if contract:
        await _enable_provider(
            session_factory, "whop", {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": COMPANY}, country="JO"
        )
    await enable_features(session_factory, "wallet_enabled")
    if flag:
        await enable_features(session_factory, "whop_card_enabled")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="whop_card",
            name="الدفع بالبطاقة المصرفية", integration="whop", enabled=True, for_topup=True, for_subscription=True,
            fee_bearer="taxo", sort_order=0, max_amount=Decimal("100.000"),
        )
        session.add(method)
        await session.commit()
        return method.id


def _hook(config: str, kind: str = "payment.succeeded", *, secret: str = HOOK_VALUE, at: int | None = None) -> tuple[bytes, dict[str, str]]:
    """**الإشعارُ كما يوقّعه Whop** (Standard Webhooks) — HMAC-SHA256 على «id.timestamp.body» بالسرّ كما أُعطي، base64 بعد `v1,`."""
    payload = {"id": "msg_1", "type": kind, "api_version": "v1", "data": {"id": "pay_1", "checkout_configuration_id": config}}
    body = json.dumps(payload).encode()
    stamp = str(at if at is not None else int(time.time()))
    msg_id = "msg_" + secrets.token_hex(4)
    sig = base64.b64encode(hmac.new(secret.encode(), f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    return body, {"webhook-id": msg_id, "webhook-timestamp": stamp, "webhook-signature": f"v1,{sig}", "content-type": "application/json"}


async def _deliver(client: AsyncClient, config: str, kind: str = "payment.succeeded") -> dict:
    body, headers = _hook(config, kind)
    response = await client.post("/payment-requests/webhook/whop", content=body, headers=headers)
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


# ------------------------------------------------------------------ «paid» وحدَه يحرّك المال، ومكرَّرُه قيدٌ واحد


async def test_paid_activates_the_subscription_once_and_a_duplicate_webhook_changes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory, country="JO", name="خطةُ بطاقة Whop", price="10")

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "whop_card")
    # **ما يُقال قبل الدفع صادق**: بالدينار بلا صرف، ومعالجُها Whop ورسمُه على TAXO — **ولا هويّةَ ولا أصلَ رقميّ**
    assert card["charge_currency"] == "JOD" and card["charge_rate"] is None
    assert card["partner"] == "Whop" and card["partner_fee"] is None
    assert card["partner_kyc"] is False and card["settles_digital"] is False
    assert card["fee_payer"] == "taxo"

    opened = await _open(client, captain["headers"], method_id, purpose="subscription", amount="1", plan_id=str(plan_id))
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    # **الرابطُ النسبيُّ يُكمَّل بنطاق Whop**
    assert opened.json()["checkout_url"] == "https://whop.com/checkout/ch_1/"
    # **ثمنُ الخطّة من الخادم** (المرسَلُ «1» يُتجاهل) — دفعةٌ واحدةٌ بالدينار لحساب المالك، بلا صرف
    assert opened.json()["request"]["amount"] == "10.000"
    plan = fake.created[0]["plan"]
    assert plan == plan | {"company_id": COMPANY, "currency": "jod", "plan_type": "one_time", "initial_price": 10.0}
    # **لا بيانات بطاقةٍ ولا اسمَ ولا هاتف** — مرجعُ طلبنا وحدَه
    assert set(fake.created[0]["metadata"]) == {"order_ref", "source"} and fake.created[0]["metadata"]["order_ref"]
    assert fake.created[0]["redirect_url"].endswith(f"r={request_id}")

    # **ما دام لم يكتمل** — دفعةٌ معلّقةٌ عند البنك لا تحرّك شيئاً
    fake.pay("ch_1", status="pending", substatus="pending")
    assert (await _deliver(client, "ch_1", "payment.pending"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0

    fake.payments.clear()
    fake.pay("ch_1")
    assert (await _deliver(client, "ch_1"))["applied"] == 1
    assert (await _deliver(client, "ch_1"))["applied"] == 0
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert await _entries(session_factory, request_id) == 1
    assert row.gateway_message == "10.000 JOD"


# ------------------------------------------------------------------ الإشعار: المزوَّرُ والقديمُ يُردّان


@pytest.mark.parametrize("forgery", ["wrong_secret", "stale", "no_signature"])
async def test_a_forged_or_stale_webhook_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]
    fake.pay("ch_1")

    if forgery == "wrong_secret":
        body, headers = _hook("ch_1", secret="ws_not-the-secret")
    elif forgery == "stale":
        # **توقيعٌ صحيحٌ لكنّه أقدمُ من خمس دقائق** — إعادةُ بثٍّ لا تُقبل
        body, headers = _hook("ch_1", at=int(time.time()) - whop.WEBHOOK_TOLERANCE_SECONDS - 60)
    else:
        body, headers = _hook("ch_1")
        headers.pop("webhook-signature")
    refused = await client.post("/payment-requests/webhook/whop", content=body, headers=headers)
    assert refused.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ المستردُّ والفاشلُ والمنتهي — بلا مال


@pytest.mark.parametrize("substatus", ["refunded", "partially_refunded", "dispute_lost"])
async def test_a_reversed_payment_is_rejected_without_money_and_says_why(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, substatus: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("ch_1", substatus=substatus)
    await _deliver(client, "ch_1", "payment.succeeded")
    row = await _row(session_factory, request_id)
    assert row.status.value == "rejected"
    assert row.rejection_reason == payment_reasons.CARD_REFUNDED
    assert await _entries(session_factory, request_id) == 0


async def test_failed_attempts_leave_it_pending_and_the_sweep_cancels_it_without_money(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**رفضُ البنك لمحاولةٍ لا يُغلق الطلب** — الكبتنُ يعيد في الصفحة نفسِها؛ **والمهلةُ تغلقه** إن لم يكتمل."""
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("ch_1", status="void", substatus="failed")
    fake.pay("ch_1", status="uncollectible", substatus="failed")
    assert (await _deliver(client, "ch_1", "payment.failed"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"

    far = datetime.now(UTC) + timedelta(days=1)
    async with session_factory() as session:
        await payment_requests.expire_stale(session, now=far)
    row = await _row(session_factory, request_id)
    assert row.status.value == "cancelled"
    assert row.cancel_reason == payment_requests.EXPIRED_REASON
    assert await _entries(session_factory, request_id) == 0


async def test_a_payment_to_another_account_or_currency_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("ch_1", account_id="biz_someone_else")
    assert (await _deliver(client, "ch_1"))["applied"] == 0
    fake.payments.clear()
    fake.pay("ch_1", currency="eur", total={"amount": "13.00", "currency": "eur"})
    assert (await _deliver(client, "ch_1"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


async def test_a_paid_amount_that_differs_from_the_request_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**شرطُ المالك «a credit mismatches the charge»** — دُفع أقلُّ من المطلوب (رمزُ خصمٍ في حساب Whop مثلاً): لا قيد،
    ويبقى الطلبُ معلّقاً بسببٍ مكتوبٍ يراه المالك، ولا يُطلب من صاحبه أن يدفع ثانية."""
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("ch_1", total={"amount": "5.000", "currency": "jod"})
    await _deliver(client, "ch_1")
    row = await _row(session_factory, request_id)
    assert row.status.value == "pending" and row.outcome_note
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ إشعارٌ فائت


async def test_a_missed_webhook_is_settled_once_by_the_fallback_check(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.pay("ch_1")
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
    assert (await _deliver(client, "ch_1"))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ المستحقّات


async def test_paying_dues_by_whop_clears_them_and_lifts_the_block(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory)
    captain = await approved_driver(client, session_factory)
    async with session_factory() as session:
        session.add(DriverDebt(
            driver_id=captain["driver_id"], country_code=CountryCode.JO, source=DriverDebtSource.RIDE_COMMISSION,
            amount=Decimal("6.500"), collected=Decimal("0"), currency=Currency.JOD, status=DriverDebtStatus.OUTSTANDING,
        ))
        driver = await session.get(Driver, captain["driver_id"])
        driver.debt_blocked = True
        await session.commit()

    request_id = (await _open(client, captain["headers"], method_id, amount="6.500")).json()["request"]["id"]
    fake.pay("ch_1", total={"amount": "6.500", "currency": "jod"})
    assert (await _deliver(client, "ch_1"))["applied"] == 1

    async with session_factory() as session:
        debt = await session.scalar(select(DriverDebt).where(DriverDebt.driver_id == captain["driver_id"]))
        driver = await session.get(Driver, captain["driver_id"])
        assert debt.status is DriverDebtStatus.SETTLED and driver.debt_blocked is False
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ مطفأةٌ ومخفيّة — ومتى تُعرض ولمن


async def test_hidden_without_keys_and_shown_only_to_drivers(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    method_id = await _jordan_whop(session_factory, contract=False)
    captain = await approved_driver(client, session_factory)
    listed = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert listed.status_code == 403, listed.text
    assert (await _open(client, captain["headers"], method_id)).status_code in (409, 503)

    await _enable_provider(
        session_factory, "whop", {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": COMPANY}, country="JO"
    )
    shown = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    assert [row["code"] for row in shown["methods"]] == ["whop_card"]
    rider = await rider_session(client, RIDER)
    hidden = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert hidden.status_code == 403, hidden.text
    assert (await _open(client, rider["headers"], method_id)).status_code == 422


async def test_switched_off_it_is_hidden_and_does_not_open_even_with_keys(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**مطفأةٌ كما تُرفع** («OFF and hidden from all drivers») — ولو أُدخلت المفاتيح؛ **والطرقُ القائمةُ لا تتغيّر**."""
    fake = _install(monkeypatch)
    method_id = await _jordan_whop(session_factory, flag=False)
    captain = await approved_driver(client, session_factory)
    off = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert off.status_code == 403
    assert (await _open(client, captain["headers"], method_id)).status_code == 403
    assert fake.created == []

    await enable_features(session_factory, "whop_card_enabled")
    on = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    assert [row["code"] for row in on["methods"]] == ["whop_card"]


async def test_algeria_and_libya_are_locked_in_the_server(client: AsyncClient, admin_headers: dict) -> None:
    assert payment_gateways.switch_allowed("whop_card_enabled", CountryCode.JO)
    for country in (CountryCode.DZ, CountryCode.LY):
        assert not payment_gateways.switch_allowed("whop_card_enabled", country)
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": country, "feature_key": "whop_card_enabled", "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 422, refused.text


# ------------------------------------------------------------------ الراكب: شحنُ المحفظة ودفعُ الرحلة


async def _jordan_rider_whop(session_factory, *flags: str) -> uuid.UUID:
    """**صفُّ الراكب كما يضعه `0160`** — شحنٌ وحدَه، بلا حدٍّ أعلى؛ ومفتاحاه مطفآن هناك فيُشعل هنا ما يطلبه الاختبار."""
    if flags:
        await enable_features(session_factory, *flags)
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="whop_rider_card",
            name="شحن المحفظة بالبطاقة", integration="whop", enabled=True, for_topup=True, for_subscription=False,
            fee_bearer="taxo", sort_order=2,
        )
        session.add(method)
        await session.commit()
        return method.id


async def test_a_rider_tops_up_by_card_once_and_each_audience_keeps_its_own_row(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    driver_row = await _jordan_whop(session_factory)
    rider_row = await _jordan_rider_whop(session_factory, "whop_rider_topup_enabled")
    rider = await rider_session(client, RIDER)
    captain = await approved_driver(client, session_factory)

    seen = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])).json()
    assert [row["code"] for row in seen["methods"]] == ["whop_rider_card"]
    seen = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    assert [row["code"] for row in seen["methods"]] == ["whop_card"]
    # **لا يعبر أحدٌ إلى صفِّ غيره** ولو أرسل معرّفَه بيده
    assert (await _open(client, rider["headers"], driver_row)).status_code == 422
    assert (await _open(client, captain["headers"], rider_row)).status_code == 422

    opened = await _open(client, rider["headers"], rider_row)
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    fake.pay("ch_1")
    assert (await _deliver(client, "ch_1"))["applied"] == 1
    assert (await _deliver(client, "ch_1"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "approved"
    assert await _entries(session_factory, request_id) == 1
    assert Decimal((await wallet_of(client, rider["headers"]))["balance"]) == Decimal("10.000")


async def test_either_rider_switch_opens_the_rider_row_and_both_off_hide_it(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    await _jordan_whop(session_factory, flag=False)
    await _jordan_rider_whop(session_factory)
    rider = await rider_session(client, RIDER)
    off = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert off.status_code == 403, off.text

    # **دفعُ الرحلة بالبطاقة وحدَه** يكفي: هو شحنٌ بقيمتها ثمّ دفعٌ من المحفظة
    await enable_features(session_factory, "whop_rider_trip_enabled")
    on = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])).json()
    assert [row["code"] for row in on["methods"]] == ["whop_rider_card"]


async def test_a_trip_cancelled_after_paying_by_card_leaves_the_money_in_the_wallet(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, jordan_settings: None
) -> None:
    """**قرارُ المالك ٢٠٢٦-١١-١٣**: البطاقةُ تشحن المحفظةَ بقيمة الرحلة — **فإلغاءُ الرحلة لا يمسّ الشحن**، والمبلغُ يبقى للراكب."""
    fake = _install(monkeypatch)
    await _jordan_whop(session_factory, flag=False)
    rider_row = await _jordan_rider_whop(session_factory, "whop_rider_trip_enabled")
    rider = await rider_session(client, RIDER)
    ride = await request_ride(client, rider["headers"])

    request_id = (await _open(client, rider["headers"], rider_row)).json()["request"]["id"]
    fake.pay("ch_1")
    assert (await _deliver(client, "ch_1"))["applied"] == 1

    cancelled = await client.post(f"/rides/{ride['id']}/cancel", json={}, headers=rider["headers"])
    assert cancelled.status_code == 200, cancelled.text
    assert Decimal((await wallet_of(client, rider["headers"]))["balance"]) == Decimal("10.000")
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ المحوِّلُ وحدَه


def test_a_dollar_contract_charges_dollars_at_the_peg() -> None:
    gateway = whop.build_whop(
        {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": COMPANY, "currency": "usd"}
    )
    assert gateway.card_currency == "USD" and gateway.usd_per_jod == Decimal("1.4104")
    default = whop.build_whop({"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": COMPANY})
    assert default.card_currency == "JOD" and default.usd_per_jod is None


def test_missing_contract_values_keep_the_method_hidden() -> None:
    for values in (
        {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE},
        {"api_key": API_VALUE, "company_id": COMPANY, "webhook_secret": ""},
        {"webhook_secret": HOOK_VALUE, "company_id": COMPANY},
        {"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": "not-a-company"},
    ):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            whop.build_whop(values)


def test_the_card_is_charged_exactly_the_dues_in_dollars_rounded_up() -> None:
    assert whop.charge_amount(Decimal("10.000"), Decimal("1.4104")) == Decimal("14.11")
    assert whop.charge_amount(Decimal("6.500"), Decimal("1.4104")) == Decimal("9.17")
    assert whop.charge_amount(Decimal("1.000"), Decimal("1.41")) == Decimal("1.41")


def test_a_webhook_without_a_checkout_id_names_nothing() -> None:
    gateway = whop.build_whop({"api_key": API_VALUE, "webhook_secret": HOOK_VALUE, "company_id": COMPANY})
    body, headers = _hook("not-a-checkout")
    assert gateway.webhook_ids(headers, body) == []


# ------------------------------------------------------------------ ترتيبُ طرق الدفع (أمرُ المالك ٢٠٢٦-١١-١٣: «Whop first for Jordan»)


async def test_the_owner_orders_payment_methods_per_country_and_the_apps_read_it(
    client: AsyncClient, admin_headers: dict
) -> None:
    saved = await client.patch(
        "/admin/settings/payments/JO", json={"payment_method_order": ["card", "wallet", "cliq", "cash"]}, headers=admin_headers
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["payment_method_order"] == ["card", "wallet", "cliq", "cash"]

    published = {c["country_code"]: c for c in (await client.get("/config")).json()["countries"]}
    assert published["JO"]["payment_method_order"] == ["card", "wallet", "cliq", "cash"]
    # **الجزائرُ وليبيا «كما كانت»** — لا ترتيبَ يُكتب لهما
    for other in ("DZ", "LY"):
        if other in published:
            assert published[other]["payment_method_order"] == []

    # **كلُّ طريقةٍ مرّة، ومن الأربع وحدَها** — والفارغةُ تعيد «كما كان»
    for bad in (["card", "card"], ["bitcoin"]):
        refused = await client.patch("/admin/settings/payments/JO", json={"payment_method_order": bad}, headers=admin_headers)
        assert refused.status_code == 422, refused.text
    cleared = await client.patch("/admin/settings/payments/JO", json={"payment_method_order": []}, headers=admin_headers)
    assert cleared.json()["payment_method_order"] == []
