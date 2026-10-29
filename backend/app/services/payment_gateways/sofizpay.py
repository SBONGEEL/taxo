"""**SofizPay** — بطاقةُ CIB عبر SATIM (SPEC §٧٣-هـ المرحلة ٣)، **بوثائقه المنشورة** في `docs.sofizpay.com` (قُرئت ٢٠٢٦-١٠-١١).

**ما أُخذ من الوثائق حرفاً**:
- `GET https://sofizpay.com/make-cib-transaction/` (و`/sandbox/make-cib-transaction/` للتجربة) بـ`account` و`amount` و`full_name` و`phone`
  و`email` (إلزاميّةٌ كلُّها) و`return_url` و`webhook_url` و`memo` (حتى ٢٨ بايتاً) و`redirect`؛ ويعود بـ`success` و`cib_transaction_id`
  و`payment_url`.
- `GET https://sofizpay.com/cib-transaction-check/?order_number=…` ⇐ `orderStatus` (`2` مقبول · `6` مرفوض) و`respCode` (`"00"` مقبول) و
  `destination_account` و`Amount`.
- إشعارُ `cib.payment.updated` بـ`cib_transaction_id` و`order_number` و`message` و`signature`.

**وتوقيعُ الإشعار** (SPEC §٨٧/٥، أمرُ المالك ٢٠٢٦-١٠-٢٨) — **بطريقة SDK الرسميّ** (`sofizpay-sdk-python` 1.0.2،
`SofizPayClient.verify_sofizpay_signature`): **RSA PKCS#1 v1.5 بـSHA-256** على نصِّ `message` كما وصل، بمفتاح SofizPay **العامّ** المنشور
في الـSDK (`SOFIZPAY_PUBLIC_KEY_PEM` أدناه — مفتاحٌ عامٌّ لا سرّ)، والتوقيعُ Base64 أو Base64 الآمنُ للعناوين. **إشعارٌ بلا توقيعٍ أو
بتوقيعٍ لا يطابق يُرَدّ `401`** ولا يُقرأ منه حرف. **والحقيقةُ تبقى من بابِ الفحص** — مقبولٌ برمزيه، **وحسابُ الوجهة حسابُنا، والمبلغُ
مبلغُ الطلب**: الإشعارُ الموقَّعُ يوقظ التسويةَ ولا يقيِّد بنفسه (`confirms_by_webhook = False` كما كان)، **وما رُدَّ بتوقيعه تحسمه
التسويةُ الدوريّةُ وعودةُ التطبيق** فلا يضيع مالٌ بإشعارٍ مردود.

**وما لم تقله الوثائق — ولم يُخمَّن** (يُذكر في التقرير ويُطلب من SofizPay):
1. **أيُّ حقولٍ يجمعها `message`** — لا يلزمنا: التوقيعُ على النصِّ كما وصل، ولا يُقرأ منه إلا المعرّف.
2. **مصادقةُ الطلبات** — لا مفتاحَ يُرسل في الوثائق؛ والحسابُ (`account`) معرّفُ التاجر.
3. **تحميلُ الرسوم على المشتري** — لا معاملَ له؛ فرسومُه على TAXO وحدَها (`FEE_BEARERS`).
4. **بابٌ لاختبار الاتصال بلا أثر** — لا يوجد؛ فزرُّ الاختبار يقول ذلك ولا يفتح دفعةً ليختبر.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services import payment_reasons as reasons
from app.services.providers import credentials as credentials_service

BASE = "https://sofizpay.com"

#: **مفتاحُ SofizPay العامُّ للتوقيع** — منسوخٌ حرفاً من الـSDK الرسميّ (`sofizpay/client.py`، الإصدار 1.0.2). **عامٌّ لا سرّ**: به يُتحقَّق
#: من أن الإشعارَ من SofizPay، ولا يوقّع شيئاً
SOFIZPAY_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1N+bDPxpqeB9QB0affr/
02aeRXAAnqHuLrgiUlVNdXtF7t+2w8pnEg+m9RRlc+4YEY6UyKTUjVe6k7v2p8Jj
UItk/fMNOEg/zY222EbqsKZ2mF4hzqgyJ3QHPXjZEEqABkbcYVv4ZyV2Wq0x0ykI
+Hy/5YWKeah4RP2uEML1FlXGpuacnMXpW6n36dne3fUN+OzILGefeRpmpnSGO5+i
JmpF2mRdKL3hs9WgaLSg6uQyrQuJA9xqcCpUmpNbIGYXN9QZxjdyRGnxivTE8awx
THV3WRcKrP2krz3ruRGF6yP6PVHEuPc0YDLsYjV5uhfs7JtIksNKhRRAQ16bAsj/
9wIDAQAB
-----END PUBLIC KEY-----"""


def verify_signature(message: str, signature: str, *, public_key_pem: bytes | None = None) -> bool:
    """**طريقةُ الـSDK الرسميّ حرفاً** (`verify_sofizpay_signature`): Base64 الآمنُ يُعاد عاديّاً ويُكمَّل حشوُه، ثمّ RSA PKCS#1 v1.5 بـSHA-256."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    if not message or not signature:
        return False
    normal = signature.strip().replace("-", "+").replace("_", "/")
    normal += "=" * (-len(normal) % 4)
    try:
        raw = base64.b64decode(normal, validate=True)
        key = serialization.load_pem_public_key(public_key_pem or SOFIZPAY_PUBLIC_KEY_PEM)
        key.verify(raw, message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr,call-arg]
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _payload(body: bytes) -> dict[str, Any]:
    """**الإشعارُ JSON أو نموذجٌ مرمَّز** — الوثائقُ لا تقطع، فيُقرأ الاثنان؛ وما عداهما فارغ."""
    try:
        parsed = json.loads(body)
    except ValueError:
        from urllib.parse import parse_qs

        try:
            form = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            return {}
        return {k: v[0] for k, v in form.items() if v}
    return parsed if isinstance(parsed, dict) else {}


class SofizPayGateway:
    name = "sofizpay"
    #: **إشعارُه بلا توقيعٍ موثَّق** — فالفحصُ المباشرُ يحسم كما بُني (§٧٣-هـ المرحلة ٣)
    confirms_by_webhook = False

    def __init__(
        self, *, account: str, sandbox: bool, fallback_only: bool = False, allowlist: frozenset[str] = frozenset()
    ) -> None:
        self.account = account
        self.sandbox = sandbox
        self.test_mode = sandbox
        #: **«بديلٌ حين يتوقّف Chargily»** (§٨٥/٢) — يُعرض للدافع حين يكون Chargily متوقّفاً وحدَه؛ وإلا فالاثنان معاً
        self.fallback_only = fallback_only
        #: **قائمةُ السماح** (أمرُ المالك ٢٠٢٦-١٠-٢٩) — غيرُ فارغةٍ ⇐ لا يرى الطريقةَ ولا يفتح صفحتَها إلا من فيها (`allowed_for`)
        self.allowlist = allowlist

    def _path(self, path: str) -> str:
        return f"/sandbox{path}" if self.sandbox else path

    async def _get(
        self, path: str, params: dict[str, str], *, timeout: float = base.REQUEST_TIMEOUT_SECONDS
    ) -> dict[str, Any]:
        try:
            async with base.http_client(timeout) as http:
                response = await http.get(f"{BASE}{path}", params=params, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            # **مهلةٌ أو انقطاع** — الوسيطُ متوقّفٌ أو بطيءٌ جدّاً، لا رافضٌ لطلبنا (§٨٢-أ/١ بقاعدته)
            raise base.GatewayDown() from exc
        if response.status_code >= 500:
            raise base.GatewayDown()
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من SofizPay") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"SofizPay: {message}" if message else "رفض SofizPay الطلب")
        return body

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
        if not customer.email:
            # **البريدُ إلزاميٌّ عند SofizPay** — ولا يُخترع بريدٌ لصاحب الدفعة
            raise base.GatewayError("SofizPay يشترط بريداً إلكترونيّاً في حسابك — أضفه أو اختر طريقةً أخرى")
        body = await self._get(
            self._path("/make-cib-transaction/"),
            {
                "account": self.account,
                "amount": str(int(amount)),
                "full_name": customer.full_name,
                "phone": customer.phone,
                "email": customer.email,
                "return_url": return_url,
                "webhook_url": webhook_url,
                "memo": description.encode()[:28].decode(errors="ignore"),
                "redirect": "no",
            },
        )
        cib_id, url = body.get("cib_transaction_id"), body.get("payment_url")
        if body.get("success") is not True or cib_id in (None, "") or not isinstance(url, str):
            raise base.GatewayError("جوابُ SofizPay بلا معرّفٍ أو رابط")
        return base.Checkout(external_id=str(cib_id), checkout_url=url)

    async def health(self) -> None:
        """**فحصٌ قبل فتح الصفحة** (§٨٥/١) — بابُ الفحص بمعرّفٍ لا يوجد: **أيُّ جوابٍ مقروءٍ يعني أنه قائم** (ولو «غيرُ موجود»)،
        والمهلةُ أو `5xx` ⇐ `GatewayDown`. لا يفتح دفعةً ولا يمسّ مالاً."""
        try:
            await self._get(self._path("/cib-transaction-check/"), {"order_number": "0"}, timeout=base.HEALTH_TIMEOUT_SECONDS)
        except base.GatewayDown:
            raise
        except base.GatewayError:
            return

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        try:
            body = await self._get(self._path("/cib-transaction-check/"), {"order_number": external_id})
        except base.GatewayDown:
            raise
        except base.GatewayError:
            # **«غيرُ موجودة» ليست رفضاً** — صفحةٌ لم يبدأها الدافعُ بعد لا تُسجَّل؛ والمهلةُ تحسمها لا هذا الجواب
            return None
        if body.get("error"):
            return None
        status = body.get("orderStatus")
        if status == 2 and body.get("respCode") == "00":
            # **حسابُ الوجهة حسابُنا** — دفعةٌ مقبولةٌ إلى حسابٍ آخر ليست دفعةً لنا ولو حملت المعرّف
            if body.get("destination_account") != self.account:
                return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason="وصلت الدفعةُ حساباً غيرَ حساب TAXO")
            try:
                amount = Decimal(str(body.get("Amount")))
            except (InvalidOperation, ValueError):
                amount = None
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, amount=amount)
        if status == 6:
            # **السببُ من بيت الأسباب لا من البنك** (قِيس في وضع التجربة ٢٠٢٦-١٠-٢٩): `respCode_desc` فرنسيّةُ SATIM («Refusée») — كانت
            # تُكتب كما هي فيقرؤها الراكبُ العربيّ بلغةٍ لا يطلبها؛ ونصُّ البنك يبقى في السجلّ لا في الشاشة
            return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason=reasons.GATEWAY_FAILED)
        if status == 3:
            # **`3` حالٌ نهائيّةٌ لا «قيد الفحص»** (قِيس في وضع التجربة ٢٠٢٦-١٠-٢٩، ولم تذكره الوثائق): زرُّ «إلغاء» في صفحة الدفع
            # (`respCode` ‏17) وبطاقةُ المهلة (‏68) كلاهما `orderStatus 3` — وكان يُترك معلّقاً حتى مهلتنا فيرى الدافعُ «ننتظر» لدفعةٍ ألغاها
            expired = body.get("respCode") == "68"
            return base.GatewayEvent(
                external_id,
                PaymentRequestStatus.CANCELLED,
                reason=reasons.GATEWAY_EXPIRED if expired else reasons.GATEWAY_CANCELLED,
            )
        return None

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        """**التوقيعُ أوّلاً بطريقة الـSDK الرسميّ** (رأسُ الملفّ) — وما لا يطابق `401`؛ **ثمّ المعرّفُ وحدَه، والفحصُ المباشرُ يقرّر**."""
        payload = _payload(body)
        message, signature = payload.get("message"), payload.get("signature")
        if not isinstance(message, str) or not isinstance(signature, str) or not verify_signature(message, signature):
            raise base.WebhookSignatureInvalid()
        external = payload.get("cib_transaction_id") or payload.get("order_number")
        return [str(external)] if external not in (None, "") else []

    async def test_connection(self) -> str:
        return (
            "لا بابَ في وثائق SofizPay يختبر الاتصالَ بلا أن يفتح دفعة — العقدُ محفوظٌ ولم يُقَس الاتصال. "
            "جرّب دفعةً بوضع التجربة (sandbox) من التطبيق."
        )


def build_sofizpay(values: Mapping[str, Any]) -> SofizPayGateway:
    account = str(values.get("account") or "").strip()
    if not account:
        raise base.GatewayUnavailable("لا حسابَ في عقد SofizPay")
    return SofizPayGateway(
        account=account,
        sandbox=credentials_service.is_on(values, "sandbox"),
        fallback_only=credentials_service.is_on(values, "fallback_only"),
        allowlist=frozenset(p.strip() for p in str(values.get("allowlist") or "").replace("\n", ",").split(",") if p.strip()),
    )
