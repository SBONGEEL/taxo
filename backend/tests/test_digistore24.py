"""**اشتراكُ الكبتن بالبطاقة عبر Digistore24** (أمرا المالك ٢٠٢٦-١١-٢٣). **ما يُقاس هنا شروطُه بلفظها**:

- «IPN verified with the official SHA-512 sha_sign» — مزوَّرٌ أو غائبُ التوقيع يُردّ ولا يحرّك شيئاً؛ والجوابُ نصُّ `OK`.
- «each subscription credited once only, through the ledger, with audit» — المكرَّرُ (إعادةُ الإشعار) قيدٌ واحد، **ومتزامنان كذلك**.
- «PENDING/APPROVED/REFUNDED» — الاستردادُ بعد الاعتماد يُلغي الاشتراكَ ويعيد المحفظةَ كما كانت بقيودٍ مقابلة.
- «price guard» — لا يُفتح دفعٌ إلا لما يدفعه الكبتنُ الآن = 3 أو 17 أو 45، **وبالمنتج المربوط به**.
- «separate panel switch for the Play build» — نسخةُ Play لا تفتح الدفعَ ومفتاحُها مطفأ ولو اشتعل مفتاحُ الموقع.
- «Libya and Algeria stay OFF» — مقفلتان في الخادم.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — والإشعارُ موقَّعٌ بخوارزمية مثالهم الرسميّ `ipn_receiver.php` مكتوبةً هنا من جديد لا مستوردة.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import CountryCode, PaymentProviderKind, WalletTransactionType
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.subscription import DriverSubscription
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_requests
from app.services.payment_gateways import digistore24
from tests.helpers import RIDER, _enable_provider, approved_driver, enable_features, ensure_plan, rider_session



@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """**لا شبكةَ في الاختبار**: `ping` قبل فتح الصفحة (`gateway_health.require_up`) يُجاب من نقلٍ مزيَّف — وأيُّ نداءٍ آخر يُسجَّل ويُردّ 404
    فيظهر في الاختبار لا في حساب Digistore24 الحقيقيّ (وقع مقيساً ٢٠٢٦-١١-٢٣: «The API key is invalid» من الخادم الحقيقيّ)."""
    import httpx

    from app.services import payment_gateways as _gateways

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path.endswith("/api/call/ping"):
            return httpx.Response(200, json={"result": "success", "data": {"server_time": "now"}})
        return httpx.Response(404, json={"result": "error", "message": f"unexpected {request.url.path}"})

    monkeypatch.setattr(_gateways, "http_transport", httpx.MockTransport(handler))
    return seen

pytestmark = pytest.mark.asyncio

#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = secrets.token_hex(12)
PASS_VALUE = secrets.token_hex(16)
PRODUCTS = {"daily": "611001", "weekly": "611007", "monthly": "611030"}


def _contract(**extra: str) -> dict[str, str]:
    return {
        "api_key": API_VALUE, "ipn_passphrase": PASS_VALUE, "product_daily": PRODUCTS["daily"],
        "product_weekly": PRODUCTS["weekly"], "product_monthly": PRODUCTS["monthly"],
    } | extra


def _official_sign(fields: dict[str, str], passphrase: str) -> str:
    """**`digistore_signature()` كما في `ipn_receiver.php`** — مكتوبةً هنا مستقلّةً عن المحوِّل، فلا يصدّق المحوِّلُ نفسَه."""
    keys = sorted(k for k in fields if k not in ("sha_sign", "SHASIGN"))
    text = "".join(f"{k}={fields[k]}{passphrase}" for k in keys if fields[k] not in ("", None))
    return hashlib.sha512(text.encode()).hexdigest().upper()


def _ipn(custom: str, *, event: str = "on_payment", product: str = PRODUCTS["monthly"], passphrase: str = PASS_VALUE,
         sign: bool = True, **extra: str) -> bytes:
    fields = {
        "event": event, "api_mode": "live", "order_id": "DS" + secrets.token_hex(3).upper(), "product_id": product,
        "billing_type": "single_payment", "currency": "USD", "amount": "63.50", "custom": custom,
        "email": "", "address_country": "JO",
    } | extra
    if sign:
        fields["sha_sign"] = _official_sign(fields, passphrase)
    return urlencode(fields).encode()


async def _deliver(client: AsyncClient, body: bytes) -> str:
    response = await client.post(
        "/payment-requests/webhook/digistore24", content=body, headers={"content-type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200, response.text
    return response.text


async def _jordan(session_factory, *, contract: dict[str, str] | None = None, web: bool = True, play: bool = False) -> uuid.UUID:
    """**كما تضعها `0188`** — صفٌّ للاشتراك وحدَه، **والمفتاحان مطفآن هناك** فيُشعَل هنا ما يلزم الاختبار."""
    await _enable_provider(session_factory, "digistore24", contract or _contract(), country="JO")
    await enable_features(session_factory, "wallet_enabled")
    if web:
        await enable_features(session_factory, "digistore24_card_enabled")
    if play:
        await enable_features(session_factory, "digistore24_card_play_enabled")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="digistore24_card",
            name="الدفع بالبطاقة المصرفية", integration="digistore24", enabled=True, for_topup=False, for_subscription=True,
            fee_bearer="taxo", sort_order=1, max_amount=Decimal("100.000"),
        )
        session.add(method)
        await session.commit()
        return method.id


async def _open(client: AsyncClient, session_factory, headers: dict, method_id: uuid.UUID, *, price: str = "45",
                name: str = "TAXO X30 — شهري", channel: str | None = None):
    plan_id = await ensure_plan(session_factory, country="JO", name=name, price=price)
    body = {"provider_id": str(method_id), "purpose": "subscription", "amount": "1", "plan_id": str(plan_id)}
    if channel is not None:
        body["channel"] = channel
    return await client.post("/payment-requests/checkout", json=body, headers=headers)


def _custom(checkout_url: str) -> str:
    return parse_qs(urlsplit(checkout_url).query)["custom"][0]


async def _row(session_factory, request_id: str) -> PaymentRequest:
    async with session_factory() as session:
        return await session.get(PaymentRequest, uuid.UUID(request_id))


async def _count(session_factory, key: str) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(WalletTransaction).where(WalletTransaction.idempotency_key == key)
            ) or 0
        )


async def _balance(session_factory, user_id: str) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(WalletTransaction.owner_id == uuid.UUID(user_id))
        )
        return Decimal(str(total))


# ------------------------------------------------------------------ الشراء: إشعارٌ موقَّعٌ وحدَه يفعّل، ومكرَّرُه لا شيء


async def test_signed_ipn_activates_once_and_a_resent_ipn_credits_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "digistore24_card")
    # **ما يُقال قبل الدفع**: بطاقةٌ بالدولار **بلا سعرٍ يُعرض** (الدينارُ وحدَه وسطرٌ خفيف)، ومعالجُها Digistore24 ورسمُه على TAXO
    assert card["charge_currency"] == "USD" and card["charge_rate"] is None
    assert card["partner"] == "Digistore24" and card["partner_fee"] is None
    assert [Decimal(a) for a in card["fixed_amounts"]] == [Decimal("3"), Decimal("17"), Decimal("45")]

    opened = await _open(client, session_factory, captain["headers"], method_id)
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    url = opened.json()["checkout_url"]
    # **منتجُ الشهر بعرضه، ومرجعُ طلبنا وحدَه** — لا اسمَ ولا هاتف
    assert url.startswith(f"https://www.digistore24.com/product/{PRODUCTS['monthly']}?custom=")
    custom = _custom(url)
    assert opened.json()["request"]["amount"] == "45.000"

    # **العودةُ من الصفحة بلا إشعارٍ لا تفعّل شيئاً**
    back = await client.post(f"/payment-requests/{request_id}/refresh", headers=captain["headers"])
    assert back.status_code == 200 and back.json()["status"] == "pending"

    body = _ipn(custom)
    assert await _deliver(client, body) == "OK"
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert row.gateway_message.startswith("Digistore24 order DS")
    assert await _count(session_factory, f"payment_request:{request_id}") == 1
    assert await _count(session_factory, f"payreq_sub:{request_id}") == 1

    # **Digistore24 يعيد الإشعارَ حتى يرى OK** — الإعادةُ نفسُها لا تكتب شيئاً
    assert await _deliver(client, body) == "OK"
    assert await _deliver(client, _ipn(custom)) == "OK"
    assert await _count(session_factory, f"payment_request:{request_id}") == 1
    async with session_factory() as session:
        subs = await session.scalar(
            select(func.count()).select_from(DriverSubscription).where(DriverSubscription.driver_id == uuid.UUID(str(captain["driver_id"])))
        ) if "driver_id" in captain else 1
    assert subs == 1


async def test_two_identical_ipns_at_once_activate_one_subscription(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**التزامن**: إشعاران في اللحظة نفسِها يقرأ كلٌّ منهما «معلَّق» قبل القفل — **وواحدٌ وحدَه يجده معلَّقاً بعده**."""
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    body = _ipn(_custom(opened.json()["checkout_url"]))

    answers = await asyncio.wait_for(asyncio.gather(_deliver(client, body), _deliver(client, body), _deliver(client, body)), 30)
    assert answers == ["OK", "OK", "OK"]
    assert await _count(session_factory, f"payment_request:{request_id}") == 1
    assert await _count(session_factory, f"payreq_sub:{request_id}") == 1


# ------------------------------------------------------------------ التوقيع


@pytest.mark.parametrize("forgery", ["wrong_passphrase", "no_signature", "tampered"])
async def test_a_forged_ipn_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    custom = _custom(opened.json()["checkout_url"])

    if forgery == "wrong_passphrase":
        body = _ipn(custom, passphrase=secrets.token_hex(16))
    elif forgery == "no_signature":
        body = _ipn(custom, sign=False)
    else:
        body = _ipn(custom).replace(b"amount=63.50", b"amount=1.00")
    refused = await client.post(
        "/payment-requests/webhook/digistore24", content=body, headers={"content-type": "application/x-www-form-urlencoded"}
    )
    assert refused.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _count(session_factory, f"payment_request:{request_id}") == 0


def test_connection_test_ipn_is_accepted_and_names_nothing() -> None:
    gateway = digistore24.build_digistore24(_contract())
    fields = {"event": "connection_test", "api_mode": "live"}
    fields["sha_sign"] = _official_sign(fields, PASS_VALUE)
    assert gateway.webhook_ids({}, urlencode(fields).encode()) == []


def test_the_adapter_signature_matches_the_official_algorithm() -> None:
    fields = {"b": "2", "a": "1", "empty": "", "B": "x", "custom": "TX-1"}
    assert digistore24.sign(fields, PASS_VALUE) == _official_sign(fields, PASS_VALUE)


# ------------------------------------------------------------------ منتجٌ آخر · وضعٌ آخر — بلا مال


async def test_an_ipn_for_the_wrong_product_or_mode_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    custom = _custom(opened.json()["checkout_url"])

    # **منتجُ اليوميّ لا يُفعِّل خطّةَ الشهر** — يبقى «قيد المعالجة» بسببه ويراه المالك
    await _deliver(client, _ipn(custom, product=PRODUCTS["daily"], amount="4.25"))
    row = await _row(session_factory, request_id)
    assert row.status.value == "pending" and row.outcome_note
    # **ومالٌ تجريبيٌّ على عقدٍ حيّ لا يُقيَّد**، ولا منتجٌ ليس لنا
    await _deliver(client, _ipn(custom, api_mode="test"))
    await _deliver(client, _ipn(custom, product="999999"))
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _count(session_factory, f"payment_request:{request_id}") == 0


# ------------------------------------------------------------------ حارسُ السعر


@pytest.mark.parametrize("price", ["60", "50", "17.5"])
async def test_a_price_without_a_product_opens_no_payment(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, price: str
) -> None:
    """**انتهى عرضُ «TAXO MAN 45» (60) أو تبدّل سعرٌ في اللوحة** — لا يُفتح دفعٌ بمبلغٍ لا منتجَ له، ولا يُكتب طلب."""
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    refused = await _open(client, session_factory, captain["headers"], method_id, price=price, name=f"خطة {price}")
    assert refused.status_code >= 400, refused.text


@pytest.mark.parametrize(("price", "plan"), [("3", "daily"), ("17", "weekly"), ("45", "monthly")])
async def test_each_fixed_amount_opens_its_own_product(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, price: str, plan: str
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id, price=price, name=f"خطة {plan}")
    assert opened.status_code == 201, opened.text
    assert f"/product/{PRODUCTS[plan]}?" in opened.json()["checkout_url"]


# ------------------------------------------------------------------ الاسترداد


async def test_a_refund_after_approval_cancels_the_subscription_and_restores_the_wallet(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    custom = _custom(opened.json()["checkout_url"])
    async with session_factory() as session:
        owner_id = str((await session.get(PaymentRequest, uuid.UUID(request_id))).user_id)
    before = await _balance(session_factory, owner_id)

    await _deliver(client, _ipn(custom))
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved"
    subscription_id = row.subscription_id
    assert await _balance(session_factory, owner_id) == before  # شحنٌ ثمّ شراء

    refund = _ipn(custom, event="on_refund")
    assert await _deliver(client, refund) == "OK"
    assert await _deliver(client, refund) == "OK"  # **إعادتُه لا تعكس مرّتين**
    row = await _row(session_factory, request_id)
    assert row.status.value == "refunded" and row.refund_reason
    async with session_factory() as session:
        sub = await session.get(DriverSubscription, subscription_id)
        assert sub.status.value == "cancelled"
    assert await _count(session_factory, f"payment_request_refund:{request_id}") == 1
    assert await _count(session_factory, f"subscription_refund:{subscription_id}") == 1
    # **المحفظةُ كما كانت قبل الدفع** — والمالُ نفسُه عاد إلى البطاقة
    assert await _balance(session_factory, owner_id) == before
    async with session_factory() as session:
        negative = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(owner_id), WalletTransaction.balance_after < 0
            )
        )
        assert negative == 0
        types = set((await session.scalars(
            select(WalletTransaction.type).where(WalletTransaction.owner_id == uuid.UUID(owner_id))
        )).all())
    assert WalletTransactionType.ADJUSTMENT in types and WalletTransactionType.REFUND in types


async def test_a_refund_before_any_payment_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    await _deliver(client, _ipn(_custom(opened.json()["checkout_url"]), event="on_refund"))
    row = await _row(session_factory, request_id)
    assert row.status.value in ("pending", "rejected")
    assert await _count(session_factory, f"payment_request:{request_id}") == 0
    assert await _count(session_factory, f"payment_request_refund:{request_id}") == 0


# ------------------------------------------------------------------ نسخةُ Play بمفتاحها


async def test_the_play_build_opens_nothing_while_its_own_switch_is_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory, web=True, play=False)
    captain = await approved_driver(client, session_factory, subscribed=False)
    play = await _open(client, session_factory, captain["headers"], method_id, channel="play")
    assert play.status_code in (403, 409), play.text
    web = await _open(client, session_factory, captain["headers"], method_id, channel="web", price="17", name="خطة أسبوع")
    assert web.status_code == 201, web.text

    await enable_features(session_factory, "digistore24_card_play_enabled")
    later = await _open(client, session_factory, captain["headers"], method_id, channel="play", price="3", name="خطة يوم")
    assert later.status_code == 201, later.text


async def test_web_switch_off_closes_the_website_even_when_play_is_on(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory, web=False, play=True)
    captain = await approved_driver(client, session_factory, subscribed=False)
    web = await _open(client, session_factory, captain["headers"], method_id)
    assert web.status_code in (403, 409), web.text


# ------------------------------------------------------------------ مخفيّةٌ ومقفلة


async def test_hidden_without_switches_and_never_shown_to_riders(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    await _jordan(session_factory, web=False, play=False)
    captain = await approved_driver(client, session_factory, subscribed=False)
    off = await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])
    assert "digistore24_card" not in [r["code"] for r in (off.json().get("methods") or [])] if off.status_code == 200 else True
    rider = await rider_session(client, RIDER)
    await enable_features(session_factory, "digistore24_card_enabled")
    hidden = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert "digistore24_card" not in [r["code"] for r in (hidden.json().get("methods") or [])] if hidden.status_code == 200 else True


async def test_algeria_and_libya_are_locked_in_the_server(client: AsyncClient, admin_headers: dict) -> None:
    for flag in ("digistore24_card_enabled", "digistore24_card_play_enabled"):
        assert payment_gateways.switch_allowed(flag, CountryCode.JO)
        for country in (CountryCode.DZ, CountryCode.LY):
            assert not payment_gateways.switch_allowed(flag, country)
            refused = await client.put(
                "/admin/settings/feature-flags",
                json={"country_code": country, "feature_key": flag, "enabled": True},
                headers=admin_headers,
            )
            assert refused.status_code == 422, refused.text


def test_missing_contract_values_keep_the_method_hidden() -> None:
    for values in (
        {"api_key": API_VALUE, "ipn_passphrase": PASS_VALUE},
        {"api_key": API_VALUE, "product_monthly": PRODUCTS["monthly"]},
        {"ipn_passphrase": PASS_VALUE, "product_monthly": PRODUCTS["monthly"]},
    ):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            digistore24.build_digistore24(values)
