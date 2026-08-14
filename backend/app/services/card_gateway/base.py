"""واجهة مزود الدفع بالبطاقة — العقد الذي يتكلمه كل ما عدا المزود نفسه.

نفس نهج `services/auth/`: الراوترات والخدمات تعتمد على **الواجهة** لا على مزود
بعينه، فتبديل المزود أو تشغيل مزودٍ وهمي لا يمس مساراً واحداً (SPEC القسم 15).

القاعدة التي تحكم كل هذا الملف: **لا يُصدَّق العميل في شأن المال، ولا تُصدَّق
حمولة الـ webhook**. الحمولة إشارةُ استيقاظ لا مصدرَ حقيقة؛ الحقيقةُ جوابُ
`check_order` الذي يأتي من المزود إلى الخلفية مباشرة، وعليه وحده يتحرك الدفتر.
لذلك `WebhookNotice` لا تحمل مبلغاً: لو حملته لأصبح مبلغٌ مُرسَلٌ من الشبكة
قابلاً لأن يُقيَّد.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.exceptions import AppError
from app.models.enums import Currency, PaymentProvider

# مهلة كل نداء للمزود. أقصر من مهلة العميل بهامشٍ يكفي لتسجيل الفشل
REQUEST_TIMEOUT_SECONDS = 20.0


# ------------------------------------------------------------------ الأخطاء


class CardGatewayUnavailable(AppError):
    """لا عقد مزود بطاقات مُدخل أو مفعّل لهذه الدولة من صفحة العقود.

    503 لا 501: الميزة مبنية والعقد غائب — نفس منطق `RoutingUnavailable`.
    """

    status_code = 503
    code = "card_gateway_unavailable"
    message = "الدفع بالبطاقة غير متاح الآن — اختر طريقة دفع أخرى."


class CardGatewayError(AppError):
    """المزود ردّ بخطأ، أو تعذّر الوصول إليه، أو جاء جوابه بشكلٍ لا يُقرأ."""

    status_code = 502
    code = "card_gateway_error"
    message = "تعذّر إتمام العملية عند مزود الدفع"


class InvalidWebhookSignature(AppError):
    """توقيع الإشعار لا يطابق ما نحسبه بمفتاح العقد (SPEC القسم 14).

    يُرفض ولا يُسجَّل أثرٌ مالي: إشعارٌ لا نعرف مصدره لا يحرّك ديناراً.
    """

    status_code = 400
    code = "invalid_webhook_signature"
    message = "توقيع إشعار الدفع غير صالح"


# ------------------------------------------------------------------ الحمولات


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """ما نطلبه من المزود لفتح عملية واحدة."""

    cart_id: str
    amount: Decimal
    currency: Currency
    description: str
    # عناوين عودة المتصفح من الصفحة المستضافة (نجاح/إلغاء/رفض)
    return_url: str
    # اسم الدافع وهاتفه — يطلبها المزودون لمكافحة الغسل، ولا نرسل غيرها
    customer_name: str
    customer_phone: str
    # مُعرّف ثابت للدافع لدى المزود، تُربط به البطاقات المحفوظة
    customer_ref: str
    save_card: bool = False


@dataclass(frozen=True, slots=True)
class CardDetails:
    """ما يجوز حفظه من البطاقة — ولا شيء غيره (SPEC القسم 4/6.4).

    `token` رمزٌ يصدره المزود ولا يعمل إلا لدى نفس المتجر. لا PAN ولا CVV ولا
    أيُّ بيانٍ يمكن أن يُدفع به: هذا كل غرض الـ tokenization.
    """

    token: str | None = None
    brand: str | None = None
    last4: str | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None

    @property
    def is_storable(self) -> bool:
        """الحفظ يحتاج رمزاً وآخرَ أربعةٍ وتاريخاً — وناقصُها لا يُعرض ولا يُدفع به."""
        return bool(
            self.token and self.last4 and self.expiry_month and self.expiry_year
        )


@dataclass(frozen=True, slots=True)
class OrderState:
    """حال العملية عند المزود، كما قرأتها الخلفية منه مباشرة.

    `settled=False` تعني «لم يُحسم بعد» — الراكب على الصفحة أو المزود ينتظر
    مصادقة البنك. لا تسوية على غير محسوم، ولا تخمين لصالح أحد.
    """

    provider_order_ref: str
    settled: bool
    paid: bool
    status_text: str
    amount: Decimal | None = None
    currency: str | None = None
    card: CardDetails | None = None
    # مرجع الحركة عند المزود — يُحفظ في `payments.provider_payment_id`
    transaction_ref: str | None = None


@dataclass(frozen=True, slots=True)
class HostedPage:
    provider_order_ref: str
    redirect_url: str


@dataclass(frozen=True, slots=True)
class WebhookNotice:
    """إشعارٌ موقَّعٌ وصل من المزود.

    **بلا مبلغ عمداً.** الإشعار يقول «انظر في هذا الطلب»، والمبلغ والحالة
    يُقرآن بعده من `check_order`. مبلغٌ يأتي من الشبكة ويُقيَّد في الدفتر بابٌ
    لا يُغلق بتوقيعٍ وحده.
    """

    cart_id: str
    provider_order_ref: str


# ------------------------------------------------------------------ الواجهة


class CardGateway(Protocol):
    """أربع عمليات هي كل ما تحتاجه المرحلة 6-ب من أي مزود بطاقات."""

    provider: PaymentProvider

    async def create_hosted_page(self, order: OrderRequest) -> HostedPage:
        """يفتح عملية ويعيد رابط صفحة الدفع المستضافة."""
        ...

    async def check_order(self, provider_order_ref: str) -> OrderState:
        """يستعلم حال العملية — المصدر الوحيد الذي يُبنى عليه تحريك المال."""
        ...

    async def charge_saved_card(
        self, order: OrderRequest, card_token: str
    ) -> OrderState:
        """الدفع بضغطة: خصمٌ مباشر على بطاقةٍ محفوظة بلا صفحة (SPEC القسم 6.4)."""
        ...

    async def refund_order(
        self, provider_order_ref: str, amount: Decimal, currency: Currency, reason: str
    ) -> str:
        """يردّ المبلغ إلى البطاقة ويعيد مرجع الردّ لدى المزود."""
        ...

    def verify_webhook(self, payload: Mapping[str, str]) -> WebhookNotice:
        """يتحقق من توقيع الإشعار أو يرفضه — يفشل مغلقاً دائماً."""
        ...

    async def test_connection(self) -> str:
        """زرّ «اختبار الاتصال» في بطاقة العقد (المرحلة 8، SPEC القسم 13/7).

        **لا يفتح طلباً ولا يحرّك مالاً**: اختبارٌ يترك أثراً مالياً ليس
        اختباراً. يعيد وصفاً يُعرض للمشرف، أو يرفع `CardGatewayError`.
        """
        ...
