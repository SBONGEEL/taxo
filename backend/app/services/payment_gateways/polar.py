"""**Polar — اشتراكُ الكبتن الشهريّ بالبطاقة في الأردن** (أمرُ المالك ٢٠٢٦-١١-١٤: «Build the Polar integration … ship it OFF»).

**ما يجري**: منتجٌ واحدٌ عند Polar — «TAXO Driver — Monthly Subscription» (اشتراكٌ متكرّرٌ شهريّاً، خاصٌّ لا يُشترى إلا من رابط دفع) —
نفتح له «جلسةَ دفع» (checkout) لكلِّ طلبٍ عندنا، فيدفع الكبتنُ ببطاقته في صفحة Polar المستضافة. **ولا تمرّ بيانات البطاقة بخوادمنا**،
**ولا أصلَ رقميَّ في الطريق**، وPolar هو البائعُ المسجَّل (Merchant of Record) والمالُ يصل حسابَه ثمّ حسابَ المالك البنكيّ عبر Stripe.

**ما أُخذ من وثائقه المنشورة** (`polar.sh/docs`):
- الأساسُ `https://api.polar.sh/v1` (والتجربة `https://sandbox-api.polar.sh/v1` بحسابٍ ومفاتيحَ منفصلة)، والمصادقةُ `Authorization: Bearer`
  برمز منظّمة (Organization Access Token).
- `POST /checkouts/` بـ`products` و`metadata` و`success_url` و`allow_discount_codes` — ويعود بـ`id` و`url`.
- `GET /checkouts/{id}` — حالُها: open · expired · confirmed · succeeded · failed.
- `GET /orders/` بـ`checkout_id` — والطلبيّةُ تحمل `status` (pending · paid · refunded · partially_refunded) و`net_amount` و`discount_amount`
  و`currency` و`product_id` و`billing_reason` و`checkout_id` و`subscription_id`. **والمبالغُ بالسنت.**
- **الإشعار**: مواصفةُ Standard Webhooks — `webhook-id` و`webhook-timestamp` و`webhook-signature` (`v1,<base64>`)، والسرُّ يبدأ بـ`whsec_`.

**والحقيقةُ جوابُ `check`** لا حمولةُ الإشعار (قاعدةُ `payment_gateways`): الإشعارُ الموقَّعُ يعيد معرّفَ جلسة الدفع وحدَه، ثمّ يُسأل Polar.

**والمبلغ — بالدولار، فPolar لا يقبل الدينار** (قائمةُ عملاته في لوحته بلا JOD، قُرئت ٢٠٢٦-١١-١٤): سعرُ المنتج عنده **84.63 دولاراً** =
سعرُ الخطّة الشهريّة في اللوحة (60.000 دينار) × ربطُ الدينار 1.4104، مقرَّباً للأعلى إلى السنت. **ولا يُفتح دفعٌ بمبلغٍ آخر**: سعرُ المنتج
يُقرأ من Polar عند كلِّ فتح، ومبلغُ طلبنا بالربط يجب أن يساويه سنتاً بسنت — وإلا رُدّ الطلب (خصمٌ على الخطّة، أو تبدّل السعرُ في اللوحة
ولم يُحدَّث المنتج). **ولا رموزَ خصم** (`allow_discount_codes = false`)، **وطلبيّةٌ فيها خصمٌ أو بغير السعر لا تُعتمد**.

**والتجديدُ الشهريّ الآليّ لا يُقيَّد آليّاً هنا** — طلبيّةُ التجديد (`billing_reason = subscription_cycle`) لا جلسةَ دفعٍ لها عندنا ولا طلب،
فتُسجَّل وتُشعِر المالكَ ولا تحرّك مالاً. **وهذا شرطٌ قبل الإشعال** مكتوبٌ في `HANDOFF.md`: يُقرَّر بناءُ تجديدٍ آليٍّ أو إيقافُ التجديد عند Polar.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from collections.abc import Mapping
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

logger = logging.getLogger(__name__)

LIVE_BASE = "https://api.polar.sh/v1"
SANDBOX_BASE = "https://sandbox-api.polar.sh/v1"

#: **ربطُ الدينار بالدولار** (البنك المركزيّ الأردنيّ: 0.709 دينار للدولار منذ ١٩٩٥) — افتراضٌ يُبدَّل من العقد
DEFAULT_USD_PER_JOD = Decimal("1.4104")
CHARGE_CURRENCY = "usd"
PARTNER_NAME = "Polar"
#: **مهلةُ الإشعار** (Standard Webhooks: خمسُ دقائق) — إشعارٌ أقدمُ منها يُرفض ولو صحّ توقيعُه (إعادةُ بثٍّ قديم)
WEBHOOK_TOLERANCE_SECONDS = 300
_CENT = Decimal("0.01")

#: **ما يعني أنّ المالَ رُدّ بعد الدفع** — «دُفع» لا يُعتمد معه
_REVERSED = frozenset({"refunded", "partially_refunded"})
#: **جلسةُ دفعٍ أُكّدت ولم تكتمل بعد** — البنكُ يعالج: «قيد المعالجة» لا «لم يُدفع»
_PROCESSING = frozenset({"confirmed"})
#: **أحداثُ الطلبيّة التي تحمل جلسةَ الدفع** — وأحداثُ الاشتراك تحملها أيضاً حين تكون
_RENEWAL = "subscription_cycle"


def charge_amount(amount: Decimal, usd_per_jod: Decimal) -> Decimal:
    """**ما يُخصم بالدولار لمبلغٍ بالدينار** — بالربط، ومقرَّباً للأعلى إلى السنت. **والحسابُ هنا وحدَه** (§14)."""
    return (amount * usd_per_jod).quantize(_CENT, rounding=ROUND_UP)


def to_cents(amount: Decimal) -> int:
    return int((amount / _CENT).to_integral_value())


class PolarGateway:
    name = "polar"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق** — وإن فات، فالتسويةُ الدوريّة تقيِّده من جواب Polar المباشر بعد مهلته
    confirms_by_webhook = True
    drivers_only = True
    #: **ما يُقال للكبتن قبل الدفع** — اسمُ معالج البطاقة، **ورسمُه على TAXO** (فلا نصَّ رسمٍ على الدافع)
    partner_name = PARTNER_NAME
    partner_fee = None
    partner_kyc = False
    settles_digital = False
    card_currency = "USD"

    def __init__(
        self,
        *,
        api_key: str,
        webhook_secret: str,
        product_id: str,
        sandbox: bool,
        usd_per_jod: Decimal = DEFAULT_USD_PER_JOD,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self._key = api_key
        self._webhook_secret = webhook_secret
        self.product_id = product_id
        self.base_url = SANDBOX_BASE if sandbox else LIVE_BASE
        self.test_mode = sandbox
        #: **ما يُقال للدافع**: الخصمُ بالدولار بهذا السعر
        self.usd_per_jod = usd_per_jod
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        self.last_status: str | None = None
        self.last_received: str | None = None

    # ------------------------------------------------------------------ الشبكة

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        params: Mapping[str, Any] | None = None,
        timeout: float = base.REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._key}"}
        try:
            async with base.http_client(timeout) as http:
                response = await http.request(
                    method, f"{self.base_url}{path}", json=payload, params=dict(params or {}), headers=headers
                )
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Polar") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = None
            if isinstance(body, dict):
                detail = body.get("detail")
                message = detail if isinstance(detail, str) else body.get("error")
            raise base.GatewayError(f"Polar: {message}" if isinstance(message, str) and message else "رفض Polar الطلب")
        return body

    async def _product_price_cents(self, *, timeout: float = base.REQUEST_TIMEOUT_SECONDS) -> int:
        """**سعرُ المنتج كما هو عند Polar الآن** — ثابتٌ بالدولار؛ ومنتجٌ مؤرشفٌ أو بسعرٍ غيرِ ثابتٍ أو بغير الدولار لا يُدفع له."""
        body = await self._request("GET", f"/products/{self.product_id}", timeout=timeout)
        if body.get("is_archived"):
            raise base.GatewayError("منتجُ Polar مؤرشف")
        for price in body.get("prices") or []:
            if not isinstance(price, dict) or price.get("is_archived"):
                continue
            if price.get("amount_type") not in (None, "fixed"):
                continue
            if str(price.get("price_currency") or "").lower() != CHARGE_CURRENCY:
                continue
            amount = price.get("price_amount")
            if isinstance(amount, int) and amount > 0:
                return amount
        raise base.GatewayError("منتجُ Polar بلا سعرٍ ثابتٍ بالدولار")

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — المنتجُ نفسُه بمهلةٍ قصيرة."""
        await self._product_price_cents(timeout=base.HEALTH_TIMEOUT_SECONDS)

    # ------------------------------------------------------------------ الدفعة

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
        # **المبلغُ سعرُ المنتج سنتاً بسنت أو لا دفع** — فلا يُخصم من بطاقة الكبتن غيرُ ما في طلبه
        price = await self._product_price_cents()
        if to_cents(charge_amount(amount, self.usd_per_jod)) != price:
            raise base.GatewayError("هذا المبلغُ لا يُدفع ببطاقة Polar — الاشتراكُ الشهريُّ بسعره وحدَه")
        # **عنوانُ الإشعار يُضبط في لوحة Polar مرّةً** — ولا اسمَ ولا هاتفَ للدافع: مرجعُ طلبنا وحدَه
        payload: dict[str, Any] = {
            "products": [self.product_id],
            "success_url": return_url,
            "allow_discount_codes": False,
            "metadata": {"order_ref": customer.order_ref or "", "source": "taxo"},
        }
        if customer.email:
            payload["customer_email"] = customer.email
        body = await self._request("POST", "/checkouts/", payload)
        checkout_id = str(body.get("id") or "")
        url = body.get("url")
        if not checkout_id or not isinstance(url, str) or not url.startswith("https://"):
            raise base.GatewayError("جوابُ Polar بلا معرّف دفعٍ أو رابطِ صفحة")
        return base.Checkout(external_id=checkout_id, checkout_url=url)

    async def _orders_of(self, checkout_id: str) -> list[dict[str, Any]]:
        body = await self._request("GET", "/orders/", params={"checkout_id": checkout_id, "limit": 10})
        rows = body.get("items")
        if not isinstance(rows, list):
            raise base.GatewayError("جوابُ Polar بلا قائمة طلبيّات")
        # **يُطابَق المعرّفُ هنا أيضاً** — فمرشّحٌ يتجاهله الخادمُ لا يُلحق طلبيّةَ غيرنا بطلبنا
        return [row for row in rows if isinstance(row, dict) and row.get("checkout_id") == checkout_id]

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        self.last_status = None
        self.last_received = None
        checkout = await self._request("GET", f"/checkouts/{external_id}")
        status = str(checkout.get("status") or "").lower()
        if status in _PROCESSING:
            self.last_status = "processing"
            return None
        if status != "succeeded":
            # open · expired · failed — لم يُدفع؛ **ولا يُرفض الطلب**: الكبتنُ قد يعيد في الصفحة نفسِها، والمهلةُ تغلقه
            return None
        orders = await self._orders_of(external_id)
        if not orders:
            # **نجحت الجلسةُ ولم تظهر الطلبيّةُ بعد** — قيد المعالجة، والإشعارُ أو التسويةُ تحسمها
            self.last_status = "processing"
            return None
        price = await self._product_price_cents()
        for row in orders:
            order_status = str(row.get("status") or "").lower()
            received = _money(row)
            self.last_received = received
            code = order_status[:32] or None
            if order_status in _REVERSED or int(row.get("refunded_amount") or 0) > 0:
                return base.GatewayEvent(
                    external_id, PaymentRequestStatus.REJECTED, reason=reasons.CARD_REFUNDED, gateway_code=code,
                    gateway_message=received,
                )
            if order_status != "paid" and row.get("paid") is not True:
                self.last_status = "processing"
                continue
            if not _matches(row, self.product_id, price):
                # **طلبيّةٌ لغير منتجنا أو بغير سعره أو بخصمٍ لا تُعتمد** — تبقى معلّقةً ويحسمها المالكُ من اللوحة
                return None
            # **بالدولار لا يُقارَن بمبلغ الطلب** (عملةٌ غيرُ عملته) — والمطابقةُ بالسعر أعلاه هي الحارس
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, gateway_code=code, gateway_message=received)
        return None

    async def details(self, external_id: str) -> dict[str, Any]:
        """**ما يقوله Polar عن طلبيّات جلسة دفع** — للّوحة؛ ولا يُكتب منه شيء."""
        orders = await self._orders_of(external_id)
        return {
            "orders": [
                {"id": row.get("id"), "status": row.get("status"), "billing_reason": row.get("billing_reason"), "total": _money(row)}
                for row in orders
            ]
        }

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        lowered = {key.lower(): value for key, value in headers.items()}
        msg_id = (lowered.get("webhook-id") or "").strip()
        stamp = (lowered.get("webhook-timestamp") or "").strip()
        signatures = (lowered.get("webhook-signature") or "").strip()
        if not msg_id or not stamp or not signatures or not self._webhook_secret:
            raise base.WebhookSignatureInvalid()
        try:
            sent_at = int(stamp)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        if abs(time.time() - sent_at) > WEBHOOK_TOLERANCE_SECONDS:
            raise base.WebhookSignatureInvalid()
        signed = f"{msg_id}.{stamp}.".encode() + body
        expected = [
            base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode() for key in self._secret_keys()
        ]
        offered = [part.split(",", 1)[1] for part in signatures.split() if part.startswith("v1,") and "," in part]
        if not any(hmac.compare_digest(sig, exp) for sig in offered for exp in expected):
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return []
        checkout_id = data.get("checkout_id")
        if isinstance(checkout_id, str) and checkout_id:
            return [checkout_id]
        if str(payload.get("type") or "").startswith("order.") and data.get("billing_reason") == _RENEWAL:
            # **تجديدٌ شهريٌّ لا طلبَ له عندنا** — لا يُقيَّد آليّاً؛ يُسجَّل ليراه المالك (شرطٌ قبل الإشعال)
            logger.error(
                "Polar: طلبيّةُ تجديدٍ شهريّ بلا طلبٍ عندنا — لم تُقيَّد (order=%s, subscription=%s)",
                data.get("id"), data.get("subscription_id"),
            )
        return []

    def _secret_keys(self) -> list[bytes]:
        """**مفتاحُ HMAC من السرّ** — Polar يوقّع بالسرّ كاملاً بايتاتٍ (`whsec_…` كما أُعطي)؛ **وصيغةُ Standard Webhooks** (ما بعد
        `whsec_` مفكوكاً) تُجرَّب أيضاً. **وكلاهما السرُّ نفسُه** — فلا يُقبل إلا بتوقيعه."""
        secret = self._webhook_secret
        keys = [secret.encode()]
        if secret.startswith("whsec_"):
            try:
                keys.append(base64.b64decode(secret[len("whsec_") :], validate=True))
            except (binascii.Error, ValueError):
                pass
        return keys

    async def test_connection(self) -> str:
        price = await self._product_price_cents()
        mode = "تجربة (sandbox)" if self.test_mode else "حيّ"
        return f"الاتصالُ بـPolar يعمل — الوضع: {mode} · سعرُ المنتج: {Decimal(price) / 100} USD"


# ------------------------------------------------------------------ مساعدات


def _money(row: Mapping[str, Any]) -> str | None:
    total = row.get("total_amount")
    if not isinstance(total, int):
        return None
    return f"{Decimal(total) / 100} {str(row.get('currency') or '').upper()}".strip()


def _matches(row: Mapping[str, Any], product_id: str, price_cents: int) -> bool:
    """**الطلبيّةُ لمنتجنا وبسعره وبالدولار وبلا خصم** — `net_amount` قبل الضريبة (يضيفها Polar على الدافع حيث تجب)."""
    product = row.get("product_id") or (row.get("product") or {}).get("id")
    currency = str(row.get("currency") or "").lower()
    discount = int(row.get("discount_amount") or 0)
    net = row.get("net_amount")
    return product == product_id and currency == CHARGE_CURRENCY and discount == 0 and net == price_cents


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def build_polar(values: Mapping[str, Any]) -> PolarGateway:
    key = str(values.get("api_key") or "").strip()
    secret = str(values.get("webhook_secret") or "").strip()
    product = str(values.get("product_id") or "").strip()
    if not key or not secret or not product:
        # **حتى يُدخل المالكُ المفاتيحَ الثلاثة تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return PolarGateway(
        api_key=key,
        webhook_secret=secret,
        product_id=product,
        sandbox=credentials_service.is_on(values, "sandbox"),
        usd_per_jod=_decimal(values.get("usd_per_jod")) or DEFAULT_USD_PER_JOD,
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
    )
