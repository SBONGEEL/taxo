"""**Whop — «الدفع بالبطاقة المصرفية» للكبتن في الأردن** (أمرُ المالك ٢٠٢٦-١١-١٣: «prepare everything, but nothing goes live yet»).

**ما يجري**: نفتح عند Whop «إعدادَ دفعٍ» (checkout configuration) بخطّةٍ لمرّةٍ واحدةٍ بالدينار، ونرسل الدافعَ (الكبتنَ أو الراكب) إلى صفحة Whop المستضافة،
فيدفع ببطاقته هناك. **ولا تمرّ بيانات البطاقة بخوادمنا**، **ولا أصلَ رقميَّ في الطريق**: شراءٌ عاديٌّ بالبطاقة يصل رصيدَ Whop للمالك.

**ما أُخذ من وثائقه المنشورة** (`docs.whop.com`، قُرئت ٢٠٢٦-١١-١٣):
- الأساسُ `https://api.whop.com/api/v1` (والتجربة `https://sandbox-api.whop.com/api/v1` بمفاتيحَ منفصلة)، والمصادقةُ `Authorization: Bearer`.
- `POST /checkout_configurations` بـ`plan` = {`company_id`, `currency`, `plan_type: one_time`, `initial_price` بعملة العقد} و`metadata`
  و`redirect_url` — ويعود بـ`id` (`ch_…`) و`purchase_url`.
- `GET /payments` بـ`account_id` (`biz_…`) و`created_after` وترقيمٍ بالمؤشّر (`first`/`after`، و`page_info.end_cursor`)؛ **ولا مرشّحَ
  بإعداد الدفع** — فيُطابَق `checkout_configuration_id` في كلِّ دفعةٍ هنا.
- حالُ الدفعة `status`: draft · open · authorized · paid · pending · uncollectible · unresolved · void، و`substatus` أدقُّ منه
  (succeeded · refunded · partially_refunded · dispute_lost · failed …)، و`total.amount` نصٌّ عشريٌّ بالعملة الكبرى.
- **الإشعار**: مواصفةُ Standard Webhooks — ترويساتُ `webhook-id` و`webhook-timestamp` و`webhook-signature` (`v1,<base64>`)، والتوقيعُ
  `HMAC-SHA256` على `"{id}.{timestamp}.{الجسمُ الخامّ}"` بالسرّ (`ws_…`) **كما أُعطي**؛ ويُرفض ما بَعُد توقيتُه أكثرَ من ٥ دقائق.

**والحقيقةُ جوابُ `check`** لا حمولةُ الإشعار (قاعدةُ `payment_gateways`): الإشعارُ الموقَّعُ يعيد معرّفَ إعداد الدفع وحدَه، ثمّ يُسأل Whop.

**والمبلغ**: الطلبُ بالدينار، **وWhop يقبل الدينار (`jod` في تعداد عملاته) فيُخصم الدينارُ نفسُه بلا صرف** — وهو الأصل. **والدولارُ بديلٌ
من العقد** (`currency = usd`) إن رفض Whop الدينارَ لحساب المالك: يُحوَّل حينها بربط الدينار الرسميّ (1 JOD = 1.4104 USD) ويُقرَّب للأعلى
إلى السنت. **وبالدينار يُقارَن ما دُفع بالمطلوب** (`GatewayEvent.amount`): مبلغٌ مختلفٌ لا يُقيَّد، ويبقى الطلبُ «قيد المعالجة» بسببه
ويُشعَر المالك — وهو شرطُ المالك ٢٠٢٦-١١-١٣ «a credit mismatches the charge». **ورسمُ Whop على التاجر** يُخصم ممّا يصل المالكَ — **فلا يُضاف على الكبتن شيء**: تُخصم بطاقتُه المستحقَّ وحدَه.
**ومقدارُ رسم Whop لا يُكتب هنا**: لم يُؤكَّد لحساب المالك بعد (سُئل دعمُهم) — فلا يُقيَّد رسمٌ بالدينار على الطلب.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

LIVE_BASE = "https://api.whop.com/api/v1"
SANDBOX_BASE = "https://sandbox-api.whop.com/api/v1"

#: **ربطُ الدينار بالدولار** (البنك المركزيّ الأردنيّ: 0.709 دينار للدولار منذ ١٩٩٥) — افتراضٌ يُبدَّل من العقد
DEFAULT_USD_PER_JOD = Decimal("1.4104")
#: **عملةُ الخصم ابتداءً الدينار** (أمرُ المالك: «Use JOD if Whop supports it» — و`jod` في قائمة عملات Whop المنشورة `Currencies`،
#: قُرئت ٢٠٢٦-١١-١٣)؛ **والدولارُ بديلٌ من العقد** بربط الدينار إن رفض Whop الدينارَ لحساب المالك
DEFAULT_CURRENCY = "jod"
CURRENCIES = frozenset({"jod", "usd"})
CHARGE_CURRENCY = "usd"
PARTNER_NAME = "Whop"
#: **مهلةُ الإشعار** (الوثائق: «more than 5 minutes») — إشعارٌ أقدمُ منها يُرفض ولو صحّ توقيعُه (إعادةُ بثٍّ قديم)
WEBHOOK_TOLERANCE_SECONDS = 300
#: **كم يُرجع البحثُ عن دفعة إعداد الدفع** — صفحاتٌ من مئة، منذ ثلاثة أيّام؛ ومراجعةُ الملغى عندنا ٤٨ ساعة
LOOKBACK = timedelta(days=3)
PAGE_SIZE = 100
MAX_PAGES = 5
_CENT = Decimal("0.01")

#: **ما يعني أنّ المالَ رُدّ أو خُسر بعد الدفع** — «دُفع» لا يُعتمد معه
_REVERSED = frozenset({"refunded", "partially_refunded", "dispute_lost", "auto_refunded"})
#: **حالاتٌ لم تكتمل بعد** — البنكُ يعالج أو يطلب تحقّقاً (3-D Secure): «قيد المعالجة» لا «لم يُدفع»
_PROCESSING = frozenset({"authorized", "pending", "unresolved"})


def charge_amount(amount: Decimal, usd_per_jod: Decimal) -> Decimal:
    """**ما يُخصم بالدولار لمبلغٍ بالدينار** — بالربط، ومقرَّباً للأعلى إلى السنت. **والحسابُ هنا وحدَه** (§14)."""
    return (amount * usd_per_jod).quantize(_CENT, rounding=ROUND_UP)


class WhopGateway:
    name = "whop"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق** — وإن فات، فالتسويةُ الدوريّة تقيِّده من جواب Whop المباشر بعد مهلته
    confirms_by_webhook = True
    drivers_only = True
    #: **ما يُقال للكبتن قبل الدفع** — اسمُ معالج البطاقة، **ورسمُه على TAXO** (فلا نصَّ رسمٍ على الدافع)
    partner_name = PARTNER_NAME
    partner_fee = None
    #: **لا تحقّقَ هويّةٍ من الدافع، ولا أصلَ رقميّ** — فلا يُقال للكبتن ما لا يقع (السطران خاصّان بـNOWPayments)
    partner_kyc = False
    settles_digital = False

    def __init__(
        self,
        *,
        api_key: str,
        webhook_secret: str,
        company_id: str,
        sandbox: bool,
        usd_per_jod: Decimal = DEFAULT_USD_PER_JOD,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
        currency: str = DEFAULT_CURRENCY,
    ) -> None:
        self._key = api_key
        self.currency = currency if currency in CURRENCIES else DEFAULT_CURRENCY
        #: **ما يُقال للدافع**: عملةُ الخصم، وسعرُ الصرف حين يكون بالدولار وحدَه (`None` بالدينار — لا صرف)
        self.card_currency = self.currency.upper()
        self._webhook_secret = webhook_secret
        self.company_id = company_id
        self.base_url = SANDBOX_BASE if sandbox else LIVE_BASE
        self.test_mode = sandbox
        self.usd_per_jod = usd_per_jod if self.currency == "usd" else None
        self._rate = usd_per_jod
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: آخرُ حالٍ قاله `check` — **ولا «pending» أبداً** (ذاك يُلغي الطلبَ عند عودة الكبتن): صفحةُ Whop قد تطلب تحقّقَ البنك
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
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Whop") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = None
            if isinstance(body, dict):
                error = body.get("error")
                message = error.get("message") if isinstance(error, dict) else body.get("message")
            raise base.GatewayError(f"Whop: {message}" if message else "رفض Whop الطلب")
        return body

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — أصغرُ قراءةٍ بالمفتاح ومهلةٍ قصيرة."""
        await self._request(
            "GET", "/payments", params={"account_id": self.company_id, "first": 1}, timeout=base.HEALTH_TIMEOUT_SECONDS
        )

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
        # **عنوانُ الإشعار يُضبط في لوحة Whop مرّةً** (لا لكلِّ دفعة) — فلا يُرسل هنا؛ ولا اسمَ ولا هاتفَ للدافع: مرجعُ طلبنا وحدَه
        price = charge_amount(amount, self._rate) if self.currency == "usd" else amount
        payload: dict[str, Any] = {
            "mode": "payment",
            "redirect_url": return_url,
            "metadata": {"order_ref": customer.order_ref or "", "source": "taxo"},
            "plan": {
                "company_id": self.company_id,
                "currency": self.currency,
                "plan_type": "one_time",
                "initial_price": float(price),
                "title": description[:80],
            },
        }
        body = await self._request("POST", "/checkout_configurations", payload)
        config_id = str(body.get("id") or "")
        url = _purchase_url(body.get("purchase_url"))
        if not config_id.startswith("ch_") or url is None:
            raise base.GatewayError("جوابُ Whop بلا معرّف دفعٍ أو رابطِ صفحة")
        return base.Checkout(external_id=config_id, checkout_url=url)

    async def _payments_of(self, config_id: str) -> list[dict[str, Any]]:
        """**دفعاتُ إعداد الدفع** — لا مرشّحَ به في الوثائق، فتُقرأ صفحاتُ اليومين الأخيرين ويُطابَق المعرّفُ هنا."""
        since = (datetime.now(UTC) - LOOKBACK).isoformat().replace("+00:00", "Z")
        found: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {
                "account_id": self.company_id,
                "created_after": since,
                "first": PAGE_SIZE,
                "order": "created_at",
                "direction": "desc",
            }
            if cursor:
                params["after"] = cursor
            body = await self._request("GET", "/payments", params=params)
            rows = body.get("data")
            if not isinstance(rows, list):
                raise base.GatewayError("جوابُ Whop بلا قائمة دفعات")
            found.extend(row for row in rows if isinstance(row, dict) and row.get("checkout_configuration_id") == config_id)
            info = body.get("page_info") if isinstance(body.get("page_info"), dict) else {}
            cursor = info.get("end_cursor")
            if not info.get("has_next_page") or not cursor:
                break
        return found

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        payments = await self._payments_of(external_id)
        self.last_status = None
        self.last_received = None
        if not payments:
            return None  # لم يدفع بعد — الصفحةُ مفتوحةٌ أو تُركت؛ والمهلةُ تحسمها
        # **دفعةٌ مكتملةٌ واحدةٌ تكفي** — محاولةٌ رُفضت ثمّ أُعيدت فنجحت تُقرأ بنجاحها
        for row in payments:
            status = str(row.get("status") or "").lower()
            sub = str(row.get("substatus") or "").lower()
            if status != "paid":
                continue
            received = _money(row.get("total"))
            self.last_received = received
            code = (sub or status)[:32]
            if sub in _REVERSED:
                return base.GatewayEvent(
                    external_id, PaymentRequestStatus.REJECTED, reason=reasons.CARD_REFUNDED, gateway_code=code,
                    gateway_message=received,
                )
            if not _matches(row, self.company_id, self.currency):
                # **دفعةٌ لغير حساب المالك أو بغير عملة العقد لا تُعتمد** — يحسمها المالكُ من اللوحة
                return None
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.APPROVED, gateway_code=code, gateway_message=received,
                # **بالدينار يُقارَن المدفوعُ بالمطلوب** — والخلافُ يُبقي الطلبَ معلَّقاً لا مقيَّداً (`settle`)؛ وبالدولار لا يُعاد
                # (عملةٌ غيرُ عملة الطلب، والسعرُ الذي حدّدناه هو ما على الصفحة)
                amount=_paid(row) if self.currency == "jod" else None,
            )
        if any(str(row.get("status") or "").lower() in _PROCESSING for row in payments):
            self.last_status = "processing"
        # **محاولاتٌ فشلت فقط** (void · uncollectible · open): لا يُرفض الطلبُ — الكبتنُ قد يعيد في الصفحة نفسِها، والمهلةُ تغلقه
        return None

    async def details(self, external_id: str) -> dict[str, Any]:
        """**ما يقوله Whop عن دفعات طلبٍ** — للّوحة؛ ولا يُكتب منه شيء."""
        payments = await self._payments_of(external_id)
        return {
            "payments": [
                {"id": row.get("id"), "status": row.get("status"), "substatus": row.get("substatus"), "total": _money(row.get("total"))}
                for row in payments
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
        config_id = data.get("checkout_configuration_id")
        return [str(config_id)] if isinstance(config_id, str) and config_id.startswith("ch_") else []

    def _secret_keys(self) -> list[bytes]:
        """**مفتاحُ HMAC من السرّ** — Whop: السرُّ «كما أُعطي» (`ws_…`) بايتاته مفتاحاً؛ **وصيغةُ Standard Webhooks** (`whsec_` + base64)
        تُفكّ. **وكلاهما السرُّ نفسُه** — فلا يُقبل إلا بتوقيعه."""
        secret = self._webhook_secret
        keys = [secret.encode()]
        if secret.startswith("whsec_"):
            try:
                keys.append(base64.b64decode(secret[len("whsec_") :], validate=True))
            except (binascii.Error, ValueError):
                pass
        return keys

    async def test_connection(self) -> str:
        await self._request("GET", "/payments", params={"account_id": self.company_id, "first": 1})
        mode = "تجربة (sandbox)" if self.test_mode else "حيّ"
        return f"الاتصالُ بـWhop يعمل — الوضع: {mode} · الحساب: {self.company_id}"


# ------------------------------------------------------------------ مساعدات


def _purchase_url(value: Any) -> str | None:
    """**رابطُ صفحة الدفع** — الوثائقُ تعطيه نسبيّاً (`/checkout/ch_…/`) أحياناً، فيُكمَّل بنطاق Whop؛ **وكلُّه https**."""
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("/"):
        value = f"https://whop.com{value}"
    return value if value.startswith("https://") else None


def _money(value: Any) -> str | None:
    if not isinstance(value, dict) or value.get("amount") in (None, ""):
        return None
    return f"{value.get('amount')} {str(value.get('currency') or '').upper()}".strip()


def _matches(row: Mapping[str, Any], company_id: str, currency_code: str = CHARGE_CURRENCY) -> bool:
    """**الدفعةُ لحساب المالك وبعملة العقد** — `account_id` (أو `company_id` في الإصدارات الأقدم) والعملة."""
    owner = row.get("account_id") or row.get("company_id")
    if isinstance(owner, dict):
        owner = owner.get("id")
    currency = str(row.get("currency") or (row.get("total") or {}).get("currency") or "").lower()
    return (owner in (None, company_id)) and currency in ("", currency_code)


def _paid(row: Mapping[str, Any]) -> Decimal | None:
    """**ما دُفع بالعملة الكبرى** — `total.amount` (أو `total` رقماً)؛ و`None` حين لا يُقرأ، فلا يُخترع مبلغ."""
    total = row.get("total")
    return _decimal(total.get("amount") if isinstance(total, dict) else total)


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def build_whop(values: Mapping[str, Any]) -> WhopGateway:
    key = str(values.get("api_key") or "").strip()
    secret = str(values.get("webhook_secret") or "").strip()
    company = str(values.get("company_id") or "").strip()
    if not key or not secret or not company.startswith("biz_"):
        # **حتى يُدخل المالكُ المفاتيحَ الثلاثة تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return WhopGateway(
        api_key=key,
        webhook_secret=secret,
        company_id=company,
        sandbox=credentials_service.is_on(values, "sandbox"),
        usd_per_jod=_decimal(values.get("usd_per_jod")) or DEFAULT_USD_PER_JOD,
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
        currency=str(values.get("currency") or DEFAULT_CURRENCY).strip().lower(),
    )
