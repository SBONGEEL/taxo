"""**الدفعُ بالبطاقة المصرفية للكبتن في الأردن** — NOWPayments (أمرُ المالك ٢٠٢٦-١١-١١). **ما يُقاس هنا شروطُه بلفظها**:

- «credit the subscription or clear the dues only on a final «finished» status» — وما سواه لا يحرّك مالاً.
- «Handle partial payments, expiries and failures with clear Arabic messages» — لكلٍّ سببُه المكتوب.
- «Idempotent, a fallback status check if a webhook is missed» — إشعارٌ مكرَّرٌ قيدٌ واحد، **وإشعارٌ فائتٌ تحسمه التسويةُ الدوريّة**.
- «IPN webhook verified (HMAC signature)» — توقيعٌ مزوَّرٌ يُردّ.
- «Until they're entered, the method stays hidden automatically» · «Algeria and Libya locked off» · للكباتن وحدَهم · سقفُ اليوم.

**والمحوِّلُ الحقيقيُّ هو المُختبَر** — الشبكةُ وحدَها مزيّفة، بأشكال وثائق NOWPayments المنشورة.
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
from tests.helpers import RIDER, _enable_provider, approved_driver, enable_features, ensure_plan, rider_session

pytestmark = pytest.mark.asyncio

#: **مفتاحان مولَّدان لكلِّ تشغيلٍ لا حرفيّان** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفعٍ سابق
API_VALUE = "np_" + secrets.token_hex(10)
IPN_VALUE = secrets.token_hex(16)


class NowpayFake:
    """**NOWPayments بلا شبكة** — `POST /payment` يعيد معرّفاً ورابطَ صفحة البطاقة، و`GET /payment/{id}` يقول الحالَ المضبوطة."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self.status: dict[str, str] = {}
        self.outcome: dict[str, tuple[str, str]] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/status"):
            return httpx.Response(200, json={"message": "OK"})
        if request.method == "POST" and path.endswith("/payment"):
            assert request.headers.get("x-api-key") == API_VALUE
            body = json.loads(request.content)
            self.created.append(body)
            self.headers.append(dict(request.headers))
            payment_id = str(5000 + len(self.created))
            self.status[payment_id] = "waiting"
            return httpx.Response(
                201,
                json={
                    "payment_id": payment_id,
                    "payment_status": "waiting",
                    "price_amount": body["price_amount"],
                    "price_currency": body["price_currency"],
                    "redirectData": {"redirect_url": f"https://partner.example/checkout/{payment_id}"},
                },
            )
        if request.method == "GET" and "/payment/" in path:
            payment_id = path.rsplit("/", 1)[-1]
            if payment_id not in self.status:
                return httpx.Response(404, json={"message": "Payment not found"})
            amount, currency = self.outcome.get(payment_id, ("", ""))
            return httpx.Response(
                200,
                json={
                    "payment_id": int(payment_id),
                    "payment_status": self.status[payment_id],
                    "outcome_amount": amount or None,
                    "outcome_currency": currency or None,
                },
            )
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})


def _install(monkeypatch: pytest.MonkeyPatch) -> NowpayFake:
    fake = NowpayFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)
    return fake


async def _jordan_card(session_factory, *, contract: bool = True, flag: bool = True, daily_cap: str = "") -> uuid.UUID:
    """**كما يضعها `0158` على الإنتاج** — صفُّ الطريقة والمفتاحُ مشتعلاً — **والعقدُ بمفتاحَي المالك** (بالخدمة نفسِها)."""
    if contract:
        await _enable_provider(
            session_factory, "nowpay", {"api_key": API_VALUE, "ipn_secret": IPN_VALUE, "daily_cap": daily_cap}, country="JO"
        )
    # **المحفظةُ مشتعلةٌ في الأردن على الإنتاج** — الاعتمادُ قيدٌ فيها ثمّ شراءٌ أو تحصيلُ مستحقّات
    await enable_features(session_factory, "wallet_enabled")
    if flag:
        await enable_features(session_factory, "nowpay_card_enabled")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="nowpay_card",
            name="الدفع بالبطاقة المصرفية", integration="nowpay", enabled=True, for_topup=True, for_subscription=True,
            fee_bearer="taxo", sort_order=0, max_amount=Decimal("100.000"),
        )
        session.add(method)
        await session.commit()
        return method.id


def _ipn(payment_id: str, status: str = "finished", *, secret: str = IPN_VALUE) -> tuple[bytes, dict[str, str]]:
    """**الإشعارُ كما يوقّعه NOWPayments** — HMAC-SHA512 لجسمٍ مرتّب المفاتيح بلا مسافات."""
    payload = {"payment_id": int(payment_id), "payment_status": status, "price_amount": 14.11, "price_currency": "usd"}
    text = json.dumps(dict(sorted(payload.items())), separators=(",", ":"))
    sig = hmac.new(secret.encode(), text.encode(), hashlib.sha512).hexdigest()
    return text.encode(), {"x-nowpayments-sig": sig, "content-type": "application/json"}


async def _deliver(client: AsyncClient, payment_id: str, status: str = "finished") -> dict:
    body, headers = _ipn(payment_id, status)
    response = await client.post("/payment-requests/webhook/nowpay", content=body, headers=headers)
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


# ------------------------------------------------------------------ «finished» وحدَه يحرّك المال، ومكرَّرُه قيدٌ واحد


async def test_finished_activates_the_subscription_once_and_a_duplicate_webhook_changes_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory, country="JO", name="خطةُ بطاقةٍ أردنيّة", price="10")

    listed = (await client.get("/payment-requests/methods", params={"purpose": "subscription"}, headers=captain["headers"])).json()
    card = next(row for row in listed["methods"] if row["code"] == "nowpay_card")
    # **ما يُقال قبل الدفع** يصل كما هو: عملةُ الخصم وسعرُها والشريكُ ورسمُه
    assert card["charge_currency"] == "USD" and Decimal(card["charge_rate"]) == Decimal("1.4104")
    assert card["partner"] == "Guardarian" and card["partner_fee"] == "1.5% + 2 USD"

    opened = await _open(client, captain["headers"], method_id, purpose="subscription", amount="1", plan_id=str(plan_id))
    assert opened.status_code == 201, opened.text
    request_id = opened.json()["request"]["id"]
    assert opened.json()["checkout_url"] == "https://partner.example/checkout/5001"
    # **ثمنُ الخطة من الخادم لا من التطبيق**، والبطاقةُ بالدولار مقرَّباً للأعلى إلى السنت (١٠ × ١٫٤١٠٤ = ١٤٫١٠٤ ⇐ ١٤٫١١)
    assert opened.json()["request"]["amount"] == "10.000"
    assert fake.created[0]["price_amount"] == 14.11 and fake.created[0]["pay_currency"] == "usd"
    assert fake.created[0]["order_id"] and "ipn_callback_url" in fake.created[0]
    assert fake.headers[0].get("origin-ip")

    # **ما دام لم يكتمل** — إشعارٌ بحالٍ وسيطة لا يحرّك شيئاً
    fake.status["5001"] = "confirming"
    assert (await _deliver(client, "5001", "confirming"))["applied"] == 0
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0

    fake.status["5001"] = "finished"
    fake.outcome["5001"] = ("13.9", "usdttrc20")
    assert (await _deliver(client, "5001"))["applied"] == 1
    assert (await _deliver(client, "5001"))["applied"] == 0
    row = await _row(session_factory, request_id)
    assert row.status.value == "approved" and row.subscription_id is not None
    assert await _entries(session_factory, request_id) == 1
    # **ما وصل حسابَ المالك** يُكتب للّوحة
    assert row.gateway_message == "13.9 USDTTRC20"


async def test_a_forged_signature_is_refused_and_moves_nothing(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]
    fake.status["5001"] = "finished"

    body, _ = _ipn("5001", secret="not-the-secret")
    forged = await client.post(
        "/payment-requests/webhook/nowpay", content=body,
        headers={"x-nowpayments-sig": "0" * 128, "content-type": "application/json"},
    )
    assert forged.status_code == 401
    assert (await _row(session_factory, request_id)).status.value == "pending"
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ الجزئيُّ والفاشلُ والمنتهي — بلا مالٍ وبسببٍ مكتوب


@pytest.mark.parametrize(
    ("status", "outcome", "reason"),
    [
        ("partially_paid", "rejected", payment_reasons.CARD_PARTIAL),
        ("failed", "rejected", payment_reasons.GATEWAY_FAILED),
        ("refunded", "rejected", payment_reasons.CARD_REFUNDED),
    ],
)
async def test_partial_failed_and_refunded_close_without_money_and_say_why(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, status: str, outcome: str, reason: str
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.status["5001"] = status
    fake.outcome["5001"] = ("4.2", "usdttrc20") if status == "partially_paid" else ("", "")
    await _deliver(client, "5001", status)
    row = await _row(session_factory, request_id)
    assert row.status.value == outcome
    assert row.rejection_reason == reason
    assert await _entries(session_factory, request_id) == 0
    if status == "partially_paid":
        # **ما وصل من الجزئيّ يُكتب** — فيراه المالكُ ويكمله الدعمُ أو يردّه
        assert row.gateway_message == "4.2 USDTTRC20"


async def test_an_expired_payment_is_cancelled_by_the_sweep_without_any_webhook(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**NOWPayments لا يرسل إشعاراً بعد الانتهاء** (وثائقه) — فالتسويةُ الدوريّةُ تسأله وتغلق الطلبَ بسببه."""
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.status["5001"] = "expired"
    async with session_factory() as session:
        await payment_requests.reconcile_gateway(session, now=datetime.now(UTC) + timedelta(minutes=5))
    row = await _row(session_factory, request_id)
    assert row.status.value == "cancelled"
    assert row.cancel_reason == payment_reasons.GATEWAY_EXPIRED
    assert await _entries(session_factory, request_id) == 0


# ------------------------------------------------------------------ إشعارٌ فائت


async def test_a_missed_webhook_is_settled_once_by_the_fallback_check(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]

    fake.status["5001"] = "finished"
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
    # **والإشعارُ إن وصل متأخّراً لا يقيِّد ثانية**
    assert (await _deliver(client, "5001"))["applied"] == 0
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ المستحقّات


async def test_paying_dues_by_card_clears_them_and_lifts_the_block(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
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
    fake.status["5001"] = "finished"
    assert (await _deliver(client, "5001"))["applied"] == 1

    async with session_factory() as session:
        debt = await session.scalar(select(DriverDebt).where(DriverDebt.driver_id == captain["driver_id"]))
        driver = await session.get(Driver, captain["driver_id"])
        assert debt.status is DriverDebtStatus.SETTLED and driver.debt_blocked is False
    assert await _entries(session_factory, request_id) == 1


# ------------------------------------------------------------------ متى تُعرض ولمن


async def test_hidden_without_keys_and_shown_only_to_drivers(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    method_id = await _jordan_card(session_factory, contract=False)
    captain = await approved_driver(client, session_factory)
    listed = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    # **لا طريقةَ تُعرض** — ونظامُ الدفع العامُّ مطفأ، فالجوابُ «غيرُ متاح» كما كان قبل البطاقة
    assert listed.status_code == 403, listed.text
    assert (await _open(client, captain["headers"], method_id)).status_code in (409, 503)

    # **والمفتاحان يُدخلان** ⇐ تظهر للكبتن، **ولا تظهر للراكب ولا يفتحها**
    await _enable_provider(session_factory, "nowpay", {"api_key": API_VALUE, "ipn_secret": IPN_VALUE}, country="JO")
    shown = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    assert [row["code"] for row in shown["methods"]] == ["nowpay_card"]
    rider = await rider_session(client, RIDER)
    hidden = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=rider["headers"])
    assert hidden.status_code == 403, hidden.text
    assert (await _open(client, rider["headers"], method_id)).status_code == 422


async def test_the_switch_off_hides_it_and_the_general_system_stays_off(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**كليكُ والطرقُ القائمةُ لا تتغيّر**: نظامُ الدفع العامُّ يبقى مطفأً في الأردن، ومفتاحُ البطاقة يفتح طريقتَها وحدَها."""
    _install(monkeypatch)
    method_id = await _jordan_card(session_factory, flag=False)
    async with session_factory() as session:
        session.add(PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.CASH, code="office", name="كاش المكتب",
            enabled=True, fee_bearer="taxo",
        ))
        await session.commit()
    captain = await approved_driver(client, session_factory)
    off = await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])
    assert off.status_code == 403
    assert (await _open(client, captain["headers"], method_id)).status_code == 403

    await enable_features(session_factory, "nowpay_card_enabled")
    on = (await client.get("/payment-requests/methods", params={"purpose": "wallet_topup"}, headers=captain["headers"])).json()
    # **طريقةُ النظام العامّ لا تُعرض** — مفتاحُه هو مطفأ
    assert [row["code"] for row in on["methods"]] == ["nowpay_card"]


async def test_algeria_and_libya_are_locked_in_the_server() -> None:
    assert payment_gateways.switch_allowed("nowpay_card_enabled", CountryCode.JO)
    for country in (CountryCode.DZ, CountryCode.LY):
        assert not payment_gateways.switch_allowed("nowpay_card_enabled", country)


async def test_the_panel_cannot_switch_it_on_outside_jordan(client: AsyncClient, admin_headers: dict) -> None:
    for country in ("DZ", "LY"):
        refused = await client.put(
            "/admin/settings/feature-flags",
            json={"country_code": country, "feature_key": "nowpay_card_enabled", "enabled": True},
            headers=admin_headers,
        )
        assert refused.status_code == 422, refused.text
    allowed = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "nowpay_card_enabled", "enabled": True},
        headers=admin_headers,
    )
    assert allowed.status_code == 200, allowed.text


async def test_the_daily_cap_refuses_the_payment_that_would_cross_it(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory, daily_cap="15")
    captain = await approved_driver(client, session_factory)
    assert (await _open(client, captain["headers"], method_id, amount="10")).status_code == 201
    fake.status["5001"] = "finished"
    await _deliver(client, "5001")
    over = await _open(client, captain["headers"], method_id, amount="6")
    assert over.status_code == 422 and "حدَّه اليوميّ" in over.json()["message"]
    assert (await _open(client, captain["headers"], method_id, amount="5")).status_code == 201


async def test_the_max_per_payment_is_enforced(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    too_much = await _open(client, captain["headers"], method_id, amount="150")
    assert too_much.status_code == 422 and too_much.json()["field"] == "amount"


# ------------------------------------------------------------------ اللوحة


async def test_the_panel_overview_lists_payments_and_saves_limits(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch, admin_headers: dict
) -> None:
    fake = _install(monkeypatch)
    method_id = await _jordan_card(session_factory)
    captain = await approved_driver(client, session_factory)
    request_id = (await _open(client, captain["headers"], method_id)).json()["request"]["id"]
    fake.status["5001"] = "finished"
    fake.outcome["5001"] = ("13.9", "usdttrc20")
    await _deliver(client, "5001")

    overview = await client.get("/admin/card-pay", headers=admin_headers)
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["ready"] is True and body["keys_entered"] is True
    assert {(c["country_code"], c["locked"]) for c in body["countries"]} == {("JO", False), ("DZ", True), ("LY", True)}
    assert body["requests"][0]["external_id"] == "5001" and body["requests"][0]["gateway_message"] == "13.9 USDTTRC20"
    assert Decimal(body["today_total"]) == Decimal("10")
    # **ولا قيمةَ سرٍّ في الجواب**
    assert API_VALUE not in overview.text and IPN_VALUE not in overview.text

    live = await client.get(f"/admin/card-pay/payments/{request_id}/live", headers=admin_headers)
    assert live.status_code == 200 and live.json()["received"] == "13.9 USDTTRC20"

    saved = await client.put(
        "/admin/card-pay/limits",
        json={"min_amount": "2", "max_amount": "50", "daily_cap": "300", "usd_per_jod": "1.41"},
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["method"]["max_amount"] == "50.000" and Decimal(saved.json()["daily_cap"]) == Decimal("300")
    assert Decimal(saved.json()["usd_per_jod"]) == Decimal("1.41")
    inverted = await client.put(
        "/admin/card-pay/limits",
        json={"min_amount": "60", "max_amount": "50", "daily_cap": None, "usd_per_jod": None},
        headers=admin_headers,
    )
    assert inverted.status_code == 422


async def test_limits_without_keys_save_the_bounds_but_not_the_contract_fields(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _jordan_card(session_factory, contract=False)
    bounds = await client.put(
        "/admin/card-pay/limits",
        json={"min_amount": "1", "max_amount": "40", "daily_cap": None, "usd_per_jod": None},
        headers=admin_headers,
    )
    assert bounds.status_code == 200, bounds.text
    assert bounds.json()["ready"] is False
    cap = await client.put(
        "/admin/card-pay/limits",
        json={"min_amount": "1", "max_amount": "40", "daily_cap": "300", "usd_per_jod": None},
        headers=admin_headers,
    )
    assert cap.status_code == 422


async def test_settings_service_refuses_the_flag_outside_jordan(session_factory) -> None:
    from app.core.exceptions import InvalidInput

    async with session_factory() as session:
        with pytest.raises(InvalidInput):
            await settings_service.set_flag(session, country_code=CountryCode.DZ, feature_key="nowpay_card_enabled", enabled=True)
