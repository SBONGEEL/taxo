"""مُحوِّل Telr — **الملف الوحيد في المشروع الذي يعرف شكل أسلاك Telr**.

أسماء الحقول، صيغة التوقيع، أرقام حالات الطلب، عناوين الخدمة: كلها هنا ولا
تظهر في أي ملف آخر. ما عدا هذا الملف يتكلم `base.CardGateway` وحده، فتصحيحُ
تفصيلٍ من تفاصيل المزود تعديلُ سطرٍ في مكانٍ واحد لا مطاردةٌ في الطبقات.

> **ملاحظة تنفيذية صريحة.** SPEC القسم 6.4 ينص على أن رابط توثيق Telr الرسمي
> يُسلَّم في جلسة التنفيذ، ولم يُسلَّم، ولا بيانات Sandbox في البيئة. فثلاثة
> تفاصيل هنا **مبنيّة على أفضل قراءةٍ لواجهة Telr العامة وتحتاج مطابقةً
> بالتوثيق الرسمي قبل أول تشغيل حقيقي**، وهي مجموعةٌ في ثوابت مسمّاة أعلى
> الملف كي تُطابَق في دقائق:
>
> 1. `TRAN_CHECK_FIELDS` — ترتيب حقول توقيع الإشعار.
> 2. `SAVED_CARD_*` — أسماء حقول الخصم على بطاقة محفوظة.
> 3. `_card_from_check` — موضع رمز البطاقة في جواب `check`.
>
> وخطؤها **لا يحرّك مالاً خطأً**: توقيعٌ لا يطابق يرفض الإشعار (400 صريح
> يُرى في السجل)، ومسار «استعلم عن طلبي» يبقى يسوّي العملية بجواب `check`؛
> وخصمٌ على بطاقة محفوظة يفشل يرتدّ 502 قبل أي قيد. البابُ الذي يمر منه المال
> واحدٌ لا ثلاثة: `check_order`.

المزود الوهمي (`mock.py`) هو ما تُختبر عليه المرحلة كلها، وهو نفسه ما تصفه
SPEC القسم 15: «تُبنى كاملة الآن ضد واجهة مزود موحدة مع مزود وهمي للاختبار».
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import httpx

from app.models.enums import Currency, PaymentProvider
from app.services.card_gateway.base import (
    REQUEST_TIMEOUT_SECONDS,
    CardDetails,
    CardGatewayError,
    HostedPage,
    InvalidWebhookSignature,
    OrderRequest,
    OrderState,
    WebhookNotice,
)

ORDER_URL = "https://secure.telr.com/gateway/order.json"
# الخصم المباشر على بطاقة محفوظة لا يمر بصفحةٍ مستضافة، فله عنوانه
REMOTE_URL = "https://secure.telr.com/gateway/remote.json"

# رموز حالة الطلب لدى Telr. `1` وحدها «لم يُحسم»: الراكب على الصفحة أو البنك
# لم يجب بعد. ما دونها حسمٌ بالرفض، وما فوقها حسمٌ بالقبول.
STATUS_EXPIRED = -3
STATUS_CANCELLED = -2
STATUS_DECLINED = -1
STATUS_PENDING = 1
STATUS_AUTHORISED = 2
STATUS_PAID = 3

PAID_STATUSES = frozenset({STATUS_AUTHORISED, STATUS_PAID})

# (1) ترتيب حقول توقيع الإشعار: SHA-1 على قيمها موصولةً بنقطتين، ومفتاح
#     المصادقة أولُها. الترتيب هو كل ما يمكن أن يختلف عن التوثيق — القيم
#     تأتي من الحمولة نفسها، والخطأ فيه يرفض كل إشعار ولا يقبل واحداً زائفاً.
TRAN_CHECK_FIELDS: tuple[str, ...] = (
    "tran_store",
    "tran_type",
    "tran_class",
    "tran_test",
    "tran_ref",
    "tran_prevref",
    "tran_firstref",
    "tran_currency",
    "tran_amount",
    "tran_cartid",
    "tran_status",
    "tran_authcode",
    "tran_authmessage",
)
CHECK_FIELD = "tran_check"
STORE_FIELD = "tran_store"
CART_FIELD = "tran_cartid"
REF_FIELD = "tran_ref"

# (2) حقول الخصم على بطاقة محفوظة
SAVED_CARD_METHOD = "sale"
SAVED_CARD_TOKEN_FIELD = "card_token"


def _flag(value: object) -> str:
    return "1" if value in (True, "1", 1, "true", "True") else "0"


class TelrGateway:
    """عقدُ متجرٍ واحد لدى Telr — يُبنى من قيم العقد المشفّرة لا من `.env`."""

    provider = PaymentProvider.TELR

    def __init__(
        self,
        *,
        store_id: str,
        auth_key: str,
        test_mode: bool,
        webhook_base_url: str | None = None,
    ) -> None:
        self._store_id = str(store_id).strip()
        self._auth_key = str(auth_key).strip()
        self._test_mode = test_mode
        self._webhook_base_url = webhook_base_url

    @property
    def store_id(self) -> str:
        return self._store_id

    # -------------------------------------------------------------- النداء

    def _credentials(self, method: str) -> dict[str, str]:
        return {
            "ivp_method": method,
            "ivp_store": self._store_id,
            "ivp_authkey": self._auth_key,
            "ivp_test": _flag(self._test_mode),
        }

    async def _post(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        """نداء واحد للمزود — نقطة الحقن الوحيدة في الاختبارات.

        نفس نهج `directions.fetch_route`: يُستبدل النداء وحده فتبقى قراءةُ
        العقد من `provider_credentials` حقيقية.
        """
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.post(url, data=data)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise CardGatewayError() from exc
        except ValueError as exc:  # جواب ليس JSON
            raise CardGatewayError("جواب مزود الدفع غير مقروء") from exc

        if not isinstance(payload, dict):
            raise CardGatewayError("جواب مزود الدفع غير مقروء")

        error = payload.get("error")
        if error:
            # نصُّ المزود يُعرض للمستخدم؛ `note` تفصيلٌ تشخيصي لا يُعرض
            message = (error.get("message") if isinstance(error, dict) else None) or ""
            raise CardGatewayError(
                f"مزود الدفع رفض العملية: {message}" if message else None
            )
        return payload

    # ------------------------------------------------------------- الإنشاء

    async def create_hosted_page(self, order: OrderRequest) -> HostedPage:
        data = self._credentials("create") | {
            "ivp_cart": order.cart_id,
            "ivp_amount": str(order.amount),
            "ivp_currency": order.currency.value,
            "ivp_desc": order.description,
            "return_auth": order.return_url,
            "return_can": order.return_url,
            "return_decl": order.return_url,
            "ivp_lang": "ar",
            "bill_custref": order.customer_ref,
            "bill_fname": order.customer_name,
            "bill_phone": order.customer_phone,
        }
        if order.save_card:
            data["ivp_savecard"] = "1"

        payload = await self._post(ORDER_URL, data)
        block = payload.get("order")
        ref = (block or {}).get("ref")
        url = (block or {}).get("url")
        if not ref or not url:
            raise CardGatewayError("مزود الدفع لم يعد برابط صفحة الدفع")
        return HostedPage(provider_order_ref=str(ref), redirect_url=str(url))

    # ------------------------------------------------------------ الاستعلام

    async def check_order(self, provider_order_ref: str) -> OrderState:
        payload = await self._post(
            ORDER_URL, self._credentials("check") | {"order_ref": provider_order_ref}
        )
        return self._state_from_order_block(provider_order_ref, payload.get("order"))

    def _state_from_order_block(
        self, provider_order_ref: str, block: Any
    ) -> OrderState:
        if not isinstance(block, dict):
            raise CardGatewayError("جواب مزود الدفع لا يحمل حال الطلب")

        status = block.get("status") or {}
        try:
            code = int(status.get("code"))
        except (TypeError, ValueError) as exc:
            raise CardGatewayError("حال الطلب عند المزود غير مقروءة") from exc

        transaction = block.get("transaction") or {}
        return OrderState(
            provider_order_ref=str(block.get("ref") or provider_order_ref),
            # ما ليس `pending` محسوم؛ ورمزٌ لا نعرفه يُحسب غير محسوم فلا يُسوّى
            settled=code != STATUS_PENDING and code in _KNOWN_STATUSES,
            paid=code in PAID_STATUSES,
            status_text=str(status.get("text") or code),
            amount=_decimal_or_none(block.get("amount")),
            currency=(str(block["currency"]) if block.get("currency") else None),
            card=self._card_from_check(block.get("card")),
            transaction_ref=(
                str(transaction.get("ref")) if transaction.get("ref") else None
            ),
        )

    def _card_from_check(self, block: Any) -> CardDetails | None:
        """(3) رمز البطاقة وبياناتها المعروضة من جواب `check`.

        Telr يعيد كتلة `card` بعد نجاح العملية. لا نقرأ منها إلا ما يجوز حفظه
        (SPEC القسم 4): الرمز والعلامة وآخر أربعة والانتهاء — ولا first6 ولا
        أيَّ بيانٍ آخر ولو أرسله المزود.
        """
        if not isinstance(block, dict):
            return None
        expiry = block.get("expiry") or {}
        return CardDetails(
            token=_str_or_none(block.get("token")),
            brand=_str_or_none(block.get("type")),
            last4=_str_or_none(block.get("last4")),
            expiry_month=_int_or_none(expiry.get("month")),
            expiry_year=_int_or_none(expiry.get("year")),
        )

    # -------------------------------------------------------- الدفع بضغطة

    async def charge_saved_card(
        self, order: OrderRequest, card_token: str
    ) -> OrderState:
        """خصمٌ مباشر بلا صفحة — يُحسم في نداء واحد فيعود بحالٍ نهائية."""
        payload = await self._post(
            REMOTE_URL,
            self._credentials(SAVED_CARD_METHOD)
            | {
                "ivp_cart": order.cart_id,
                "ivp_amount": str(order.amount),
                "ivp_currency": order.currency.value,
                "ivp_desc": order.description,
                "bill_custref": order.customer_ref,
                SAVED_CARD_TOKEN_FIELD: card_token,
            },
        )
        return self._state_from_order_block(order.cart_id, payload.get("order"))

    # ------------------------------------------------------------ الاسترداد

    async def refund_order(
        self, provider_order_ref: str, amount: Decimal, currency: Currency, reason: str
    ) -> str:
        payload = await self._post(
            ORDER_URL,
            self._credentials("refund")
            | {
                "order_ref": provider_order_ref,
                "ivp_amount": str(amount),
                "ivp_currency": currency.value,
                "ivp_desc": reason,
            },
        )
        block = payload.get("order") or {}
        transaction = block.get("transaction") or {}
        return str(transaction.get("ref") or block.get("ref") or provider_order_ref)

    # -------------------------------------------------------------- التوقيع

    def expected_check(self, payload: Mapping[str, str]) -> str:
        """التوقيع كما نحسبه: SHA-1 على مفتاح العقد ثم حقول الإشعار بترتيبها."""
        parts = [self._auth_key]
        parts += [str(payload.get(field, "") or "") for field in TRAN_CHECK_FIELDS]
        return hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()

    def verify_webhook(self, payload: Mapping[str, str]) -> WebhookNotice:
        """يفشل مغلقاً: إشعارٌ بلا توقيعٍ مطابقٍ لا يُقرأ منه شيء (SPEC القسم 14)."""
        received = str(payload.get(CHECK_FIELD, "") or "")
        cart_id = str(payload.get(CART_FIELD, "") or "")
        ref = str(payload.get(REF_FIELD, "") or "")

        if not received or not cart_id:
            raise InvalidWebhookSignature("إشعار الدفع ناقص الحقول")
        # المقارنة بزمنٍ ثابت: توقيعٌ يُقارن حرفاً حرفاً يُخمَّن حرفاً حرفاً
        if not hmac.compare_digest(
            received.lower(), self.expected_check(payload).lower()
        ):
            raise InvalidWebhookSignature()

        return WebhookNotice(cart_id=cart_id, provider_order_ref=ref)


_KNOWN_STATUSES = frozenset(
    {
        STATUS_EXPIRED,
        STATUS_CANCELLED,
        STATUS_DECLINED,
        STATUS_PENDING,
        STATUS_AUTHORISED,
        STATUS_PAID,
    }
)


def _str_or_none(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _decimal_or_none(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except (TypeError, ValueError, ArithmeticError):
        return None
