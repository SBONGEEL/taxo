from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.services.settlement import SettlementState
from app.models.enums import (
    Currency,
    DisputeResolution,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    ProviderOrderPurpose,
    ProviderOrderStatus,
)

# نفس مفتاح عدم التكرار المستعمل في التحويل — القسم 14 يفرضه على الدفع أيضاً
IdempotencyKey = Field(min_length=8, max_length=64)


class PaymentCreate(BaseModel):
    """اختيار الراكب لقناة الدفع بعد اكتمال الرحلة.

    لا مبلغ هنا: المبلغ هو المتبقي من `final_fare` محسوباً في الخلفية —
    التسعير في الخلفية حصراً (SPEC القسم 14).
    """

    method: PaymentMethod
    idempotency_key: str = IdempotencyKey

    # للبطاقة وحدها (SPEC القسم 6.4): حفظُ البطاقة قرارُ صاحبها لا افتراضُنا،
    # و`saved_card_id` هو «الدفع بضغطة» — بطاقةٌ محفوظة سلفاً بلا صفحة دفع
    save_card: bool = False
    saved_card_id: uuid.UUID | None = None


class PaymentDisputeRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class CliqReferenceRequest(BaseModel):
    """مرجع الحوالة كما يقرؤه الراكب من تطبيق بنكه (SPEC القسم 6.3).

    لا مبلغ ولا alias هنا: كلاهما مُجمَّد على الدفعة منذ فُتحت، وقبولُهما من
    العميل يعني أن يقول الدافعُ كم دفع.
    """

    transfer_reference: str = Field(min_length=3, max_length=64)


class PaymentResolveRequest(BaseModel):
    resolution: DisputeResolution
    note: str | None = Field(default=None, max_length=255)


class PaymentRefundRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    method: PaymentMethod
    provider: PaymentProvider | None
    provider_payment_id: str | None
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    confirmed_by: PaymentConfirmedBy | None
    confirmed_at: datetime | None
    transaction_id: uuid.UUID | None

    # خطوات قناة كليك المسجَّلة على الصف (SPEC القسم 6.2 — المرحلة 9).
    # `cliq_reference` المرجع الذي ولّده TAXO، و`cliq_transfer_reference` ما
    # أدخله الراكب بعد أن حوّل. الاثنان يظهران للطرفين: بهما يتفاهمان.
    cliq_alias: str | None
    cliq_reference: str | None
    cliq_transfer_reference: str | None
    cliq_reference_at: datetime | None
    # موعدُ انقضاء المهلة — مجمَّدٌ على الصف، فترسمه الواجهة عدّاداً بلا أن
    # تحسبه من إعدادٍ قد يتغيّر تحتها (القسم 6.2/6)
    cliq_confirmation_expires_at: datetime | None

    dispute_reason: str | None
    disputed_at: datetime | None
    resolution: DisputeResolution | None
    resolution_note: str | None
    resolved_at: datetime | None

    created_at: datetime


class CardOrderOut(BaseModel):
    """طلب الدفع لدى المزود كما تراه الواجهة (SPEC القسم 6.4).

    `redirect_url` هو ما تفتحه الواجهة، و`cart_id` هو ما تسأل به عن الحال بعد
    العودة. لا مرجعَ مزودٍ داخلياً هنا ولا مفتاحَ عقد: الواجهة تعرض وتنتظر.
    """

    model_config = ConfigDict(from_attributes=True)

    cart_id: str
    provider: PaymentProvider
    purpose: ProviderOrderPurpose
    status: ProviderOrderStatus
    amount: Decimal
    currency: Currency
    redirect_url: str | None
    failure_reason: str | None
    transaction_id: uuid.UUID | None
    created_at: datetime


class CliqChargeOut(BaseModel):
    """ما تعرضه صفحة دفع كليك داخل التطبيق (SPEC القسم 6.2 — المرحلة 9).

    `qr_payload` نصٌّ ترسمه الواجهة رمزاً مربّعاً — **ولا تبنيه**: يحمل مبلغاً
    ومرجعاً يُحاسَب عليهما، وبناؤهما في الخلفية حصراً (القسم 14). و`deep_link`
    ما يفتح تطبيق البنك على شاشة تحويلٍ مملوءة.

    يظهر ما دامت الدفعة `pending`: بعد أن يؤكد الكبتن لم يعد للرمز معنى.
    """

    payment_id: uuid.UUID
    alias: str
    reference: str
    amount: Decimal
    currency: Currency
    qr_payload: str
    deep_link: str
    # ما أدخله الراكب — فارغٌ حتى يحوّل ويعود
    transfer_reference: str | None = None
    transfer_reference_at: datetime | None = None


class RidePaymentsOut(BaseModel):
    """حال الدفع على رحلة كاملةً — لا دفعةً واحدة.

    الدفع المختلط صفّان (SPEC القسم 6)، فالردّ على «ادفع» قائمةٌ دائماً وإن
    كان فيها عنصر واحد. `cliq_charge` يظهر مع دفعة كليك قائمة: منه تبني
    الواجهة الرمزَ والرابطَ وحقلَ المرجع (القسم 6.2). و`card_order` يظهر مع
    طلب بطاقةٍ لم يُحسم: منه تبني «متابعة الدفع» بعد عودةٍ مقطوعة (القسم 6.4).
    """

    ride_id: uuid.UUID
    currency: Currency
    final_fare: Decimal | None
    outstanding: Decimal
    # **الحكمُ لا الرقم**: `outstanding <= 0` كانت تُقرأ «اكتمل الدفع» بينما
    # صفٌّ `pending` قائم، فقالت الشاشةُ «شكراً لك» فوق «بانتظار التأكيد».
    # المصدرُ واحدٌ لأربع شاشات — `services/settlement.py`
    settlement: SettlementState
    # **رسمُ إلغاءٍ سابقٌ يُسدَّد مع هذه الرحلة** (`CANCELLATION-FEE.md` §4/§5)
    # — **بجانب `outstanding` لا داخله**: ذاك ما تبقّى من **أجرة هذه الرحلة**
    # ومنه تُحسب العمولةُ ونصيبُ الكبتن، وضمُّ الدَّين إليه يحسب عمولةً على
    # مالٍ لا يخصّه ويُخفي أن صاحبَه كبتنٌ آخر (نصُّ §5). والرقمُ هنا كي يعرف
    # الراكبُ كم يسلّم نقداً: رقمٌ لا يراه لا يُدفع
    cancellation_debt: Decimal = Decimal("0.000")
    payments: list[PaymentOut]
    cliq_charge: CliqChargeOut | None = None
    card_order: CardOrderOut | None = None


class CardTopupCreate(BaseModel):
    """شحن محفظة بالبطاقة — فوريٌّ آلي بلا طلبٍ ينتظر إنساناً (SPEC القسم 7)."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    save_card: bool = False
    saved_card_id: uuid.UUID | None = None


class SavedCardOut(BaseModel):
    """ما يُعرض من بطاقةٍ محفوظة — **لا رمزَ المزود ولا رقمَ بطاقة**.

    `provider_token` لا يخرج من الخلفية أبداً: هو ما يُدفع به، وعرضُه يبطل
    غرضَ الـ tokenization كلَّه (SPEC القسم 4).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: PaymentProvider
    brand: str | None
    last4: str
    expiry_month: int
    expiry_year: int
    is_default: bool
    created_at: datetime


class CliqDeclareOut(BaseModel):
    """جوابُ «حوّلتُ» — **وقتُ الختم هو ما تقرؤه الشاشة**.

    **ولا يُعاد الصفُّ كلُّه**: الشاشةُ تملكه أصلاً، **وما لا تملكه هو أن
    الختمَ وقع ومتى** — فتُبدّل حالَها وتعرض نافذةَ المراجعة.
    """

    cart_id: str
    #: **لحظةُ قوله «حوّلتُ»** — و`null` لا تقع من هذا الباب أبداً
    declared_paid_at: datetime | None = None
    status: ProviderOrderStatus
