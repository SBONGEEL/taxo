"""**Chargily Pay V2** — الذهبية وCIB (SPEC §٧٣-هـ المرحلة ٣)، **بوثائقه المنشورة** في `dev.chargily.com/pay-v2` (قُرئت ٢٠٢٦-١٠-١١).

**ما أُخذ من الوثائق حرفاً**:
- الأساسُ `https://pay.chargily.net/test/api/v2` للاختبار و`https://pay.chargily.net/api/v2` للحيّ، والمصادقةُ `Authorization: Bearer <المفتاح السرّيّ>`.
- `POST /checkouts` بـ`amount` (عددٌ صحيح) و`currency` («dzd» وحدَها مدعومة) و`success_url` (إلزاميّ) و`failure_url` و`webhook_endpoint` و`locale`
  و`chargily_pay_fees_allocation` (`customer` · `merchant` · `split`)؛ ويعود بـ`id` و`checkout_url`.
- `GET /checkouts/{id}` بالحال: `pending` · `processing` · `paid` · `failed` · `canceled`. و`GET /balance` (زرُّ الاختبار).
- **الـwebhook**: ترويسةُ `signature` = `HMAC-SHA256` لجسم الطلب **الخام** بالمفتاح السرّيّ، **ومقارنةٌ ثابتةُ الزمن**؛ والجسمُ `type` و`data`.

**وما لم يُرسل لأنه غيرُ موثَّقٍ بما يكفي**: `metadata` (نوعُه في الوثائق «مصفوفة» بلا شكل) — والطلبُ يُعرف بمعرّف الصفحة نفسِها.

**وما أُضيف ٢٠٢٦-١٠-١٧** (§٧٦-ع/٢، بوثائقه المنشورة — قُرئت اليوم):
- `POST /customers` بـ`name` و`email` و`phone` (لا إلزاميَّ معلَناً)، ويعود بـ`id`؛ **و`customer_id` في `POST /checkouts`** — فلا تسأل الصفحةُ
  الدافعَ بياناتِه كلَّ مرّة. **ولا يُرسل إلا بمفتاحه في العقد** (`send_customer`، مطفأٌ ابتداءً): كانت سياسةُ الخصوصية تقول «لا نرسل إلى
  Chargily اسمَك ولا رقمَ هاتفك» — **فعُدِّلت أوّلاً (النسخةُ ٤ للجزائر) ثمّ أُشعل المفتاحُ على الإنتاج** (§٧٦-ع/٦، ٢٠٢٦-١٠-١٨).
- `locale` من لغة الطلب (`ar` · `fr`؛ والوثائقُ تقبل `en` أيضاً) — كان «ar» ثابتاً.
- `GET /checkouts/{id}` يعيد `checkout_url` — فصفحةٌ معلَّقةٌ تُستأنف بعينها («أكمل الدفع») ولا تُفتح ثانية.
**ولا حدَّ أدنى للمبلغ موثَّق** — فما يرفضه الوسيطُ يُعاد نصُّه للمستخدم ولا يُخترع حدّ.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

TEST_BASE = "https://pay.chargily.net/test/api/v2"
LIVE_BASE = "https://pay.chargily.net/api/v2"

#: **من يحمل الرسوم بلغة TAXO ⇐ بلغة Chargily** (`chargily_pay_fees_allocation`)
FEES_ALLOCATION = {"taxo": "merchant", "user": "customer", "split": "split"}

#: **لغاتُ صفحته كما في وثائقه** — وما سواها عربيّة كما كانت
LOCALES = frozenset({"ar", "fr", "en"})


class ChargilyGateway:
    name = "chargily"
    #: **لا شحنَ ولا اشتراكَ إلا بإشعارٍ موقَّعٍ متحقَّق** (أمرُ المالك §٧٤-ط/٥) — وعودةُ التطبيق تسأل ولا تقيِّد «دُفع»
    confirms_by_webhook = True

    def __init__(self, *, secret_key: str, test_mode: bool, send_customer: bool = False) -> None:
        self._key = secret_key
        self.base_url = TEST_BASE if test_mode else LIVE_BASE
        self.test_mode = test_mode
        #: **عميلُ Chargily باسم الدافع وهاتفه** — بمفتاحه في العقد وحدَه (أعلاه)
        self.send_customer = send_customer
        #: **آخرُ حالٍ قالها `check`** — فإلغاءُ المهلة يقول «لم يكتمل» لصفحةٍ قيد المعالجة لا «لم يُدفع شيء» (§٧٦-ع/٢، المشكلة ١٧)
        self.last_status: str | None = None

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float = base.REQUEST_TIMEOUT_SECONDS
    ) -> dict[str, Any]:
        try:
            async with base.http_client(timeout) as http:
                response = await http.request(
                    method,
                    f"{self.base_url}{path}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            # **مهلةٌ أو انقطاع** — الوسيطُ متوقّفٌ أو بطيءٌ جدّاً، لا رافضٌ لطلبنا (§٨٢-أ/١)
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            # **`502` · `503` · `504` منه** — عطلُه هو، فيُقال للدافع «متوقّفٌ مؤقّتاً» لا نصُّ صفحةِ خطأ
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Chargily") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"Chargily: {message}" if message else "رفض Chargily الطلب")
        return body

    async def health(self) -> None:
        """**فحصٌ سريعٌ قبل فتح الصفحة** (§٨٢-أ/١) — `GET /balance` بمهلةٍ قصيرة؛ يرفع `GatewayDown` إن تعذّر أو أبطأ."""
        await self._request("GET", "/balance", timeout=base.HEALTH_TIMEOUT_SECONDS)

    async def checkout(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        webhook_url: str,
        fee_bearer: str,
        customer: base.CheckoutCustomer,
        locale: str = "ar",
    ) -> base.Checkout:
        # **عددٌ صحيحٌ بالدينار** (الوثائق: `amount` integer) — والطلبُ دينارٌ صحيحٌ أصلاً (§٧٣-ج/٣)
        payload: dict[str, Any] = {
            "amount": int(amount),
            "currency": "dzd",
            "success_url": return_url,
            "failure_url": return_url,
            "webhook_endpoint": webhook_url,
            "description": description[:255],
            "locale": locale if locale in LOCALES else "ar",
            "chargily_pay_fees_allocation": FEES_ALLOCATION[fee_bearer],
        }
        if customer.gateway_id:
            payload["customer_id"] = customer.gateway_id
        body = await self._request("POST", "/checkouts", payload)
        checkout_id, url = body.get("id"), body.get("checkout_url")
        if not isinstance(checkout_id, str) or not isinstance(url, str):
            raise base.GatewayError("جوابُ Chargily بلا معرّفٍ أو رابط")
        return base.Checkout(
            external_id=checkout_id,
            checkout_url=url,
            fee_on_customer=_money(body.get("fees_on_customer")),
            fee_on_merchant=_money(body.get("fees_on_merchant")),
        )

    async def create_customer(self, customer: base.CheckoutCustomer) -> str | None:
        """**عميلٌ في Chargily باسم الدافع وهاتفه** (وبريدِه إن كان) — معرّفُه، أو `None` والمفتاحُ مطفأ. **ولا يُخترع بريد.**"""
        if not self.send_customer:
            return None
        payload: dict[str, Any] = {"name": customer.full_name[:255], "phone": customer.phone}
        if customer.email:
            payload["email"] = customer.email
        body = await self._request("POST", "/customers", payload)
        customer_id = body.get("id")
        if not isinstance(customer_id, str):
            raise base.GatewayError("جوابُ Chargily بلا معرّف عميل")
        return customer_id

    async def resume_url(self, external_id: str) -> str | None:
        """**رابطُ صفحةٍ ما زالت تنتظر الدفع** — بعينها لا صفحةٌ ثانية؛ و`None` لما حُسم أو بدأت معالجتُه."""
        body = await self._request("GET", f"/checkouts/{external_id}")
        url = body.get("checkout_url")
        return url if body.get("status") == "pending" and isinstance(url, str) else None

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        body = await self._request("GET", f"/checkouts/{external_id}")
        status = body.get("status")
        self.last_status = status if isinstance(status, str) else None
        amount = Decimal(str(body["amount"])) if body.get("amount") is not None else None
        fees = {"fee_on_customer": _money(body.get("fees_on_customer")), "fee_on_merchant": _money(body.get("fees_on_merchant"))}
        if status == "paid":
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, amount=amount, **fees)
        if status == "failed":
            return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason=reasons.GATEWAY_FAILED)
        if status == "canceled":
            return base.GatewayEvent(external_id, PaymentRequestStatus.CANCELLED, reason=reasons.GATEWAY_CANCELLED)
        if status == "expired":
            # **لا تسمّيه الوثائق، وصفحةُ وضع التجربة تحمل زرَّه** («Expire» — قُرئت ٢٠٢٦-١٠-١٣) — فيُحسم ملغًى بسببه لا معلَّقاً إلى الأبد
            return base.GatewayEvent(external_id, PaymentRequestStatus.CANCELLED, reason=reasons.GATEWAY_EXPIRED)
        return None  # `pending` · `processing`

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        signature = headers.get("signature") or ""
        expected = hmac.new(self._key.encode(), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not str(payload.get("type", "")).startswith("checkout."):
            return []
        checkout_id = data.get("id")
        return [checkout_id] if isinstance(checkout_id, str) else []

    async def balance(self, currency: str) -> tuple[Decimal, Decimal, Decimal] | None:
        """**ما عند Chargily لـTAXO الآن** (`GET /balance`): الرصيدُ والجاهزُ للتحويل والمعلَّق — بمحفظة العملة، أو `None` بلا محفظتها.
        **والجاهزُ نصٌّ في الوثائق** («40000») والباقيان عددان — فكلٌّ يُقرأ من نصّه."""
        body = await self._request("GET", "/balance")
        for wallet in body.get("wallets") or []:
            if isinstance(wallet, dict) and str(wallet.get("currency", "")).lower() == currency:
                try:
                    return (
                        Decimal(str(wallet.get("balance") or 0)),
                        Decimal(str(wallet.get("ready_for_payout") or 0)),
                        Decimal(str(wallet.get("on_hold") or 0)),
                    )
                except ArithmeticError as exc:
                    raise base.GatewayError("رصيدٌ غيرُ مقروءٍ من Chargily") from exc
        return None

    async def test_connection(self) -> str:
        await self._request("GET", "/balance")
        return f"الاتصالُ بـChargily يعمل — الوضع: {'اختبار' if self.test_mode else 'حيّ'}"


def _money(value: Any) -> Decimal | None:
    """رسومٌ كما يكتبها Chargily (عددٌ أو نصّ) — أو `None` حين لا تُذكر أو لا تُقرأ."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return None


def build_chargily(values: Mapping[str, Any]) -> ChargilyGateway:
    key = str(values.get("secret_key") or "").strip()
    if not key:
        raise base.GatewayUnavailable("لا مفتاحَ سرّيّاً في عقد Chargily")
    return ChargilyGateway(
        secret_key=key,
        test_mode=credentials_service.is_on(values, "test_mode"),
        send_customer=credentials_service.is_on(values, "send_customer"),
    )
