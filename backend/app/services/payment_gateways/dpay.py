"""**Dpay (dpay.ly) — بوّابةُ الدفع الليبيّة** (أمرُ المالك ٢٠٢٦-١١-١٧: «Build ONE provider-as-data integration … all switches OFF»).

**ما يجري**: لكلِّ طلبٍ عندنا «جلسةُ دفعٍ مستضافة» (Checkout Session v2) عند Dpay، **محصورةٌ بوسيلة الصفّ الذي اختاره الدافع**
(`allowed_methods`) — إدفع لي، موبي كاش، مصرفي، يُسر، الصحارى، سداد، معاملات (البطاقةُ المحلّيّة)، والبطاقةُ الدوليّة (MPGS).
**ولا تمرّ بيانات البطاقة ولا رمزُ التحقّق بخوادمنا** — الصفحةُ صفحةُ Dpay. **وDpay لا يمسك المال**: كلُّ وسيلةٍ تسوّي لحساب التاجر
عند مزوّدها بعقده معه، وDpay يربط ويشهد.

**ما أُخذ من توثيقه المنشور** (`dpay.ly/docs/api`، قُرئ ٢٠٢٦-١١-١٧):
- `POST /api/v2/checkout-sessions` بـ`amount` (نصٌّ عشريٌّ بمنزلتين **والثالثةُ تُرفض لا تُقرَّب**) و`currency` (LYD وحدَه) و`reference`
  و`return_url` و`metadata` و`allowed_methods` و`expires_in_minutes`، وترويسةُ `Idempotency-Key` (≤ ٦٤). يعود `{data: {id, url, status}}`.
- `GET /api/v2/checkout-sessions/{id}` **مصدرُ الحقيقة**: `open` · `paid` · `expired` · `cancelled`، و`payment` يحمل `pay_method`
  و`tx_id` و`amount_charged` (شاملاً الرسم) و`fee_amount`.
- **الإشعار**: `X-DPAY-Timestamp` و`X-DPAY-Event` و`X-DPAY-Signature` = HMAC-SHA256 ستّ عشريّ صغير على `{timestamp}.{body الخامّ}`
  بالسرّ كاملاً (`whsec_…` بسابقته)، **وما هو أقدمُ من خمس دقائق يُرفض**.
- **التجربة**: رمزٌ يبدأ بـ`sb_tk_` على المسارات نفسِها ⇐ `live: false` ومعرّفاتٌ `cs_test_…`؛ **وسداد وMPGS لا يُحاكَيان**.

**والحقيقةُ جوابُ `check`** لا حمولةُ الإشعار (قاعدةُ `payment_gateways`): الإشعارُ الموقَّعُ يعيد معرّفَ الجلسة، ثمّ يُسأل Dpay. **و`live`
شرطٌ صريح** (توصيتُهم): جلسةٌ تجريبيّةٌ لا تُعتمد على عقدٍ حيّ، ولا العكس.

**والرسم**: صفحةُ Dpay تضيف رسمَ الوسيلة فوق مبلغنا وتعرضه للدافع قبل أن يدفع (`amount` «قبل رسم المزوّد») — **فالرسمُ على الدافع بنيةً**
(`fee_bearer = user`)، ويُسجَّل كما قاله Dpay (`fee_amount`) ولا يُعاد حسابُه.

**والأردن** (الاشتراكُ ببطاقةٍ دوليّة عبر MPGS): Dpay يقبل الدينارَ الليبيَّ وحدَه، **فمبلغُ الجلسة = ثمنُ الخطّة بالدينار الأردنيّ × سعرٌ
واحدٌ يضعه المالكُ في العقد** (`lyd_per_jod`)، مقرَّباً للأعلى إلى القرش، ويُختم في `metadata` فيُطابَق عند التأكيد. **والدولارُ المعروضُ
تقريبيٌّ** بربط الدينار الرسميّ (`usd_per_jod`) — **الخصمُ الفعليُّ يحدّده مصرفُ MPGS بسعره**، ويُقال ذلك للكبتن. وهذا كلُّه مطفأٌ حتى
يؤكّد Dpay كتابةً قبولَ الدفع من خارج ليبيا (أسئلةُ رسالة ١٧/١١).
"""

from __future__ import annotations

import copy
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

API_BASE = "https://dpay.ly/api/v2"
PARTNER_NAME = "Dpay"
#: **ربطُ الدينار الأردنيّ بالدولار** (البنك المركزيّ الأردنيّ: 0.709 دينار للدولار) — للعرض التقريبيّ وحدَه
DEFAULT_USD_PER_JOD = Decimal("1.4104")
#: **مهلةُ الإشعار** (توثيقُ Dpay: خمسُ دقائق) — أقدمُ منها يُرفض ولو صحّ توقيعُه (إعادةُ بثٍّ قديم)
WEBHOOK_TOLERANCE_SECONDS = 300
#: **عمرُ الجلسة** — ساعةٌ كافتراضهم؛ والمهلةُ عندنا تغلق الطلبَ بعدها
SESSION_MINUTES = 60
_PIASTRE = Decimal("0.01")

#: **وسائلُ Dpay كما يسمّيها توثيقُه** (`GET /api/pay-methods` → `slug`) — كودُ صفِّ الطريقة عندنا `dpay_<slug>`
METHOD_SLUGS: frozenset[str] = frozenset(
    {"edfali", "mobicash", "masrefypay", "yousrpay", "saharapay", "sadad", "moamalat", "mpgs"}
)
CODE_PREFIX = "dpay_"


def slug_of(code: str | None) -> str | None:
    """**وسيلةُ Dpay من كود الصفّ** — `dpay_edfali` ⇐ `edfali`؛ وكودٌ لا يعرفه التوثيقُ `None` (فلا تُفتح له صفحة)."""
    if not code or not code.startswith(CODE_PREFIX):
        return None
    slug = code[len(CODE_PREFIX) :]
    if slug.endswith("_jo"):
        slug = slug[: -len("_jo")]
    return slug if slug in METHOD_SLUGS else None


def to_lyd(amount: Decimal, lyd_per_jod: Decimal) -> Decimal:
    """**ما يُطلب بالدينار الليبيّ لمبلغٍ بالأردنيّ** — بالسعر المضبوط ومقرَّباً للأعلى إلى القرش. **والحسابُ هنا وحدَه** (§14)."""
    return (amount * lyd_per_jod).quantize(_PIASTRE, rounding=ROUND_UP)


def two_places(amount: Decimal) -> str:
    """**المبلغُ بمنزلتين أو لا دفع** — Dpay يرفض الثالثةَ ولا يقرّبها، ونحن لا نقرّب مالَ أحدٍ بصمت."""
    if amount != amount.quantize(_PIASTRE):
        raise base.GatewayError("هذا المبلغُ لا يُدفع عبر Dpay — المنزلةُ الثالثةُ لا تُقبل")
    return str(amount.quantize(_PIASTRE))


class DpayGateway:
    name = "dpay"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق** — وإن فات، فالتسويةُ الدوريّة تقيِّده من جواب Dpay المباشر بعد مهلته
    confirms_by_webhook = True
    #: **ما يُقال قبل الدفع** — اسمُ الوسيط؛ ورسمُ الوسيلة تعرضه صفحتُه مع الإجماليّ قبل الدفع
    partner_name = PARTNER_NAME
    partner_fee = None
    partner_kyc = False
    settles_digital = False

    def __init__(
        self,
        *,
        api_token: str,
        webhook_secret: str,
        sandbox: bool,
        lyd_per_jod: Decimal | None = None,
        usd_per_jod: Decimal | None = None,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self._token = api_token
        self._webhook_secret = webhook_secret
        self.base_url = API_BASE
        #: **رمزُ التجربة يقرّر الوضعَ بنفسه** (`sb_tk_`) — فلا يُخطئ مفتاحٌ يدويٌّ فيفتح مالاً تجريبيّاً لحسابٍ حقيقيّ
        self.test_mode = sandbox or api_token.startswith("sb_tk_")
        #: **الأردن وحدَه**: سعرُ التحويل إلى الليبيّ (مصدرٌ واحدٌ من العقد) — `None` في ليبيا
        self.lyd_per_jod = lyd_per_jod
        #: **ما يقرؤه العرضُ** (`card_currency` و`usd_per_jod`): الدولارُ التقريبيُّ في الأردن وحدَه
        self.usd_per_jod = (usd_per_jod or DEFAULT_USD_PER_JOD) if lyd_per_jod is not None else None
        self.card_currency = "USD" if lyd_per_jod is not None else None
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: **الوسيلةُ المختارة** (`for_method`) — تحصر الصفحةَ فيها
        self.method: str | None = None
        self.last_status: str | None = None
        self.last_received: str | None = None

    def for_method(self, code: str | None) -> DpayGateway:
        """**نسخةٌ محصورةٌ بوسيلة الصفّ** — صفٌّ بلا وسيلةٍ معروفةٍ لا يفتح صفحة (`GatewayUnavailable`)."""
        slug = slug_of(code)
        if slug is None:
            raise base.GatewayUnavailable()
        # **صفُّ الأردن لا يُفتح بلا سعر التحويل، وصفُّ ليبيا لا يُفتح بسعرٍ** — فلا يُطلب دينارٌ أردنيٌّ بعدده ديناراً ليبيّاً
        if bool((code or "").endswith("_jo")) != (self.lyd_per_jod is not None):
            raise base.GatewayUnavailable()
        bound = copy.copy(self)
        bound.method = slug
        return bound

    # ------------------------------------------------------------------ الشبكة

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        timeout: float = base.REQUEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._token}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:64]
        try:
            async with base.http_client(timeout) as http:
                response = await http.request(method, f"{self.base_url}{path}", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Dpay") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            detail = body.get("detail") or body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"Dpay: {detail}" if isinstance(detail, str) and detail else "رفض Dpay الطلب")
        data = body.get("data")
        if not isinstance(data, dict):
            raise base.GatewayError("جوابُ Dpay بلا بيانات")
        return data

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — قائمةُ الجلسات بمهلةٍ قصيرة (قراءةٌ بلا أثر)."""
        try:
            async with base.http_client(base.HEALTH_TIMEOUT_SECONDS) as http:
                response = await http.get(
                    f"{self.base_url}/checkout-sessions",
                    params={"per_page": 1},
                    headers={"Accept": "application/json", "Authorization": f"Bearer {self._token}"},
                )
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise base.GatewayDown()

    # ------------------------------------------------------------------ الدفعة

    def _session_amount(self, amount: Decimal) -> str:
        if self.lyd_per_jod is not None:
            return two_places(to_lyd(amount, self.lyd_per_jod))
        return two_places(amount)

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
        if self.method is None:
            # **لا صفحةَ بكلِّ الوسائل** — الدافعُ اختار وسيلةً في التطبيق، والصفحةُ تُحصر فيها
            raise base.GatewayUnavailable()
        charged = self._session_amount(amount)
        reference = (customer.order_ref or "")[:64]
        # **عنوانُ الإشعار يُضبط في لوحة Dpay مرّةً** — ولا بطاقةَ ولا رمزَ ولا هاتف: مرجعُ طلبنا والمبلغُ المختوم وحدَهما
        payload: dict[str, Any] = {
            "amount": charged,
            "currency": "LYD",
            "description": description[:255],
            "reference": reference,
            "return_url": return_url,
            "allowed_methods": [self.method],
            "expires_in_minutes": SESSION_MINUTES,
            "locale": "en" if locale == "en" else "ar",
            "metadata": {"order_ref": reference, "source": "taxo", "charge_lyd": charged, "method": self.method},
        }
        data = await self._request(
            "POST", "/checkout-sessions", payload, idempotency_key=f"taxo:{reference}:{self.method}" if reference else None
        )
        session_id = str(data.get("id") or "")
        url = data.get("url")
        if not session_id or not isinstance(url, str) or not url.startswith("https://"):
            raise base.GatewayError("جوابُ Dpay بلا معرّف جلسةٍ أو رابطِ صفحة")
        return base.Checkout(external_id=session_id, checkout_url=url)

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        self.last_status = None
        self.last_received = None
        data = await self._request("GET", f"/checkout-sessions/{external_id}")
        status = str(data.get("status") or "").lower()
        if status in ("expired", "cancelled"):
            # **انتهت أو أُلغيت بلا دفع** — رفضٌ بلا مال؛ والدافعُ يفتح جلسةً جديدة
            return base.GatewayEvent(
                external_id,
                PaymentRequestStatus.REJECTED,
                reason=reasons.GATEWAY_EXPIRED if status == "expired" else reasons.GATEWAY_CANCELLED,
                gateway_code=status[:32],
            )
        if status != "paid":
            # open — لم يُدفع بعد (أو محاولةٌ فشلت والجلسةُ ما زالت تقبل غيرَها)
            return None
        payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
        charged = _money(payment.get("amount_charged"))
        self.last_received = f"{charged} LYD" if charged is not None else None
        if not self._matches(data):
            # **جلسةٌ لا تطابق ما فتحناه** (مبلغٌ أو عملةٌ أو بيئةٌ أو وسيلة) — لا تُعتمد؛ تبقى معلّقةً ويحسمها المالكُ من اللوحة
            logger.error("Dpay: جلسةٌ مدفوعةٌ لا تطابق ما فُتح — لم تُعتمد (session=%s)", external_id)
            return None
        amount = None if self.lyd_per_jod is not None else _money(data.get("amount"))
        return base.GatewayEvent(
            external_id,
            PaymentRequestStatus.APPROVED,
            amount=amount,
            fee_on_customer=_money(payment.get("fee_amount")),
            gateway_code=str(payment.get("pay_method") or "")[:32] or None,
            gateway_message=self.last_received,
        )

    def _matches(self, data: Mapping[str, Any]) -> bool:
        """**ما دُفع هو ما فتحناه**: الليبيُّ عملةً، والبيئةُ بيئةَ العقد، والمبلغُ المختومُ في `metadata`، ووسيلةٌ من وسائلنا."""
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        if str(data.get("currency") or "").upper() != "LYD":
            return False
        if bool(data.get("live")) == self.test_mode:
            return False
        if _money(data.get("amount")) != _money(metadata.get("charge_lyd")):
            return False
        if metadata.get("order_ref") and data.get("reference") != metadata.get("order_ref"):
            return False
        payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
        return payment.get("pay_method") in METHOD_SLUGS

    async def details(self, external_id: str) -> dict[str, Any]:
        """**ما يقوله Dpay عن الجلسة** — للّوحة؛ ولا يُكتب منه شيء."""
        data = await self._request("GET", f"/checkout-sessions/{external_id}")
        payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
        return {
            "status": data.get("status"),
            "amount": data.get("amount"),
            "method": payment.get("pay_method"),
            "charged": payment.get("amount_charged"),
            "fee": payment.get("fee_amount"),
            "tx_id": payment.get("tx_id"),
            "attempts": [
                {"method": row.get("pay_method"), "status": row.get("status")}
                for row in data.get("attempts") or []
                if isinstance(row, dict)
            ],
        }

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        lowered = {key.lower(): value for key, value in headers.items()}
        stamp = (lowered.get("x-dpay-timestamp") or "").strip()
        offered = (lowered.get("x-dpay-signature") or "").strip().lower()
        if not stamp or not offered or not self._webhook_secret:
            raise base.WebhookSignatureInvalid()
        try:
            sent_at = int(stamp)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        if abs(time.time() - sent_at) > WEBHOOK_TOLERANCE_SECONDS:
            raise base.WebhookSignatureInvalid()
        expected = hmac.new(self._webhook_secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(offered, expected):
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        if not isinstance(payload, dict):
            return []
        # **أحداثُ الجلسة** تحمل معرّفَها في رأس الجسم، **وأحداثُ المحاولة** (`payment.*`) تحته في `data`
        session_id = payload.get("checkout_session_id")
        if not session_id and isinstance(payload.get("data"), dict):
            session_id = payload["data"].get("checkout_session_id")
        return [session_id] if isinstance(session_id, str) and session_id else []

    async def test_connection(self) -> str:
        await self._request("GET", "/checkout-sessions?per_page=1")
        mode = "تجربة (sandbox)" if self.test_mode else "حيّ"
        rate = f" · سعرُ التحويل: 1 د.أ = {self.lyd_per_jod} د.ل" if self.lyd_per_jod is not None else ""
        return f"الاتصالُ بـDpay يعمل — الوضع: {mode}{rate}"


# ------------------------------------------------------------------ مساعدات


def _money(value: Any) -> Decimal | None:
    """**مبلغٌ بمنزلتين** — الإشعارُ يرسله رقماً (`125.5`) والواجهةُ نصّاً (`"125.50"`): يُوحَّدان قبل المقارنة (توصيتُهم)."""
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return Decimal(text).quantize(Decimal("0.001"))
    except InvalidOperation:
        return None


def _positive(value: Any) -> Decimal | None:
    number = _money(value)
    return number if number is not None and number > 0 else None


def build_dpay(values: Mapping[str, Any]) -> DpayGateway:
    token = str(values.get("api_token") or "").strip()
    secret = str(values.get("webhook_secret") or "").strip()
    if not token or not secret:
        # **حتى يُدخل المالكُ الرمزَ والسرَّ تبقى الطرقُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    rate_text = str(values.get("lyd_per_jod") or "").strip()
    lyd_per_jod = None
    if rate_text:
        try:
            lyd_per_jod = Decimal(rate_text)
        except InvalidOperation as exc:
            raise base.GatewayUnavailable() from exc
        if lyd_per_jod <= 0:
            raise base.GatewayUnavailable()
    return DpayGateway(
        api_token=token,
        webhook_secret=secret,
        sandbox=credentials_service.is_on(values, "sandbox"),
        lyd_per_jod=lyd_per_jod,
        usd_per_jod=_positive(values.get("usd_per_jod")),
        daily_cap=_positive(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
    )
