"""**بوّابةُ Freemius الاحتياطيّة لاشتراك الكبتن** (أمرُ المالك ٢٠٢٦-١١-٢٦). **ما يُقاس هنا شروطُه بلفظها**:

- «verified webhooks» — مزوَّرٌ أو غائبُ التوقيع يُردّ بـ`401` ولا يحرّك شيئاً؛ والتوقيعُ HMAC-SHA256 مكتوبٌ هنا مستقلّاً عن المحوِّل.
- «credit once through the ledger with audit» — المكرَّرُ قيدٌ واحد، **ومتزامنان كذلك ولو كان للكبتن صفحتان مفتوحتان**.
- «PENDING/APPROVED/REFUNDED» — الاستردادُ بعد الاعتماد يُلغي الاشتراكَ ويعيد المحفظةَ كما كانت بقيودٍ مقابلة، وإعادتُه لا تعكس مرّتين.
- «the same price guard» — لا يُفتح دفعٌ إلا لما يدفعه الكبتنُ الآن = 3 أو 17 أو 45 أو 60، **وبخطّته المربوطة**.
- «website build only (never in the Play build)» — نسخةُ Play تُردّ ولو اشتعل مفتاحُ الموقع.
- «Jordan only (Libya/Algeria refused by the server)» — مقفلتان في الخادم، وحسابٌ من غير الأردن يُردّ بسببه.
- «OFF / Digistore24 / Freemius … the captain sees only the selected one … audit every change» — إشعالُ بوّابةٍ يُطفئ الأخرى بقيدَي تدقيق.

**والربطُ بالبريد** (صفحةُ Freemius لا تحمل مرجعَنا): دفعةٌ لبريدٍ لا طلبَ له لا تُربط بأقرب طلب.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import uuid
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, PaymentProviderKind
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import payment_gateways, payment_requests
from app.services.payment_gateways import freemius
from tests.helpers import RIDER, _enable_provider, approved_driver, enable_features, ensure_plan, rider_session

pytestmark = pytest.mark.asyncio

#: **قيمٌ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
PRODUCT = str(20000 + secrets.randbelow(9000))
PUBLIC_VALUE = secrets.token_hex(12)
SECRET_VALUE = secrets.token_hex(16)
BEARER_VALUE = secrets.token_hex(16)
PLANS = {"daily": "41001", "weekly": "41007", "monthly": "41030", "monthly_full": "41060"}
USD = {"daily": "4.25", "weekly": "24.00", "monthly": "63.50", "monthly_full": "84.50"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """**لا شبكةَ في الاختبار**: فحصُ الصحّة قبل فتح الصفحة يُجاب من نقلٍ مزيَّف — وأيُّ نداءٍ آخر يُسجَّل ويُردّ 404."""
    import httpx

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == f"/v1/products/{PRODUCT}.json":
            assert request.headers.get("authorization") == f"Bearer {BEARER_VALUE}"
            return httpx.Response(200, json={"id": PRODUCT, "title": "TAXO Driver"})
        return httpx.Response(404, json={"error": f"unexpected {request.url.path}"})

    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(handler))
    return seen


def _contract(**extra: str) -> dict[str, str]:
    return {
        "product_id": PRODUCT, "public_key": PUBLIC_VALUE, "secret_key": SECRET_VALUE, "api_token": BEARER_VALUE,
        **{f"plan_{plan}": pid for plan, pid in PLANS.items()},
    } | extra


def _official_sign(body: bytes, secret: str = SECRET_VALUE) -> str:
    """**`hash_hmac('sha256', $input, SECRET)`** كما في مثالهم الرسميّ — مستقلّاً عن المحوِّل، فلا يصدّق المحوِّلُ نفسَه."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event(payment_id: str, *, email: str, plan: str = "monthly", kind: str = "payment", bound: str | None = None,
           environment: int = 0, product: str | None = None, plan_id: str | None = None) -> bytes:
    payment: dict[str, object] = {
        "id": payment_id, "plugin_id": product or PRODUCT, "user_id": "7001", "plan_id": plan_id or PLANS[plan],
        "pricing_id": "8001", "gross": USD[plan] if kind == "payment" else "-" + USD[plan], "currency": "usd",
        "type": kind, "environment": environment, "is_renewal": False, "gateway_fee": 0,
    }
    if bound:
        payment["bound_payment_id"] = bound
    return json.dumps({
        "id": "ev" + secrets.token_hex(4), "type": "payment.created" if kind == "payment" else "payment.refund",
        "plugin_id": product or PRODUCT, "objects": {"payment": payment, "user": {"id": "7001", "email": email}},
    }).encode()


async def _deliver(client: AsyncClient, body: bytes, *, signature: str | None = None) -> int:
    response = await client.post(
        "/payment-requests/webhook/freemius", content=body,
        headers={"content-type": "application/json", "x-signature": signature if signature is not None else _official_sign(body)},
    )
    return response.status_code


async def _jordan(session_factory, *, contract: dict[str, str] | None = None, web: bool = True) -> uuid.UUID:
    """**كما تضعها `0194`** — صفٌّ للاشتراك وحدَه، **والمفتاحُ مطفأٌ هناك** فيُشعَل هنا ما يلزم الاختبار."""
    await _enable_provider(session_factory, "freemius", contract or _contract(), country="JO")
    await enable_features(session_factory, "wallet_enabled")
    if web:
        await enable_features(session_factory, "freemius_card_enabled")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="freemius_card",
            name="الدفع بالبطاقة المصرفية", integration="freemius", enabled=True, for_topup=False, for_subscription=True,
            fee_bearer="taxo", sort_order=1, max_amount=Decimal("100.000"),
        )
        session.add(method)
        await session.commit()
        return method.id


async def _captain(client: AsyncClient, session_factory, *, email: str | None = "auto", name: str = "سامي أحمد العلي") -> dict:
    captain = await approved_driver(client, session_factory, subscribed=False)
    address = f"cap{secrets.token_hex(4)}@example.com" if email == "auto" else email
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(captain["user_id"]))
        user.email = address
        user.name = name
        await session.commit()
    captain["email"] = address
    return captain


async def _open(client: AsyncClient, session_factory, headers: dict, method_id: uuid.UUID, *, price: str = "45",
                name: str = "TAXO X30 — شهري", channel: str | None = None):
    plan_id = await ensure_plan(session_factory, country="JO", name=name, price=price)
    body = {"provider_id": str(method_id), "purpose": "subscription", "amount": "1", "plan_id": str(plan_id)}
    if channel is not None:
        body["channel"] = channel
    return await client.post("/payment-requests/checkout", json=body, headers=headers)


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


async def _count_requests(session_factory) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(PaymentRequest)) or 0)


def _pid() -> str:
    return str(900000 + secrets.randbelow(99999))


# ------------------------------------------------------------------ الشراء: إشعارٌ موقَّعٌ وحدَه يفعّل، ومكرَّرُه لا شيء


async def test_signed_webhook_activates_once_and_a_resent_one_credits_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "freemius_card")
    # **ما يُقال قبل الدفع**: بطاقةٌ بالدولار **بلا سعرٍ يُعرض**، ومعالجُها Freemius ورسمُه على TAXO، والمبالغُ الأربعة وحدَها
    assert card["charge_currency"] == "USD" and card["charge_rate"] is None
    assert card["partner"] == "Freemius" and card["partner_fee"] is None
    assert [Decimal(a) for a in card["fixed_amounts"]] == [Decimal("3"), Decimal("17"), Decimal("45"), Decimal("60")]

    opened = await _open(client, session_factory, captain["headers"], method_id)
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    url = opened.json()["checkout_url"]
    # **الخطّةُ بعرضها على صفحتهم المستضافة، بدفعةٍ واحدة، والبريدُ للقراءة وحدَها** — ولا هاتفَ يخرج
    assert url.startswith(f"https://checkout.freemius.com/product/{PRODUCT}/?")
    query = parse_qs(urlsplit(url).query)
    assert query["plan_id"] == [PLANS["monthly"]] and query["billing_cycle"] == ["lifetime"]
    assert query["user_email"] == [captain["email"]] and query["readonly_user"] == ["1"]
    assert query["user_firstname"] == ["سامي"] and query["user_lastname"] == ["أحمد العلي"]
    assert "sandbox" not in query and "s_ctx_ts" not in query
    assert all("+962" not in value for values in query.values() for value in values)

    # **العودةُ من الصفحة بلا إشعارٍ لا تفعّل شيئاً**
    back = await client.post(f"/payment-requests/{request_id}/refresh", headers=captain["headers"])
    assert back.status_code == 200 and back.json()["status"] == "pending"

    payment_id = _pid()
    body = _event(payment_id, email=captain["email"].upper())
    assert await _deliver(client, body) == 200
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert row.external_id == f"fs:{payment_id}"
    assert row.gateway_message.startswith(f"Freemius payment {payment_id}")
    assert await _count(session_factory, f"payment_request:{request_id}") == 1
    assert await _count(session_factory, f"payreq_sub:{request_id}") == 1

    # **إعادةُ الإشعار** — هي نفسُها لا تكتب شيئاً
    assert await _deliver(client, body) == 200
    assert await _deliver(client, _event(payment_id, email=captain["email"])) == 200
    assert await _count(session_factory, f"payment_request:{request_id}") == 1
    assert await _count(session_factory, f"payreq_sub:{request_id}") == 1


async def test_three_identical_webhooks_at_once_bind_one_page_and_credit_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**التزامن**: صفحتان مفتوحتان للكبتن نفسِه بالمبلغ نفسِه، ودفعةٌ واحدةٌ يصل إشعارُها ثلاثاً في اللحظة نفسِها — **طلبٌ واحدٌ يُربط
    ويُعتمد، والآخرُ يبقى معلَّقاً**. والذي يحرس ذلك السؤالُ الثاني بعد القفل في `freemius_link.bind`."""
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    first = await _open(client, session_factory, captain["headers"], method_id)
    second = await _open(client, session_factory, captain["headers"], method_id)
    assert first.status_code == 201 and second.status_code == 201, (first.text, second.text)
    ids = {first.json()["request"]["id"], second.json()["request"]["id"]}
    assert len(ids) == 2
    body = _event(_pid(), email=captain["email"])

    answers = await asyncio.wait_for(asyncio.gather(_deliver(client, body), _deliver(client, body), _deliver(client, body)), 30)
    assert answers == [200, 200, 200]
    statuses = sorted([(await _row(session_factory, rid)).status.value for rid in ids])
    assert statuses == ["approved", "pending"]
    credited = sum([await _count(session_factory, f"payment_request:{rid}") for rid in ids])
    assert credited == 1
    assert sum([await _count(session_factory, f"payreq_sub:{rid}") for rid in ids]) == 1


# ------------------------------------------------------------------ التوقيع


@pytest.mark.parametrize("forgery", ["wrong_secret", "no_signature", "tampered", "not_hex"])
async def test_a_forged_webhook_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, forgery: str
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    body = _event(_pid(), email=captain["email"])

    if forgery == "wrong_secret":
        status = await _deliver(client, body, signature=_official_sign(body, secrets.token_hex(16)))
    elif forgery == "no_signature":
        status = await _deliver(client, body, signature="")
    elif forgery == "tampered":
        status = await _deliver(client, body.replace(b'"63.50"', b'"1.00"'), signature=_official_sign(body))
    else:
        status = await _deliver(client, body, signature="z" * 64)
    assert status == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _count(session_factory, f"payment_request:{request_id}") == 0


def test_the_adapter_signature_matches_the_official_algorithm() -> None:
    body = b'{"type":"payment.created","objects":{}}'
    assert freemius.sign(body, SECRET_VALUE) == _official_sign(body)


def test_an_event_without_a_payment_is_accepted_and_names_nothing() -> None:
    gateway = freemius.build_freemius(_contract())
    body = json.dumps({"type": "install.installed", "plugin_id": PRODUCT, "objects": {"user": {"email": "a@b.c"}}}).encode()
    assert gateway.webhook_ids({"x-signature": _official_sign(body)}, body) == []


# ------------------------------------------------------------------ خطّةٌ أخرى · وضعٌ آخر · منتجٌ آخر · بريدٌ آخر — بلا مال


async def test_a_payment_for_another_mode_product_plan_or_email_is_not_credited(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]

    # **مالٌ تجريبيٌّ على عقدٍ حيّ**، ومنتجٌ ليس لنا، وخطّةٌ ليست لنا — كلُّها تُجاب بنجاحٍ ولا تُقيَّد
    assert await _deliver(client, _event(_pid(), email=captain["email"], environment=1)) == 200
    assert await _deliver(client, _event(_pid(), email=captain["email"], product="99999")) == 200
    assert await _deliver(client, _event(_pid(), email=captain["email"], plan_id="99999")) == 200
    # **خطّةُ اليوم لا تُربط بطلب الشهر**، **وبريدٌ بُدّل في الصفحة لا يُربط بأقرب طلب**
    assert await _deliver(client, _event(_pid(), email=captain["email"], plan="daily")) == 200
    assert await _deliver(client, _event(_pid(), email="someone-else@example.com")) == 200
    row = await _row(session_factory, request_id)
    assert row.status.value == "pending" and not (row.external_id or "").startswith("fs:")
    assert await _count(session_factory, f"payment_request:{request_id}") == 0


# ------------------------------------------------------------------ حارسُ السعر


@pytest.mark.parametrize("price", ["50", "17.5", "61"])
async def test_a_price_without_a_plan_opens_no_payment(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, price: str
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    refused = await _open(client, session_factory, captain["headers"], method_id, price=price, name=f"خطة {price}")
    assert refused.status_code >= 400, refused.text


@pytest.mark.parametrize(("price", "plan"), [("3", "daily"), ("17", "weekly"), ("45", "monthly"), ("60", "monthly_full")])
async def test_each_fixed_amount_opens_its_own_plan(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, price: str, plan: str
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    opened = await _open(client, session_factory, captain["headers"], method_id, price=price, name=f"خطة {plan}")
    assert opened.status_code == 201, opened.text
    assert parse_qs(urlsplit(opened.json()["checkout_url"]).query)["plan_id"] == [PLANS[plan]]


# ------------------------------------------------------------------ الاسترداد


async def test_a_refund_after_approval_reverses_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    payment_id = _pid()

    assert await _deliver(client, _event(payment_id, email=captain["email"])) == 200
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved"
    subscription_id = row.subscription_id

    refund = _event(_pid(), email=captain["email"], kind="refund", bound=payment_id)
    assert await _deliver(client, refund) == 200
    assert await _deliver(client, refund) == 200  # **إعادتُه لا تعكس مرّتين**
    row = await _row(session_factory, request_id)
    assert row.status.value == "refunded" and row.refund_reason
    assert await _count(session_factory, f"payment_request_refund:{request_id}") == 1
    assert await _count(session_factory, f"subscription_refund:{subscription_id}") == 1


async def test_a_refund_for_an_unknown_payment_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    opened = await _open(client, session_factory, captain["headers"], method_id)
    request_id = opened.json()["request"]["id"]
    assert await _deliver(client, _event(_pid(), email=captain["email"], kind="refund", bound=_pid())) == 200
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _count(session_factory, f"payment_request_refund:{request_id}") == 0


# ------------------------------------------------------------------ نسخةُ الموقع وحدَها · بريدٌ لازم · الأردنُّ وحدَه


async def test_the_play_build_never_opens_freemius(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    before = await _count_requests(session_factory)
    refused = await _open(client, session_factory, captain["headers"], method_id, channel="play")
    assert refused.status_code >= 400, refused.text
    assert await _count_requests(session_factory) == before
    assert "play" not in payment_gateways.CHANNEL_SWITCHES["freemius"]


async def test_an_account_without_email_is_told_to_add_one(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory, email=None)
    before = await _count_requests(session_factory)
    refused = await _open(client, session_factory, captain["headers"], method_id)
    assert refused.status_code >= 400, refused.text
    assert await _count_requests(session_factory) == before


@pytest.mark.parametrize("country", [CountryCode.DZ, CountryCode.LY])
async def test_a_non_jordan_account_cannot_open_a_freemius_payment(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, country: CountryCode
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    method_id = await _jordan(session_factory)
    captain = await _captain(client, session_factory)
    plan_id = await ensure_plan(session_factory, country="JO", name="TAXO X30 — شهري", price="45")
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(captain["user_id"]))
        user.country_code = country
        await session.commit()
    before = await _count_requests(session_factory)
    refused = await client.post(
        "/payment-requests/checkout",
        json={"provider_id": str(method_id), "purpose": "subscription", "amount": "1", "plan_id": str(plan_id)},
        headers=captain["headers"],
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "payment_gateway_country_unavailable"
    assert await _count_requests(session_factory) == before


async def test_hidden_without_its_switch_and_never_shown_to_riders(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    await _jordan(session_factory, web=False)
    captain = await _captain(client, session_factory)
    off = await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])
    assert "freemius_card" not in [r["code"] for r in (off.json().get("methods") or [])] if off.status_code == 200 else True
    rider = await rider_session(client, RIDER)
    await enable_features(session_factory, "freemius_card_enabled")
    hidden = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert "freemius_card" not in [r["code"] for r in (hidden.json().get("methods") or [])] if hidden.status_code == 200 else True


# ------------------------------------------------------------------ «بوابة الدفع بالبطاقة»: واحدةٌ على الأكثر، بتدقيق


async def test_choosing_one_card_gateway_turns_the_other_off_with_an_audit_row_each(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    async def put(flag: str, enabled: bool) -> dict:
        response = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": "JO", "feature_key": flag, "enabled": enabled},
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()["flags"]

    async def audits() -> int:
        async with session_factory() as session:
            return int(await session.scalar(
                select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.entity_type == "feature_flag")
            ) or 0)

    flags = await put("digistore24_card_enabled", True)
    assert flags["digistore24_card_enabled"] is True and flags.get("freemius_card_enabled") is not True
    before = await audits()
    flags = await put("freemius_card_enabled", True)
    assert flags["freemius_card_enabled"] is True and flags["digistore24_card_enabled"] is False
    assert await audits() == before + 2  # **قيدان**: إشعالُ Freemius وإطفاءُ Digistore24
    flags = await put("digistore24_card_enabled", True)
    assert flags["digistore24_card_enabled"] is True and flags["freemius_card_enabled"] is False
    flags = await put("digistore24_card_enabled", False)
    assert flags["digistore24_card_enabled"] is False and flags["freemius_card_enabled"] is False
    # **مفتاحُ Play لـDigistore24 لا تمسّه البوّابة** — له بابُه
    assert "digistore24_card_play_enabled" not in [key.value for key in payment_gateways.CARD_GATEWAY_FLAGS]


async def test_algeria_and_libya_are_locked_for_freemius(client: AsyncClient, admin_headers: dict) -> None:
    assert payment_gateways.switch_allowed("freemius_card_enabled", CountryCode.JO)
    for country in (CountryCode.DZ, CountryCode.LY):
        assert not payment_gateways.switch_allowed("freemius_card_enabled", country)
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": country, "feature_key": "freemius_card_enabled", "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 422, refused.text


# ------------------------------------------------------------------ العقدُ والتجربة


def test_missing_contract_values_keep_the_method_hidden() -> None:
    full = _contract()
    for missing in ("product_id", "public_key", "secret_key", "api_token"):
        with pytest.raises(payment_gateways.GatewayUnavailable):
            freemius.build_freemius({k: v for k, v in full.items() if k != missing})
    with pytest.raises(payment_gateways.GatewayUnavailable):
        freemius.build_freemius({k: v for k, v in full.items() if not k.startswith("plan_")})


def test_sandbox_links_carry_the_official_token_and_live_links_do_not() -> None:
    customer = payment_gateways.CheckoutCustomer("سامي", "+962790000000", "c@example.com", order_ref="TX-1")
    sandbox = freemius.build_freemius(_contract(test_mode="true"))
    pairs = dict(sandbox.checkout_params(plan_id=PLANS["daily"], customer=customer, return_url="https://x/r"))
    expected = hashlib.md5(f"{pairs['s_ctx_ts']}{PRODUCT}{SECRET_VALUE}{PUBLIC_VALUE}checkout".encode()).hexdigest()  # noqa: S324
    assert pairs["sandbox"] == expected
    # **اسمٌ بكلمةٍ واحدةٍ لا يُقفل** (لا اسمَ عائلةٍ مخترعاً)، **والهاتفُ لا يخرج**
    assert "readonly_user" not in pairs and "user_lastname" not in pairs and "+962790000000" not in pairs.values()
    live = freemius.build_freemius(_contract())
    assert "sandbox" not in dict(live.checkout_params(plan_id=PLANS["daily"], customer=customer, return_url=""))


def test_both_gateways_charge_the_same_dollars() -> None:
    """**مصدرٌ واحدٌ للدولار** — Freemius يقرأ `digistore24.PRICE_MAP`، فلا يفترق سعرا البوّابتين."""
    from app.services.payment_gateways import digistore24

    assert freemius.PRICE_MAP is digistore24.PRICE_MAP
    assert {amount: usd for amount, (_plan, usd) in freemius.PRICE_MAP.items()} == {
        Decimal("3.000"): Decimal("4.25"), Decimal("17.000"): Decimal("24.00"),
        Decimal("45.000"): Decimal("63.50"), Decimal("60.000"): Decimal("84.50"),
    }
