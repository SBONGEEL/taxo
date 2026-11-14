"""**MoonPay Commerce — الدفعُ بالعملات الرقميّة في الأردن** (أمرُ المالك ٢٠٢٦-١١-١٤: «turn it ON for all of Jordan»).

**ما يجري**: نفتح عند MoonPay Commerce «شحنةً» (charge) لمرّةٍ واحدةٍ من رابط دفعٍ ديناميكيٍّ للمالك، ونرسل الدافعَ (الكبتنَ أو الراكب) إلى
صفحتها المستضافة، فيدفع من محفظته الرقميّة هناك. **ولا تمرّ بياناتُ دفعٍ بخوادمنا**، **والمالُ يصل محفظةَ المالك مباشرةً** (USDC على
Solana، من نظيرٍ إلى نظير): «MoonPay لا يستطيع ردَّه ولا استعادتَه» بنصّ وثائقهم — **والاستردادُ من المالك وحدَه**.

**ما أُخذ من وثائقه المنشورة** (`dev.commerce.moonpay.com`، قُرئت ٢٠٢٦-١١-١٤، ومعه ما قِيس بمفاتيح المالك في اليوم نفسِه):
- الأساسُ `https://api.hel.io`، والمصادقةُ `apiKey` في الاستعلام و`Authorization: Bearer <السرّ>`.
- `POST /v1/charge/api-key` بـ`paymentRequestId` (رابطُ الدفع) و`requestAmount` — **قِيس: بالعملة الكبرى نصّاً** («7.09» = ٧٫٠٩ دولار؛
  ويُخزَّن عندهم بستِّ خاناتٍ عشريّة) — و`successRedirectUrl`/`cancelRedirectUrl` و`expiresAt`، ويعود بـ`id` و`pageUrl`
  (`https://app.hel.io/charge/<token>`).
- `GET /v1/charge/api-key/{token}`: `paylinkTx` فارغٌ ما لم يُدفع، وإلا `paylinkTx.meta.transactionStatus`
  (INITIATED · PENDING · SUCCESS · FAILED · CANCELED · SETTLED) و`meta.totalAmount`/`meta.amount` بأصغر وحدات العملة المدفوعة.
- **الإشعار**: ترويسةُ `X-Signature` = HMAC-SHA256 بالست عشريّ على **الجسم الخامّ**، مفتاحُه `sharedToken` الإشعار. وحمولتُه تحمل
  `chargeToken` — **وهو معرّفُنا عندهم** (`external_id`).
- **التسعير**: الدينارُ غيرُ مدعومٍ عندهم (قائمةُ عملاتهم قِيست ٢٠٢٦-١١-١٤) — **فالسعرُ بالدولار بربط الدينار الرسميّ** (1 JOD = 1.4104
  USD)، مقرَّباً للأعلى إلى السنت، **والطلبُ يبقى بالدينار**. وبالدولار يُقارَن ما وصل بما طُلب: **مبلغٌ أقلُّ لا يُقيَّد** — يبقى «قيد
  المعالجة» بسببه، ويُطفأ المفتاحُ آليّاً ويُشعَر المالك (`moonpay_guard`).

**والحقيقةُ جوابُ `check`** لا حمولةُ الإشعار (قاعدةُ `payment_gateways`): الإشعارُ الموقَّعُ يعيد `chargeToken` وحدَه، ثمّ يُسأل MoonPay.
**والدفعُ بالبطاقة عبر MoonPay Ramps غيرُ مفعَّلٍ للتاجر** (يحتاج حسابَ Ramps منفصلاً) — فلا يُقال للدافع إنه يدفع ببطاقة.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

LIVE_BASE = "https://api.hel.io"
SANDBOX_BASE = "https://api.dev.hel.io"
PARTNER_NAME = "MoonPay Commerce"
#: **ربطُ الدينار بالدولار** (البنك المركزيّ الأردنيّ: 0.709 دينار للدولار منذ ١٩٩٥) — افتراضٌ يُبدَّل من العقد
DEFAULT_USD_PER_JOD = Decimal("1.4104")
#: **رسمُ MoonPay Commerce على التاجر** كما نشرته وثائقُه (`pricing-fees`) — ٢٪ للمعاملة؛ على TAXO من المال الواصل لا على الدافع
PARTNER_FEE_TEXT = "2%"
#: **مدّةُ صفحة الدفع** — بعدها تنتهي الشحنةُ عندهم، ومهلتُنا (`CHECKOUT_TTL_HOURS`) تُلغي الطلب
CHARGE_TTL = timedelta(hours=2)
#: **أصغرُ وحدات الدولار عندهم** — قِيس: «7.09» ⇐ «7090000» (ستُّ خانات)
_USD_UNITS = Decimal(1_000_000)
_CENT = Decimal("0.01")

#: **حالاتٌ تعني أنّ المالَ وصل** — والتسويةُ (SETTLED) بعد النجاح
_PAID = frozenset({"SUCCESS", "SETTLED"})
#: **حالاتٌ لم تكتمل بعد** — المعاملةُ على السلسلة تنتظر تأكيداً: «قيد المعالجة» لا «لم يُدفع»
_PROCESSING = frozenset({"INITIATED", "PENDING"})
_FAILED = frozenset({"FAILED", "CANCELED", "CANCELLED"})


def charge_amount(amount: Decimal, usd_per_jod: Decimal) -> Decimal:
    """**ما يُطلب بالدولار لمبلغٍ بالدينار** — بالربط، ومقرَّباً للأعلى إلى السنت. **والحسابُ هنا وحدَه** (§14)."""
    return (amount * usd_per_jod).quantize(_CENT, rounding=ROUND_UP)


class MoonpayGateway:
    name = "moonpay"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق** — وإن فات، فالتسويةُ الدوريّة تقيِّده من جواب MoonPay المباشر بعد مهلته
    confirms_by_webhook = True
    #: **دفعٌ بأصلٍ رقميّ** — لا بطاقة: فلا يُعرض في زرّ «البطاقة المصرفية»، ويُقال للدافع ما يقع
    crypto = True
    partner_name = PARTNER_NAME
    partner_fee = PARTNER_FEE_TEXT

    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        webhook_secret: str,
        paylink_id: str,
        sandbox: bool,
        usd_per_jod: Decimal = DEFAULT_USD_PER_JOD,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
        packages: tuple[Decimal, ...] = (),
    ) -> None:
        self._key = api_key
        self._secret = secret_key
        self._webhook_secret = webhook_secret
        self.paylink_id = paylink_id
        self.base_url = SANDBOX_BASE if sandbox else LIVE_BASE
        self.test_mode = sandbox
        self.usd_per_jod = usd_per_jod
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: **باقاتُ الراكب** (أمرُ المالك: «fixed-value credit packages, values editable from our panel») — بالدينار، من العقد
        self.packages = packages
        self.last_status: str | None = None
        self.last_received: str | None = None

    # ------------------------------------------------------------------ الشبكة

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = base.REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._secret}"}
        try:
            async with base.http_client(timeout) as http:
                response = await http.request(
                    method, f"{self.base_url}{path}", json=payload, params={"apiKey": self._key}, headers=headers
                )
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        if response.status_code == 204:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من MoonPay Commerce") from exc
        if response.status_code < 400 and isinstance(body, list):
            # **أبوابُ القوائم** (`/v1/wallet/all`) تعيد مصفوفةً لا كائناً — وهو شكلُها الحقيقيّ المقيس
            return {"items": body}
        if response.status_code >= 400 or not isinstance(body, dict):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"MoonPay Commerce: {message}" if message else "رفض MoonPay Commerce الطلب")
        return body

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — أصغرُ قراءةٍ بالمفتاح ومهلةٍ قصيرة: محافظُ الحساب."""
        await self._request("GET", "/v1/wallet/all", timeout=base.HEALTH_TIMEOUT_SECONDS)

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
        # **الإشعارُ عامٌّ يُضبط مرّةً** في حساب MoonPay (لا لكلِّ شحنة)؛ **ولا اسمَ ولا هاتفَ للدافع**: مرجعُ طلبنا وحدَه
        price = charge_amount(amount, self.usd_per_jod)
        expires = (datetime.now(UTC) + CHARGE_TTL).isoformat().replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "paymentRequestId": self.paylink_id,
            "requestAmount": str(price),
            "expiresAt": expires,
            "successRedirectUrl": return_url,
            "cancelRedirectUrl": return_url,
            "prepareRequestBody": {
                "customerDetails": {"additionalJSON": json.dumps({"order_ref": customer.order_ref or "", "source": "taxo"})}
            },
        }
        body = await self._request("POST", "/v1/charge/api-key", payload)
        token = _token_of(body.get("pageUrl"))
        if token is None:
            raise base.GatewayError("جوابُ MoonPay Commerce بلا رابطِ صفحة")
        return base.Checkout(external_id=token, checkout_url=str(body["pageUrl"]))

    async def _charge(self, token: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/charge/api-key/{token}")

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        charge = await self._charge(external_id)
        self.last_status = None
        self.last_received = None
        tx = charge.get("paylinkTx")
        if not isinstance(tx, dict):
            return None  # لم يدفع بعد — الصفحةُ مفتوحةٌ أو تُركت؛ والمهلةُ تحسمها
        meta = tx.get("meta") if isinstance(tx.get("meta"), dict) else {}
        status = str(meta.get("transactionStatus") or "").upper()
        code = status[:32] or None
        if status in _PROCESSING:
            self.last_status = "processing"
            return None
        if status in _FAILED:
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REJECTED, reason=reasons.GATEWAY_FAILED, gateway_code=code,
            )
        if status not in _PAID:
            return None
        paid = _paid_usd(meta)
        asked = _units(charge.get("requestAmount"))
        received = f"{_plain(paid)} {_currency(meta)}".strip() if paid is not None else None
        self.last_received = received
        # **ما وصل يُقارَن بما طُلب بالدولار** — أقلُّ منه (أو لا يُقرأ) ⇐ يُعاد بالدينار مبلغاً مختلفاً، فلا يُقيَّد ويُطفأ المفتاح
        matches = paid is not None and asked is not None and paid >= asked
        return base.GatewayEvent(
            external_id, PaymentRequestStatus.APPROVED, gateway_code=code, gateway_message=received,
            amount=None if matches else _in_jod(paid, self.usd_per_jod),
        )

    async def details(self, external_id: str) -> dict[str, Any]:
        """**ما يقوله MoonPay عن شحنةٍ** — للّوحة؛ ولا يُكتب منه شيء."""
        charge = await self._charge(external_id)
        tx = charge.get("paylinkTx") if isinstance(charge.get("paylinkTx"), dict) else {}
        meta = tx.get("meta") if isinstance(tx.get("meta"), dict) else {}
        return {
            "requested_usd": str(_units(charge.get("requestAmount")) or ""),
            "status": meta.get("transactionStatus"),
            "paid": str(_paid_usd(meta) or ""),
            "currency": _currency(meta),
            "tx": meta.get("transactionSignature") or tx.get("id"),
        }

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        lowered = {key.lower(): value for key, value in headers.items()}
        offered = (lowered.get("x-signature") or "").strip().lower()
        if not offered or not self._webhook_secret:
            raise base.WebhookSignatureInvalid()
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(offered, expected):
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        if not isinstance(payload, dict):
            return []
        token = payload.get("chargeToken")
        if not isinstance(token, str) or not token:
            tx = payload.get("transactionObject") if isinstance(payload.get("transactionObject"), dict) else {}
            meta = tx.get("meta") if isinstance(tx.get("meta"), dict) else {}
            token = meta.get("chargeToken") if isinstance(meta.get("chargeToken"), str) else None
        return [token] if token and _token_like(token) else []

    async def test_connection(self) -> str:
        await self._request("GET", "/v1/wallet/all")
        mode = "تجربة (devnet)" if self.test_mode else "حيّ"
        return f"الاتصالُ بـMoonPay Commerce يعمل — الوضع: {mode} · رابطُ الدفع: {self.paylink_id}"


# ------------------------------------------------------------------ مساعدات


def _token_of(page_url: Any) -> str | None:
    """**معرّفُ الشحنة من رابط صفحتها** (`https://app.hel.io/charge/<token>`) — وكلُّه https."""
    if not isinstance(page_url, str) or not page_url.startswith("https://"):
        return None
    token = page_url.rstrip("/").rsplit("/", 1)[-1]
    return token if _token_like(token) else None


def _token_like(value: str) -> bool:
    return 8 <= len(value) <= 64 and all(ch.isalnum() or ch == "-" for ch in value)


def _units(value: Any) -> Decimal | None:
    """**أصغرُ الوحدات ⇐ العملةُ الكبرى** (ستُّ خاناتٍ للدولار وUSDC)."""
    number = _decimal(value)
    return (number / _USD_UNITS).quantize(Decimal("0.000001")) if number is not None else None


def _paid_usd(meta: Mapping[str, Any]) -> Decimal | None:
    """**ما وصل** — `totalAmount` (أو `amount`) بأصغر وحدات عملته؛ وعملةٌ غيرُ ستِّ خاناتٍ تُقرأ بخاناتها إن ذُكرت."""
    raw = meta.get("totalAmount") if meta.get("totalAmount") not in (None, "") else meta.get("amount")
    number = _decimal(raw)
    if number is None:
        return None
    currency = meta.get("currency") if isinstance(meta.get("currency"), dict) else {}
    try:
        places = int(currency.get("decimals", 6))
    except (TypeError, ValueError):
        places = 6
    return (number / (Decimal(10) ** places)).quantize(Decimal("0.000001"))


def _plain(value: Decimal) -> str:
    """**المبلغُ بلا أصفارٍ زائدة** — «14.11» لا «14.110000»، وخانتان على الأقلّ."""
    text = format(value.normalize(), "f")
    whole, _, frac = text.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def _currency(meta: Mapping[str, Any]) -> str:
    currency = meta.get("currency")
    if isinstance(currency, dict):
        return str(currency.get("symbol") or "")
    return str(currency or "")


def _in_jod(paid_usd: Decimal | None, usd_per_jod: Decimal) -> Decimal | None:
    """**ما وصل بالدينار** — للمقارنة بالطلب وحدَها (مبلغٌ مختلفٌ لا يُقيَّد)؛ و«لا يُقرأ» صفرٌ فلا يطابق أبداً."""
    if paid_usd is None or usd_per_jod <= 0:
        return Decimal("0")
    return (paid_usd / usd_per_jod).quantize(Decimal("0.001"))


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def _packages(raw: Any) -> tuple[Decimal, ...]:
    out: list[Decimal] = []
    for part in str(raw or "").split(","):
        value = _decimal(part)
        if value is not None and value not in out:
            out.append(value.quantize(Decimal("0.001")))
    return tuple(sorted(out))


def build_moonpay(values: Mapping[str, Any]) -> MoonpayGateway:
    key = str(values.get("api_key") or "").strip()
    secret = str(values.get("secret_key") or "").strip()
    hook = str(values.get("webhook_secret") or "").strip()
    paylink = str(values.get("paylink_id") or "").strip()
    if not key or not secret or not hook or not paylink:
        # **حتى تُدخل المفاتيحُ الأربعة تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return MoonpayGateway(
        api_key=key,
        secret_key=secret,
        webhook_secret=hook,
        paylink_id=paylink,
        sandbox=credentials_service.is_on(values, "sandbox"),
        usd_per_jod=_decimal(values.get("usd_per_jod")) or DEFAULT_USD_PER_JOD,
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
        packages=_packages(values.get("rider_packages")),
    )
