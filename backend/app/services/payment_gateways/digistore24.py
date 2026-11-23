"""**Digistore24 — اشتراكُ الكبتن بالبطاقة في الأردن** (أمرا المالك ٢٠٢٦-١١-٢٣، `design/OWNER-2026-11-23-DIGISTORE24-LIVE.md`).

**ما يجري**: ثلاثةُ منتجاتٍ عند Digistore24 بدفعةٍ واحدةٍ لا تتجدّد — واحدٌ لكلِّ مبلغٍ يدفعه الكبتنُ الآن (3 · 17 · 45 د.أ) بقيمته
بالدولار (**Digistore24 لا يقبل الدينار**) — وصفحةُ الطلب صفحتُهم المستضافة: **لا تمرّ بياناتُ البطاقة بخوادمنا**، وDigistore24 هو
البائعُ المسجَّل والمالُ يصل حسابَه ثمّ حسابَ المالك. **ورسمُه على TAXO** (قرارُ المالك): البطاقةُ تُخصم قيمةَ المنتج وحدَها.

**حارسُ السعر (قرارُ المالك)**: لا يُفتح دفعٌ إلا لمبلغٍ مربوطٍ بمنتج — ما يدفعه هذا الكبتنُ الآن بعد العروض يساوي 3 أو 17 أو 45 بالضبط؛
**فانتهاءُ عرض «TAXO MAN 45» يُخفي الشهريَّ آليّاً** بدل أن يُخصم 63.50$ عن 60 د.أ، والجديدُ ذو الأسبوع المجّانيّ لا يُفتح له 24$.

**ورابطُ الصفحة لا نداءَ API لفتحه**: `https://www.digistore24.com/product/<id>?custom=<طلبنا>` — و`custom` يعود في الإشعار وفي صفحة الشكر.

**الإشعار (IPN)** — من مثالهم الرسميّ `ipn_receiver.php`: `POST` حقولُ نموذج، والجوابُ نصُّ `OK` (يُكتب في الموجّه)، والتوقيعُ `sha_sign`:
احذف `sha_sign`/`SHASIGN`، رتّب المفاتيحَ نصّيّاً (حسّاساً لحالة الأحرف)، تخطَّ الفارغ، واجمع `"{k}={v}{العبارة}"` متتابعة، ثمّ SHA-512
بحروفٍ كبيرة. **والعبارةُ سرٌّ لا يعرفه إلا Digistore24 ونحن** — فالإشعارُ الموقَّعُ شهادةٌ (`confirms_by_webhook`)، ويُتحقَّق مع ذلك من
المنتج والعملة ووضع التجربة قبل أيِّ قيد.

**وما يحمله الإشعارُ الموقَّعُ يُحفظ في ذاكرة العمليّة دقائقَ** ويُقرأ في `check` في الطلب نفسِه (الموجّهُ يتحقّق ثمّ يحسم متزامناً) —
**ورقمُ طلبيّة Digistore24 يُكتب على طلبنا** (`gateway_message`) فيقرؤه المالكُ في اللوحة. وإن فات الإشعارُ (خادمٌ ساقط) أعاده Digistore24
حتى يرى `OK`، **والدفعُ الذي يصل بعد المهلة يُقيَّد** (`settle_from_gateway`).

**والاسترداد** (`on_refund` · `on_chargeback`) يُعكس بقيدَين مقابلَين لا بحذف (`payment_requests.reverse_gateway_refund`).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, quote

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

logger = logging.getLogger(__name__)

API_BASE = "https://www.digistore24.com/api/call"
ORDER_BASE = "https://www.digistore24.com/product"
PARTNER_NAME = "Digistore24"
CHARGE_CURRENCY = "USD"

#: **ما يدفعه الكبتنُ ⇐ (الخطّة، ثمنُ المنتج بالدولار)** — قرارُ المالك ٢٠٢٦-١١-٢٣ حرفاً، ورسمُ Digistore24 على TAXO.
#: **لا يتغيّر هنا إلا بقرارٍ مكتوب**: هذا ربطُ مبلغٍ بمنتج، لا سعرُ اشتراك (الأسعارُ في اللوحة ولم تُمسّ).
PRICE_MAP: dict[Decimal, tuple[str, Decimal]] = {
    Decimal("3.000"): ("daily", Decimal("4.25")),
    Decimal("17.000"): ("weekly", Decimal("24.00")),
    Decimal("45.000"): ("monthly", Decimal("63.50")),
}

#: **أحداثُ الإشعار** كما في مثالهم الرسميّ
EVENT_PAYMENT = "on_payment"
EVENT_REFUND = "on_refund"
EVENT_CHARGEBACK = "on_chargeback"
EVENT_TEST = "connection_test"
_REVERSAL = frozenset({EVENT_REFUND, EVENT_CHARGEBACK})

#: **كم يبقى الإشعارُ الموقَّعُ في الذاكرة** — يكفي الحسمَ المتزامنَ في الطلب نفسِه وإعادةَ الإشعار القريبة
_SEEN_TTL_SECONDS = 15 * 60
_SEEN: dict[str, tuple[float, dict[str, str]]] = {}


def sign(fields: Mapping[str, str], passphrase: str) -> str:
    """**توقيعُ Digistore24** — `digistore_signature()` من مثالهم الرسميّ حرفاً (بلا تكبير المفاتيح ولا فكّ HTML)."""
    parts: list[str] = []
    for key in sorted(k for k in fields if k not in ("sha_sign", "SHASIGN")):
        value = fields[key]
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}{passphrase}")
    return hashlib.sha512("".join(parts).encode("utf-8")).hexdigest().upper()


def parse_form(body: bytes) -> dict[str, str]:
    """**حقولُ النموذج** — آخرُ قيمةٍ لمفتاحٍ مكرَّر كما يقرؤها PHP في `$_POST`."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise base.WebhookSignatureInvalid() from exc
    return dict(parse_qsl(text, keep_blank_values=True))


def remember(custom: str, fields: Mapping[str, str]) -> None:
    now = time.monotonic()
    for key in [k for k, (at, _f) in _SEEN.items() if now - at > _SEEN_TTL_SECONDS]:
        _SEEN.pop(key, None)
    _SEEN[custom] = (now, dict(fields))


def recalled(custom: str) -> dict[str, str] | None:
    hit = _SEEN.get(custom)
    if hit is None or time.monotonic() - hit[0] > _SEEN_TTL_SECONDS:
        return None
    return hit[1]


def product_for(amount: Decimal) -> tuple[str, Decimal] | None:
    """**الخطّةُ والدولار لمبلغٍ بالدينار** — `None` لمبلغٍ غيرِ مربوط (حارسُ السعر)."""
    try:
        return PRICE_MAP.get(Decimal(amount).quantize(Decimal("0.001")))
    except (InvalidOperation, TypeError):
        return None


class Digistore24Gateway:
    name = "digistore24"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق وحدَه** — والعودةُ من الصفحة لا تفعّل شيئاً
    confirms_by_webhook = True
    #: **الاستردادُ بعد الاعتماد يُعكس آليّاً** بقيدَين مقابلَين (`payment_requests.reverse_gateway_refund`)
    reverses_refunds = True
    drivers_only = True
    partner_name = PARTNER_NAME
    partner_fee = None
    partner_kyc = False
    settles_digital = False
    #: **البطاقةُ تُخصم بالدولار** — ولا يُعرض سعرُه في شاشات TAXO (قرارُ المالك: الدينارُ وحدَه وسطرٌ خفيف)
    card_currency = CHARGE_CURRENCY
    usd_per_jod = None

    def __init__(
        self,
        *,
        api_key: str,
        ipn_passphrase: str,
        products: Mapping[str, str],
        test_mode: bool,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self._key = api_key
        self._passphrase = ipn_passphrase
        #: الخطّة ⇐ معرّفُ المنتج عند Digistore24
        self.products = dict(products)
        self.test_mode = test_mode
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: **المبالغُ التي يُفتح لها دفع** — يقرؤها التطبيقُ فيُظهر الزرَّ للخطّة التي يساويها ثمنُها الآن وحدَها
        self.fixed_amounts = tuple(sorted(amount for amount, (plan, _usd) in PRICE_MAP.items() if self.products.get(plan)))
        self.last_status: str | None = None
        self.last_received: str | None = None

    # ------------------------------------------------------------------ الشبكة

    async def _call(self, function: str, params: Mapping[str, Any] | None = None, *,
                    timeout: float = base.REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        headers = {"Accept": "application/json", "X-DS-API-KEY": self._key}
        try:
            async with base.http_client(timeout) as http:
                response = await http.get(f"{API_BASE}/{function}", params=dict(params or {}), headers=headers)
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Digistore24") from exc
        if not isinstance(body, dict) or body.get("result") != "success":
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"Digistore24: {message}" if isinstance(message, str) and message else "رفض Digistore24 الطلب")
        return body

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — `ping` بمفتاح API بمهلةٍ قصيرة."""
        await self._call("ping", timeout=base.HEALTH_TIMEOUT_SECONDS)

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
        mapped = product_for(amount)
        product = self.products.get(mapped[0]) if mapped else None
        if mapped is None or not product:
            # **حارسُ السعر** — مبلغٌ غيرُ مربوطٍ بمنتجٍ لا يُفتح له دفع (عرضٌ انتهى، أو سعرٌ تبدّل في اللوحة)
            raise base.GatewayError("هذا المبلغُ لا يُدفع بالبطاقة الآن — ادفع بطريقةٍ أخرى")
        ref = customer.order_ref or ""
        if not ref:
            raise base.GatewayError("طلبٌ بلا مرجع")
        # **ولا اسمَ ولا هاتفَ للدافع** — مرجعُ طلبنا وحدَه؛ والبريدُ إن وُجد يوفّر عليه كتابتَه
        url = f"{ORDER_BASE}/{quote(product, safe='')}?custom={quote(ref, safe='')}"
        if customer.email:
            url += f"&email={quote(customer.email, safe='')}"
        return base.Checkout(external_id=ref, checkout_url=url)

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        """**ما قاله الإشعارُ الموقَّعُ لهذا الطلب** — بعد التحقّق من منتجه وعملته ووضعه؛ و`None` ما لم يصل إشعار."""
        self.last_status = None
        self.last_received = None
        fields = recalled(external_id)
        if fields is None:
            return None
        event = fields.get("event", "")
        order = (fields.get("order_id") or "")[:40]
        product = fields.get("product_id") or ""
        received = _received(fields)
        self.last_received = received
        note = f"Digistore24 order {order}" + (f" · {received}" if received else "")
        if event in _REVERSAL:
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REFUNDED, reason=reasons.CARD_REFUNDED, gateway_code=event[:32],
                gateway_message=note,
            )
        if event != EVENT_PAYMENT:
            return None
        mode = (fields.get("api_mode") or "").lower()
        if mode and (mode == "test") != self.test_mode:
            # **مالٌ تجريبيٌّ على عقدٍ حيّ أو حيٌّ على عقد تجربة** — لا يُقيَّد ويراه المالكُ في السجلّ
            logger.error("Digistore24: إشعارٌ بوضع %s على عقدٍ %s — لم يُقيَّد (order=%s)", mode,
                         "تجربة" if self.test_mode else "حيّ", order)
            return None
        if product not in self.products.values():
            logger.error("Digistore24: إشعارٌ لمنتجٍ ليس لنا (%s) — لم يُقيَّد (order=%s)", product, order)
            return None
        currency = (fields.get("currency") or CHARGE_CURRENCY).upper()
        if currency != CHARGE_CURRENCY:
            logger.error("Digistore24: إشعارٌ بعملة %s — لم يُقيَّد (order=%s)", currency, order)
            return None
        # **المبلغُ بالدينار الذي يربطه هذا المنتج** — فيقارنه الحسمُ بمبلغ طلبنا (`apply_gateway_outcome`): منتجُ اليوميّ لا يُفعِّل
        # خطّةَ الشهر، ويبقى الطلبُ «قيد المعالجة» بسببه ويراه المالك
        return base.GatewayEvent(
            external_id, PaymentRequestStatus.APPROVED, amount=self.amount_of(product), gateway_code=event[:32],
            gateway_message=note,
        )

    def amount_of(self, product_id: str) -> Decimal | None:
        """**المبلغُ بالدينار المربوطُ بمنتجٍ من منتجاتنا** — `None` لغيرها."""
        for amount, (plan, _usd) in PRICE_MAP.items():
            if self.products.get(plan) == product_id:
                return amount
        return None

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        fields = parse_form(body)
        offered = fields.get("sha_sign") or fields.get("SHASIGN") or ""
        if not offered or not self._passphrase:
            raise base.WebhookSignatureInvalid()
        if not hmac.compare_digest(offered.upper(), sign(fields, self._passphrase)):
            raise base.WebhookSignatureInvalid()
        event = fields.get("event", "")
        if event == EVENT_TEST:
            return []
        custom = (fields.get("custom") or "").strip()
        if not custom:
            logger.error("Digistore24: إشعارٌ موقَّعٌ بلا مرجعٍ منّا (event=%s, order=%s)", event, fields.get("order_id"))
            return []
        remember(custom, fields)
        return [custom]

    async def test_connection(self) -> str:
        await self._call("ping")
        mode = "تجربة" if self.test_mode else "حيّ"
        missing = [plan for plan in ("daily", "weekly", "monthly") if not self.products.get(plan)]
        tail = f" · منتجاتٌ ناقصة: {', '.join(missing)}" if missing else " · المنتجاتُ الثلاثة مضبوطة"
        return f"الاتصالُ بـDigistore24 يعمل — الوضع: {mode}{tail}"


# ------------------------------------------------------------------ مساعدات


def _received(fields: Mapping[str, str]) -> str | None:
    for key in ("amount", "transaction_amount", "amount_brutto"):
        value = (fields.get(key) or "").strip()
        if value:
            return f"{value} {(fields.get('currency') or CHARGE_CURRENCY).upper()}"[:60]
    return None


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def build_digistore24(values: Mapping[str, Any]) -> Digistore24Gateway:
    key = str(values.get("api_key") or "").strip()
    passphrase = str(values.get("ipn_passphrase") or "").strip()
    products = {
        plan: str(values.get(f"product_{plan}") or "").strip() for plan in ("daily", "weekly", "monthly")
    }
    if not key or not passphrase or not any(products.values()):
        # **حتى يُدخل المالكُ المفتاحَ والعبارةَ ومنتجاً واحداً على الأقلّ تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return Digistore24Gateway(
        api_key=key,
        ipn_passphrase=passphrase,
        products={plan: pid for plan, pid in products.items() if pid},
        test_mode=credentials_service.is_on(values, "test_mode"),
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
    )
