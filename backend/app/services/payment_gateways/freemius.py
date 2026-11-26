"""**Freemius — بوّابةُ بطاقةٍ احتياطيّةٌ لاشتراك الكبتن في الأردن** (أمرُ المالك ٢٠٢٦-١١-٢٦، `design/OWNER-2026-11-26-FREEMIUS-BACKUP.md`).

**ما يجري**: أربعُ خططٍ عند Freemius بدفعةٍ واحدةٍ لا تتجدّد (دورةُ `lifetime` عندهم — **أي دفعةٌ واحدة، لا وصولٌ مدى الحياة**: مدّةُ
الاشتراك تحسبها TAXO من خطّتها) — واحدةٌ لكلِّ مبلغٍ يدفعه الكبتنُ الآن (3 · 17 · 45 · 60 د.أ) **بالدولار نفسِه الذي في Digistore24**
(`digistore24.PRICE_MAP` مصدرٌ واحد، فلا يفترق سعرا البوّابتين). وصفحةُ الدفع صفحتُهم المستضافة (`checkout.freemius.com`): **لا تمرّ بياناتُ
البطاقة بخوادمنا**، وFreemius البائعُ المسجَّل. **ورسمُه على TAXO** (قرارُ المالك): البطاقةُ تُخصم ثمنَ الخطّة وحدَه.

**حارسُ السعر** هو حارسُ Digistore24 حرفاً: لا يُفتح دفعٌ إلا لمبلغٍ مربوطٍ بخطّة؛ ومن يدفع 45 بعرض «TAXO MAN 45» يرى X30 ومن يدفع 60 يرى X30-FULL.

**والربطُ بطلبنا بالبريد لا بمرجع** — صفحةُ Freemius **لا تحمل حقلاً حرّاً يعود في الإشعار** (قِيس في `CheckoutPopupOptions` من شيفرتهم
الرسميّة ٢٠٢٦-١١-٢٧: لا `custom` ولا `metadata`). فالبريدُ يُملأ من الحساب **للقراءة وحدَها** (`readonly_user`) حين يكون الاسمُ كاملاً، والإشعارُ
يحمل `objects.user.email` وخطّةَ الدفعة، **والربطُ في `services/freemius_link.py`**: الطلبُ المعلَّقُ لصاحب هذا البريد بمبلغ هذه الخطّة،
**ثمّ يُكتب معرّفُ دفعة Freemius على الطلب** (`external_id = "fs:<id>"`) — فإعادةُ الإشعار تجد طلبَها نفسَه ولا تربط طلباً ثانياً.

**الإشعار**: `POST` جسمُه JSON، وتوقيعُه ترويسةُ `x-signature` = HMAC-SHA256 للجسم الخامّ بالمفتاح السرّيّ للمنتج، ستّةَ عشريّاً بحروفٍ صغيرة
(مثالُهم الرسميّ `php-webhook-example` و`WebhookListener.verifySignature` في `freemius-js`). **والمفتاحُ السرّيُّ لا يعرفه إلا Freemius ونحن**
— فالإشعارُ الموقَّعُ شهادةٌ (`confirms_by_webhook`)، ويُتحقَّق مع ذلك من المنتج والخطّة والعملة ووضع التجربة (`environment`) قبل أيِّ قيد.

**والاسترداد**: دفعةٌ نوعُها `refund` أو `chargeback` أو `lost_dispute` تحمل `bound_payment_id` للدفعة الأصل — فيُعكس طلبُها بقيدَين مقابلَين لا
بحذف (`payment_requests.reverse_gateway_refund`). والنزاعُ المفتوح (`disputed`) يُسجَّل ولا يُعكس قبل أن يُخسر.

**ووضعُ التجربة (sandbox)** رابطُه يحمل `s_ctx_ts` و`sandbox` = md5(الوقت + المنتج + السرّيّ + العامّ + «checkout») كما في
`CheckoutService.getSandboxParams` — **ولحسابات التجربة وحدَها** (`test_mode` في العقد، وحارسُ `_prepare`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.payment_gateways.digistore24 import PLANS, PRICE_MAP, product_for, split_name
from app.services.providers import credentials as credentials_service

logger = logging.getLogger(__name__)

API_BASE = "https://api.freemius.com/v1"
CHECKOUT_BASE = "https://checkout.freemius.com/product"
PARTNER_NAME = "Freemius"
CHARGE_CURRENCY = "USD"

#: **بادئةُ معرّف دفعة Freemius على طلبنا** — تميّزه من مرجعنا الذي كُتب عند فتح الصفحة
EXTERNAL_PREFIX = "fs:"

#: **أنواعُ الدفعة عند Freemius** (`PaymentType` في مخطّط واجهتهم)
KIND_PAYMENT = "payment"
_REVERSAL = frozenset({"refund", "chargeback", "lost_dispute"})
_DISPUTE_OPEN = "disputed"

_SIGNATURE = re.compile(r"[0-9a-fA-F]{64}")

#: **كم يبقى الإشعارُ الموقَّعُ في الذاكرة** — يكفي الربطَ والحسمَ المتزامنَين في الطلب نفسِه وإعادةَ الإشعار القريبة
_SEEN_TTL_SECONDS = 15 * 60
_SEEN: dict[str, tuple[float, dict[str, Any]]] = {}


def sign(body: bytes, secret_key: str) -> str:
    """**توقيعُ Freemius** — HMAC-SHA256 للجسم الخامّ بالمفتاح السرّيّ، ستّةَ عشريّاً بحروفٍ صغيرة."""
    return hmac.new(secret_key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def sandbox_token(timestamp: str, product_id: str, secret_key: str, public_key: str) -> str:
    """**رمزُ صفحة التجربة** — `getSandboxParams()` من `freemius-js` حرفاً."""
    return hashlib.md5(f"{timestamp}{product_id}{secret_key}{public_key}checkout".encode()).hexdigest()  # noqa: S324 — خوارزميّتُهم لا اختيارُنا


def remember(external_id: str, info: Mapping[str, Any]) -> None:
    now = time.monotonic()
    for key in [k for k, (at, _i) in _SEEN.items() if now - at > _SEEN_TTL_SECONDS]:
        _SEEN.pop(key, None)
    _SEEN[external_id] = (now, dict(info))


def recalled(external_id: str) -> dict[str, Any] | None:
    hit = _SEEN.get(external_id)
    if hit is None or time.monotonic() - hit[0] > _SEEN_TTL_SECONDS:
        return None
    return hit[1]


def external_of(payment_id: object) -> str:
    return f"{EXTERNAL_PREFIX}{payment_id}"


class FreemiusGateway:
    name = "freemius"
    #: **«دُفع» يُقيَّد من إشعارٍ موقَّعٍ متحقَّق وحدَه** — والعودةُ من الصفحة لا تفعّل شيئاً
    confirms_by_webhook = True
    #: **الاستردادُ بعد الاعتماد يُعكس آليّاً** بقيدَين مقابلَين (`payment_requests.reverse_gateway_refund`)
    reverses_refunds = True
    drivers_only = True
    #: **الربطُ بالبريد** — حسابٌ بلا بريدٍ لا تُفتح له الصفحة ويُقال له لماذا (`EmailRequired` في `start_checkout`)
    requires_email = True
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
        product_id: str,
        public_key: str,
        secret_key: str,
        api_token: str,
        plans: Mapping[str, str],
        test_mode: bool,
        daily_cap: Decimal | None = None,
        allowlist: frozenset[str] = frozenset(),
    ) -> None:
        self.product_id = product_id
        self._public = public_key
        self._secret = secret_key
        self._token = api_token
        #: الخطّة ⇐ معرّفُ الخطّة عند Freemius
        self.plans = dict(plans)
        self.test_mode = test_mode
        self.daily_cap = daily_cap
        self.allowlist = allowlist
        #: **المبالغُ التي يُفتح لها دفع** — يقرؤها التطبيقُ فيُظهر الزرَّ للخطّة التي يساويها ثمنُها الآن وحدَها
        self.fixed_amounts = tuple(sorted(amount for amount, (plan, _usd) in PRICE_MAP.items() if self.plans.get(plan)))
        self.last_status: str | None = None
        self.last_received: str | None = None

    # ------------------------------------------------------------------ الشبكة

    async def _get(self, path: str, *, timeout: float = base.REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._token}"}
        url = f"{API_BASE}/products/{quote(self.product_id, safe='')}{path}"
        try:
            async with base.http_client(timeout) as http:
                response = await http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        if response.status_code in (401, 403):
            raise base.GatewayError("Freemius رفض مفتاحَ الواجهة — راجع «API Token» في العقد")
        if response.status_code >= 400:
            raise base.GatewayError(f"Freemius: {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Freemius") from exc
        if not isinstance(body, dict):
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Freemius")
        return body

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** — المنتجُ نفسُه بمفتاح الواجهة بمهلةٍ قصيرة."""
        await self._get(".json", timeout=base.HEALTH_TIMEOUT_SECONDS)

    # ------------------------------------------------------------------ الدفعة

    def checkout_params(self, *, plan_id: str, customer: base.CheckoutCustomer, return_url: str) -> list[tuple[str, str]]:
        """**معاملاتُ الصفحة المستضافة** — الخطّةُ بدفعةٍ واحدة، والبريدُ والاسمُ من الحساب، **وما كان فارغاً لا يُرسل**.

        **والبريدُ للقراءة وحدَها حين يكون الاسمُ كاملاً** (`readonly_user`): به يُربط الدفعُ بطلبنا، فلا يُبدَّل في الصفحة. واسمٌ بكلمةٍ
        واحدةٍ لا يُقفل (لا اسمَ عائلةٍ مخترعاً)، **والشاشةُ تقول له أن يُبقي البريدَ كما هو**."""
        first, last = split_name(customer.full_name or "")
        pairs = [
            ("plan_id", plan_id), ("billing_cycle", "lifetime"), ("licenses", "1"), ("hide_licenses", "1"),
            ("currency", "usd"), ("user_email", customer.email or ""), ("user_firstname", first), ("user_lastname", last),
        ]
        if customer.email and first and last:
            pairs.append(("readonly_user", "1"))
        if return_url:
            pairs.append(("cancel_url", return_url))
        if self.test_mode:
            stamp = str(int(time.time()))
            pairs += [("s_ctx_ts", stamp), ("sandbox", sandbox_token(stamp, self.product_id, self._secret, self._public))]
        return [(key, value) for key, value in pairs if value]

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
        plan_id = self.plans.get(mapped[0]) if mapped else None
        if mapped is None or not plan_id:
            # **حارسُ السعر** — مبلغٌ غيرُ مربوطٍ بخطّةٍ لا يُفتح له دفع (عرضٌ انتهى، أو سعرٌ تبدّل في اللوحة)
            raise base.GatewayError("هذا المبلغُ لا يُدفع بالبطاقة الآن — ادفع بطريقةٍ أخرى")
        ref = customer.order_ref or ""
        if not ref:
            raise base.GatewayError("طلبٌ بلا مرجع")
        if not customer.email:
            raise base.GatewayError("لا بريدَ في الحساب — أضفه ثمّ ادفع")
        query = urlencode(self.checkout_params(plan_id=plan_id, customer=customer, return_url=return_url))
        url = f"{CHECKOUT_BASE}/{quote(self.product_id, safe='')}/?{query}"
        return base.Checkout(external_id=ref, checkout_url=url)

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        """**ما قاله الإشعارُ الموقَّعُ لهذه الدفعة** — بعد التحقّق من خطّتها وعملتها؛ و`None` ما لم يصل إشعارٌ أو لم يُربط الطلبُ بدفعة."""
        self.last_status = None
        self.last_received = None
        if not external_id.startswith(EXTERNAL_PREFIX):
            return None
        info = recalled(external_id)
        if info is None:
            return None
        payment_id = str(info.get("payment_id") or "")[:40]
        received = info.get("received")
        self.last_received = received
        note = f"Freemius payment {payment_id}" + (f" · {received}" if received else "")
        kind = info.get("kind")
        if kind in _REVERSAL:
            return base.GatewayEvent(
                external_id, PaymentRequestStatus.REFUNDED, reason=reasons.CARD_REFUNDED, gateway_code=f"payment.{kind}"[:32],
                gateway_message=note,
            )
        if kind != KIND_PAYMENT:
            return None
        plan_id = str(info.get("plan_id") or "")
        if plan_id not in self.plans.values():
            logger.error("Freemius: دفعةٌ لخطّةٍ ليست لنا (%s) — لم تُقيَّد (payment=%s)", plan_id, payment_id)
            return None
        currency = str(info.get("currency") or CHARGE_CURRENCY).upper()
        if currency != CHARGE_CURRENCY:
            logger.error("Freemius: دفعةٌ بعملة %s — لم تُقيَّد (payment=%s)", currency, payment_id)
            return None
        # **المبلغُ بالدينار الذي تربطه هذه الخطّة** — فيقارنه الحسمُ بمبلغ طلبنا (`apply_gateway_outcome`)
        return base.GatewayEvent(
            external_id, PaymentRequestStatus.APPROVED, amount=self.amount_of(plan_id), gateway_code="payment.created",
            gateway_message=note,
        )

    def amount_of(self, plan_id: str) -> Decimal | None:
        """**المبلغُ بالدينار المربوطُ بخطّةٍ من خططنا** — `None` لغيرها."""
        for amount, (plan, _usd) in PRICE_MAP.items():
            if self.plans.get(plan) == plan_id:
                return amount
        return None

    def pending_binding(self, external_id: str) -> dict[str, Any] | None:
        """**ما يلزم ربطَ دفعةٍ جديدةٍ بطلبها** — بريدُ الدافع ومبلغُ خطّته بالدينار؛ و`None` لاستردادٍ أو لما لم يُتذكَّر."""
        info = recalled(external_id)
        if info is None or info.get("kind") != KIND_PAYMENT:
            return None
        return {"email": str(info.get("email") or "").strip().lower(), "amount": self.amount_of(str(info.get("plan_id") or ""))}

    # ------------------------------------------------------------------ الإشعار

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        offered = (headers.get("x-signature") or "").strip()
        if not self._secret or not _SIGNATURE.fullmatch(offered):
            raise base.WebhookSignatureInvalid()
        if not hmac.compare_digest(offered.lower(), sign(body, self._secret)):
            raise base.WebhookSignatureInvalid()
        try:
            event = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            logger.error("Freemius: إشعارٌ موقَّعٌ بجسمٍ لا يُقرأ")
            return []
        if not isinstance(event, dict):
            return []
        objects = event.get("objects") if isinstance(event.get("objects"), dict) else {}
        payment = objects.get("payment") if isinstance(objects.get("payment"), dict) else None
        if payment is None:
            # **حدثٌ بلا دفعة** (تثبيت، ترخيص، مستخدم…) — يُجاب بنجاحٍ ولا يُقرأ منه شيء
            return []
        event_type = str(event.get("type") or "")
        plugin = str(event.get("plugin_id") or payment.get("plugin_id") or "")
        if plugin and plugin != self.product_id:
            logger.error("Freemius: إشعارٌ لمنتجٍ ليس لنا (%s، الحدث %s) — لم يُقرأ", plugin, event_type)
            return []
        sandbox = str(payment.get("environment", "0")) == "1"
        if sandbox != self.test_mode:
            # **مالٌ تجريبيٌّ على عقدٍ حيّ أو حيٌّ على عقد تجربة** — لا يُربط ولا يُقيَّد، ويراه المالكُ في السجلّ
            logger.error("Freemius: دفعةٌ بوضع %s على عقدٍ %s — لم تُقيَّد (payment=%s)",
                         "تجربة" if sandbox else "حيّ", "تجربة" if self.test_mode else "حيّ", payment.get("id"))
            return []
        kind = str(payment.get("type") or KIND_PAYMENT)
        user = objects.get("user") if isinstance(objects.get("user"), dict) else {}
        info = {
            "kind": kind, "payment_id": payment.get("id"), "plan_id": payment.get("plan_id"),
            "currency": payment.get("currency"), "email": user.get("email") or "", "received": _received(payment),
        }
        if kind == KIND_PAYMENT:
            if not payment.get("id"):
                return []
            external_id = external_of(payment["id"])
        elif kind in _REVERSAL:
            bound = payment.get("bound_payment_id")
            if not bound:
                logger.error("Freemius: استردادٌ بلا دفعةٍ أصل (payment=%s)", payment.get("id"))
                return []
            external_id = external_of(bound)
        else:
            if kind == _DISPUTE_OPEN:
                logger.warning("Freemius: نزاعٌ مفتوحٌ على الدفعة %s — لا يُعكس قبل أن يُخسر", payment.get("bound_payment_id"))
            return []
        remember(external_id, info)
        return [external_id]

    async def test_connection(self) -> str:
        product = await self._get(".json")
        mode = "تجربة" if self.test_mode else "حيّ"
        missing = [plan for plan in PLANS if not self.plans.get(plan)]
        tail = f" · خططٌ ناقصة: {', '.join(missing)}" if missing else " · الخططُ الأربع مضبوطة"
        title = str(product.get("title") or "")[:60]
        return f"الاتصالُ بـFreemius يعمل — المنتج: {title} · الوضع: {mode}{tail}"


# ------------------------------------------------------------------ مساعدات


def _received(payment: Mapping[str, Any]) -> str | None:
    gross = payment.get("gross")
    if gross in (None, ""):
        return None
    return f"{gross} {str(payment.get('currency') or CHARGE_CURRENCY).upper()}"[:60]


def _decimal(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number > 0 else None


def build_freemius(values: Mapping[str, Any]) -> FreemiusGateway:
    product_id = str(values.get("product_id") or "").strip()
    public_key = str(values.get("public_key") or "").strip()
    secret_key = str(values.get("secret_key") or "").strip()
    api_token = str(values.get("api_token") or "").strip()
    plans = {plan: str(values.get(f"plan_{plan}") or "").strip() for plan in PLANS}
    if not product_id or not public_key or not secret_key or not api_token or not any(plans.values()):
        # **حتى يُدخل المالكُ المنتجَ والمفاتيحَ وخطّةً واحدةً على الأقلّ تبقى الطريقةُ مخفيّة** — كعقدٍ غائب
        raise base.GatewayUnavailable()
    raw_allow = str(values.get("allowlist") or "")
    return FreemiusGateway(
        product_id=product_id,
        public_key=public_key,
        secret_key=secret_key,
        api_token=api_token,
        plans={plan: pid for plan, pid in plans.items() if pid},
        test_mode=credentials_service.is_on(values, "test_mode"),
        daily_cap=_decimal(values.get("daily_cap")),
        allowlist=frozenset(part.strip() for part in raw_allow.split(",") if part.strip()),
    )
