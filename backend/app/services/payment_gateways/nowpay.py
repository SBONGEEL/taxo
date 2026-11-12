"""**NOWPayments — «الدفع بالبطاقة المصرفية» للكبتن في الأردن** (أمرُ المالك ٢٠٢٦-١١-١١، `design/NOWPAY-CARD-JO.md`).

**ما يجري**: الكبتنُ يدفع ببطاقته في صفحة شريك NOWPayments للبطاقات (Guardarian)، والشريكُ يشتري بالمبلغ أصلاً رقميّاً يصل حسابَ
المالك في NOWPayments. **ولا تمرّ بيانات البطاقة بخوادمنا**: نفتح دفعةً بـAPI ونرسل الدافعَ إلى رابط الشريك، ونعرف النتيجةَ من
سؤال NOWPayments مباشرةً بمفتاحنا.

**ما أُخذ من وثائقه المنشورة حرفاً** (مجموعة Postman الرسمية `documenter.getpostman.com/view/7907941/2s93JusNJt`، قُرئت ٢٠٢٦-١١-١١):
- الأساسُ `https://api.nowpayments.io/v1` (والتجربة `https://api-sandbox.nowpayments.io/v1`)، والمصادقةُ ترويسة `x-api-key`.
- `POST /payment` بـ`price_amount` و`price_currency` و`pay_currency` («عملةٌ ورقيّةٌ إن فُعّلت لحسابك»: USD · EUR · ILS · GBP · AUD ·
  RON — **والدينارُ الأردنيُّ ليس منها**) و`ipn_callback_url` و`order_id` و`order_description`؛ **ودفعُ البطاقة يشترط ترويسة
  `origin-ip` بعنوان الدافع**. ويعود بـ`payment_id`، و`redirectData.redirect_url` «رابطُ واجهة شريك البطاقة» في هذا المسار.
- `GET /payment/{payment_id}` بالمفتاح نفسِه — الحالات: `waiting` · `confirming` · `confirmed` · `sending` · `partially_paid` ·
  `finished` · `failed` · `refunded` · `expired`. و`outcome_amount`/`outcome_currency` ما يصل محفظةَ المالك.
- **الإشعار (IPN)**: ترويسة `x-nowpayments-sig` = `HMAC-SHA512` بالسرّ الخاصّ بالإشعارات **لجسمٍ مرتّب المفاتيح** (مثالُهم
  `JSON.stringify(sortObject(params))`). **و«لا إشعارَ بعد أن تنتهي صلاحيّة الدفعة»** — فالفحصُ الدوريُّ هو ما يحسم الانتهاء.
- `GET /status` بلا مفتاح (الصحّة)، و`GET /merchant/coins` بالمفتاح (العملاتُ المفعّلة — منه يُعرف أنّ دفعَ البطاقة مفعَّل).

**والمبلغ**: الطلبُ بالدينار، والشريكُ يخصم بالدولار — **فالسعرُ يُحوَّل بربط الدينار الرسميّ** (1 JOD = 1.4104 USD، والقيمةُ في العقد
تُضبط من صفحة العقود) **ويُقرَّب للأعلى** إلى السنت.

**ورسمُ الشريك تتحمّله TAXO** (قرارُ المالك ٢٠٢٦-١١-١١، حين `fee_bearer = taxo` على صفّ الطريقة): الشريكُ يضيف رسمَه فوق سعر
الفاتورة، **فتُخفَّض الفاتورةُ حتى تُخصم البطاقةُ المستحقَّ بالدولار وحدَه**، ويُقيَّد للكبتن المستحقُّ كاملاً، ويصل TAXO أقلّ —
والفرقُ يُكتب رسماً على TAXO في `fee_amount` بالدينار (المسارُ القائمُ لكلِّ وسيط). **وأنّ الرسمَ يُضاف فوق الفاتورة منقولٌ عن
NOWPayments لا مقيس** — أوّلُ تجربةٍ للمالك تقيسه (`breakdown`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import ROUND_DOWN, ROUND_UP, Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.currency import step_of
from app.models.enums import Currency, PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

LIVE_BASE = "https://api.nowpayments.io/v1"
SANDBOX_BASE = "https://api-sandbox.nowpayments.io/v1"

#: **ربطُ الدينار بالدولار** (البنك المركزيّ الأردنيّ: 0.709 دينار للدولار منذ ١٩٩٥) — افتراضٌ يُبدَّل من العقد
DEFAULT_USD_PER_JOD = Decimal("1.4104")
#: **عملةُ الخصم** — أوّلُ ما يقبله الشريكُ من قائمة الوثائق؛ والدينارُ ليس فيها
CHARGE_CURRENCY = "usd"

#: الحالاتُ التي تعني أنّ مالاً وصل الشريكَ ويُعالَج — «قيد المعالجة» لا «لم يُدفع»
_PROCESSING = frozenset({"confirming", "confirmed", "sending"})

#: **رسومُ الشريك على الدافع كما نشرتها NOWPayments** (مدوّنتها: «1.5% + 2 USD») — تُعرض للكبتن قبل الدفع، ولا تُحسب هنا
PARTNER_FEE_TEXT = "1.5% + 2 USD"
PARTNER_NAME = "Guardarian"
#: **رسمُ الشريك رقماً** — المنشورُ نفسُه «1.5% + 2 USD»؛ به تُحسب الفاتورةُ حين تتحمّله TAXO
PARTNER_FEE_RATE = Decimal("0.015")
PARTNER_FEE_FIXED_USD = Decimal("2.00")
_CENT = Decimal("0.01")


def breakdown(amount: Decimal, fee_bearer: str | None, usd_per_jod: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """**(خصمُ البطاقة، سعرُ الفاتورة، رسمُ الشريك) بالدولار لمبلغٍ بالدينار** — الحسابُ الواحدُ للفتح وللوحة.

    **«taxo»**: خصمُ البطاقة = المستحقُّ بالدولار، والفاتورةُ = (الخصم − ٢) ÷ ١٫٠١٥ **مقرَّبةً للأسفل** فلا تُخصم البطاقةُ فوق المستحقّ،
    والرسمُ = الفرق. **وغيرُها**: الفاتورةُ = المستحقّ، والرسمُ فوقها على الدافع — كما بُني أوّلاً.
    """
    due = (amount * usd_per_jod).quantize(_CENT, rounding=ROUND_UP)
    if fee_bearer == "taxo":
        invoice = ((due - PARTNER_FEE_FIXED_USD) / (1 + PARTNER_FEE_RATE)).quantize(_CENT, rounding=ROUND_DOWN)
        if invoice <= 0:
            raise base.GatewayError("المبلغُ أصغرُ من رسم شريك البطاقة — ادفع بكليك")
        return due, invoice, due - invoice
    fee = (due * PARTNER_FEE_RATE + PARTNER_FEE_FIXED_USD).quantize(_CENT, rounding=ROUND_UP)
    return due + fee, due, fee


class NowpayGateway:
    name = "nowpay"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق** — وإن فات، فالتسويةُ الدوريّة تقيِّده من جواب NOWPayments المباشر بعد مهلته
    confirms_by_webhook = True
    #: **للكبتن وحدَه** (أمرُ المالك) — يُسأل في العرض وفي الفتح
    drivers_only = True
    #: **ما يُقال للكبتن قبل الدفع** — اسمُ شريك البطاقة ورسمُه كما نشرتهما NOWPayments
    partner_name = PARTNER_NAME
    partner_fee = PARTNER_FEE_TEXT
    #: **الشريكُ يطلب هويّةَ الدافع أوّلَ مرّة، والمبلغُ يصل أصلاً رقميّاً** — سطرا إفصاحٍ يُقالان للكبتن (لا يقعان مع Whop)
    partner_kyc = True
    settles_digital = True

    def __init__(
        self,
        *,
        api_key: str,
        ipn_secret: str,
        sandbox: bool,
        usd_per_jod: Decimal = DEFAULT_USD_PER_JOD,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self._key = api_key
        self._ipn_secret = ipn_secret
        self.base_url = SANDBOX_BASE if sandbox else LIVE_BASE
        self.test_mode = sandbox
        self.usd_per_jod = usd_per_jod
        #: **سقفُ مجموع اليوم بالدينار** لكلِّ الكباتن معاً — `None` بلا سقف
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: آخرُ حالٍ خامٍّ قالها `check` — «قيد المعالجة» يُقرأ منه عند المهلة، **ولا «pending» أبداً**: صفحةُ البطاقة قد تأخذ دقائق
        #: (تحقّقُ الهويّة ثمّ الشراء)، فعودةُ الكبتن إلى التطبيق لا تُلغي دفعتَه
        self.last_status: str | None = None
        #: آخرُ ما قاله NOWPayments عمّا وصل (`outcome_amount` + `outcome_currency`) — للّوحة وحدَها
        self.last_received: str | None = None

    # ------------------------------------------------------------------ الشبكة

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = base.REQUEST_TIMEOUT_SECONDS,
        auth: bool = True,
    ) -> dict[str, Any]:
        sent = {"Accept": "application/json"}
        if auth:
            sent["x-api-key"] = self._key
        if headers:
            sent.update(headers)
        try:
            async with base.http_client(timeout) as http:
                response = await http.request(method, f"{self.base_url}{path}", json=payload, headers=sent)
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من NOWPayments") from exc
        if response.status_code >= 400 or not isinstance(body, (dict, list)):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"NOWPayments: {message}" if message else "رفض NOWPayments الطلب")
        return body if isinstance(body, dict) else {"data": body}

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — `GET /status` بلا مفتاح ومهلةٍ قصيرة."""
        await self._request("GET", "/status", timeout=base.HEALTH_TIMEOUT_SECONDS, auth=False)

    # ------------------------------------------------------------------ الدفعة

    def charge_amount(self, amount: Decimal) -> Decimal:
        """**ما يُخصم بالدولار لمبلغٍ بالدينار** — بالربط، ومقرَّباً للأعلى إلى السنت."""
        return (amount * self.usd_per_jod).quantize(Decimal("0.01"), rounding=ROUND_UP)

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
        _card, invoice, fee = breakdown(amount, fee_bearer, self.usd_per_jod)
        # **الرسمُ بالدينار** يُكتب على الطلب بمساره القائم (`fee_payer`/`fee_amount`) — على TAXO أو على الدافع بحسب الطريقة
        # **خطوةُ الدينار من بيتها الواحد** (`core/currency.py`، §٧٣-ج/٤) لا حرفيّةٌ هنا — مقرَّبةً للأعلى فلا يُكتب الرسمُ أصغرَ ممّا كان
        fee_jod = (fee / self.usd_per_jod).quantize(step_of(Currency.JOD), rounding=ROUND_UP)
        payload: dict[str, Any] = {
            "price_amount": float(invoice),
            "price_currency": CHARGE_CURRENCY,
            "pay_currency": CHARGE_CURRENCY,
            "ipn_callback_url": webhook_url,
            "order_id": customer.order_ref or "",
            "order_description": description[:120],
            "success_url": return_url,
            "cancel_url": return_url,
        }
        if not payload["order_id"]:
            payload.pop("order_id")
        # **عنوانُ الدافع إلزاميٌّ لدفع البطاقة** (الوثائق: «origin-ip») — ولا يُرسل غيرُه عنه: لا اسمَ ولا هاتف
        headers = {"origin-ip": customer.ip} if customer.ip else None
        body = await self._request("POST", "/payment", payload, headers=headers)
        payment_id = body.get("payment_id")
        url = _redirect_url(body)
        if payment_id in (None, ""):
            raise base.GatewayError("جوابُ NOWPayments بلا معرّف دفعة")
        if url is None:
            # **أوضحُ سببٍ يُرى في أوّل تجربة**: الحسابُ يقبل العملات المشفّرة ولم يُفعَّل فيه دفعُ البطاقة (Fiat on-ramp)
            raise base.GatewayError(
                "لم يُرجع NOWPayments رابطَ صفحة البطاقة — فعّل الدفعَ بالعملة الورقيّة (USD) في حساب NOWPayments"
            )
        on_taxo = fee_bearer == "taxo"
        return base.Checkout(
            external_id=str(payment_id),
            checkout_url=url,
            fee_on_customer=None if on_taxo else fee_jod,
            fee_on_merchant=fee_jod if on_taxo else None,
        )

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        body = await self._request("GET", f"/payment/{external_id}")
        status = str(body.get("payment_status") or "").lower()
        self.last_status = "processing" if status in _PROCESSING else (status or None)
        self.last_received = _received(body)
        code = status[:32] or None
        message = self.last_received
        if status == "finished":
            # **المبلغُ لا يُعاد**: NOWPayments يقول دولاراً والطلبُ بالدينار — و«finished» عنده يعني أنّ السعرَ الذي حدّدناه دُفع كاملاً
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, gateway_code=code, gateway_message=message)
        if status == "partially_paid":
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REJECTED, reason=reasons.CARD_PARTIAL, gateway_code=code,
                gateway_message=message,
            )
        if status == "failed":
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REJECTED, reason=reasons.GATEWAY_FAILED, gateway_code=code,
                gateway_message=message,
            )
        if status == "refunded":
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REJECTED, reason=reasons.CARD_REFUNDED, gateway_code=code,
                gateway_message=message,
            )
        if status == "expired":
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.CANCELLED, reason=reasons.GATEWAY_EXPIRED, gateway_code=code,
                gateway_message=message,
            )
        return None  # waiting · confirming · confirmed · sending

    async def details(self, external_id: str) -> dict[str, Any]:
        """**ما يقوله NOWPayments عن دفعةٍ** — للّوحة: الحالُ وما دُفع وما وصل؛ ولا يُكتب منه شيء."""
        body = await self._request("GET", f"/payment/{external_id}")
        return {
            "status": body.get("payment_status"),
            "price": _pair(body.get("price_amount"), body.get("price_currency")),
            "paid": _pair(body.get("actually_paid"), body.get("pay_currency")),
            "received": _received(body),
        }

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        signature = (headers.get("x-nowpayments-sig") or "").strip().lower()
        if not signature or not self._ipn_secret:
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        if not isinstance(payload, dict):
            raise base.WebhookSignatureInvalid()
        if not any(hmac.compare_digest(signature, candidate) for candidate in self._signatures(payload)):
            raise base.WebhookSignatureInvalid()
        payment_id = payload.get("payment_id")
        return [str(payment_id)] if payment_id not in (None, "") else []

    def _signatures(self, payload: dict[str, Any]) -> list[str]:
        """**التوقيعُ كما يحسبه NOWPayments** — جسمٌ مرتّبُ المفاتيح بلا مسافات؛ وبصيغتين للحروف غير اللاتينية (مثالُ Node يتركها،
        ومثالُ PHP يهرّبها). **وكلتاهما بالسرّ نفسِه** — فلا تُقبل إلا بتوقيعه."""
        out: list[str] = []
        for ascii_only in (False, True):
            text = json.dumps(_sorted(payload), separators=(",", ":"), ensure_ascii=ascii_only)
            out.append(hmac.new(self._ipn_secret.encode(), text.encode(), hashlib.sha512).hexdigest())
        return out

    async def test_connection(self) -> str:
        await self._request("GET", "/status", auth=False)
        coins = await self._request("GET", "/merchant/coins")
        listed = coins.get("selectedCurrencies") or coins.get("data") or []
        names = {str(item).lower() for item in listed} if isinstance(listed, list) else set()
        card = "مفعَّلٌ" if CHARGE_CURRENCY in names else "غيرُ ظاهرٍ في عملات حسابك — فعّل USD في «Coins settings»"
        mode = "تجربة (sandbox)" if self.test_mode else "حيّ"
        return f"الاتصالُ بـNOWPayments يعمل — الوضع: {mode} · الدفعُ بالبطاقة (USD): {card}"


# ------------------------------------------------------------------ مساعدات


def _sorted(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    return value


def _redirect_url(body: Mapping[str, Any]) -> str | None:
    """**رابطُ صفحة الشريك** — `redirectData.redirect_url` في الوثائق؛ وصيغتان قريبتان احتياطاً، **وكلُّها https**."""
    nested = body.get("redirectData") or body.get("redirect_data")
    candidates = [nested.get("redirect_url") if isinstance(nested, dict) else None, body.get("redirect_url")]
    for value in candidates:
        if isinstance(value, str) and value.startswith("https://"):
            return value
    return None


def _pair(amount: Any, currency: Any) -> str | None:
    if amount in (None, "", "null") or currency in (None, ""):
        return None
    return f"{amount} {str(currency).upper()}"


def _received(body: Mapping[str, Any]) -> str | None:
    return _pair(body.get("outcome_amount"), body.get("outcome_currency"))


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def build_nowpay(values: Mapping[str, Any]) -> NowpayGateway:
    key = str(values.get("api_key") or "").strip()
    secret = str(values.get("ipn_secret") or "").strip()
    if not key or not secret:
        # **حتى يُدخل المالكُ المفتاحين تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return NowpayGateway(
        api_key=key,
        ipn_secret=secret,
        sandbox=credentials_service.is_on(values, "sandbox"),
        usd_per_jod=_decimal(values.get("usd_per_jod")) or DEFAULT_USD_PER_JOD,
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
    )
