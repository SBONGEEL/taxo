"""نظامُ الدفع الجديد — العقدُ على السلك (SPEC §٧٣-هـ المرحلة ١).

**وكلُّ ردٍّ يحمل `currency`** — فالمبلغُ الجزائريُّ يُصاغ «150» على السلك (`core/money_wire.py`) والأردنيُّ والليبيُّ كما هما.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CountryCode,
    Currency,
    GatewayFeeBearer,
    PaymentProviderKind,
    PaymentRequestPurpose,
    PaymentRequestStatus,
    WalletOwnerType,
)

#: **معرّفُ الطريقة** — لاتينيٌّ قصيرٌ ثابت؛ والوسيطُ يُعرف به في المرحلة ٣
PROVIDER_CODE = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]{1,39}$")


class PaymentMethodOut(BaseModel):
    """**طريقةُ دفعٍ كما يراها الراكبُ والكبتن** — بما يلزمه ليدفع: إلى أين، وما يُطلب منه."""

    id: uuid.UUID
    kind: PaymentProviderKind
    name: str
    account_holder: str | None
    account_number: str | None
    bank_name: str | None
    instructions: str | None
    has_qr: bool
    #: **الإيصالُ ورقمُ التحويل إجباريّان** — يقرؤهما التطبيقُ ليطلبهما، والخادمُ يرفض من دونهما (§٧٣-هـ/٢)
    requires_receipt: bool
    #: **وسيطٌ آليّ** (المرحلة ٣) — يُدفع في صفحته ويُضاف فورَ تأكيده، لا طلبٌ يُراجَع
    gateway: bool
    #: **عقدُه في وضع التجربة** (§٧٤-ط/٥) — لا يراه إلا حسابُ تجربة، ومالُه «رصيد تجريبي» لا يغادر المنصّة
    test_mode: bool = False
    #: **رسومُ الوسيط على من** (§٧٤-ك/١): `taxo` — يدفع ما اختاره؛ `user` — تُضاف فوقه وتُعرض قبل الدفع
    fee_payer: str | None = None
    #: **اسمُ الوسيط كما يراه الدافع** («Chargily») — فيُقال «ادفع عبر Chargily» لا «صفحة الوسيط» (§٧٦-ع/٢)
    gateway_name: str | None = None
    #: **يصل الوسيطَ اسمُ الدافع وهاتفُه** (عميلُ Chargily، §٧٦-ع/٦) — فيُقال له ذلك قبل أن يُرسَل، لا في السياسة وحدَها
    shares_payer: bool = False
    #: **معرّفُ الطريقة** (`baridimob` …) — فيعرض التطبيقُ خطواتِ BaridiMob لطريقتها لا لكلِّ تحويل (§٨٢-ب/٣)
    code: str | None = None
    #: **اسمُ صاحب الحساب بالحروف اللاتينيّة** كما تعرضه بريدُ الجزائر (§٨٢-ب/١) — يُرسم مع العربيّ ويُنسخ
    account_holder_latin: str | None = None
    #: **حدّا المبلغ** (§٨٢-ب/٦) — `null` بلا حدّ
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    #: **الوسيطُ متوقّفٌ الآن** (§٨٢-أ/١) — كما رآه آخرُ فحص؛ فيُقال قبل الضغط لا بعده
    down: bool = False


class PaymentMethodsOut(BaseModel):
    currency: Currency
    methods: list[PaymentMethodOut]
    #: **مبالغُ الشحن عند الوسيط خياراتٌ ثابتة** (§٧٤-ط/٥) — وفارغةٌ «لا خيارات»: يُكتب المبلغ كما كان
    topup_choices: list[Decimal] = Field(default_factory=list)
    #: **طرقُ وسيطٍ مخفيّةٌ مؤقّتاً في سوقي** (SPEC §٨٧/١) — أسماؤها لِلافتةٍ تقول «متوقّفٌ مؤقّتاً، ادفع بإحدى الطرق أدناه»
    paused: list[str] = Field(default_factory=list)


class MyPaymentRequestOut(BaseModel):
    """**دفعتي كما أراها** — بحالها وسببِ رفضها أو إلغائها أو ردّها كما كُتب."""

    id: uuid.UUID
    provider_name: str
    kind: PaymentProviderKind
    purpose: PaymentRequestPurpose
    amount: Decimal
    credited_amount: Decimal | None
    currency: Currency
    status: PaymentRequestStatus
    reference: str | None
    rejection_reason: str | None
    cancel_reason: str | None
    refund_reason: str | None
    outcome_note: str | None
    created_at: datetime
    #: **دفعةٌ عند وسيطٍ آليّ** (§٧٦-ع/٢) — معلَّقةً تُقال «بانتظار الدفع» وتُستأنف بـ«أكمل الدفع»، لا «قيد المراجعة»؛ ومرجعُها معرّفُ
    #: صفحة الوسيط فلا يُعرض
    gateway: bool = False
    gateway_name: str | None = None
    #: **الطريقةُ وخطّةُ الاشتراك** — «حاول مرّةً أخرى» يعود بهما نفسَيهما
    provider_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    #: **ما يراه صاحبُها** (SPEC §٨٢-أ/٢): `processing` (دُفع ويُعالَج — لا يُسأل أن يدفع ثانية) · `unconfirmed` (لا نعرف بعد — لا
    #: يحجب) · `in_review` (تحويلٌ ينتظر المراجعة) · وإلا الحالُ نفسُها
    phase: str = ""
    #: **مرجعُ TAXO** (§٨٢-ب/٣) — يكتبه الدافعُ في ملاحظة BaridiMob
    public_ref: str | None = None
    transfer_date: date | None = None


class PaymentCheckoutIn(BaseModel):
    """**صفحةُ دفعٍ عند وسيطٍ آليّ** (المرحلة ٣) — المبلغُ بخانات عملته، والاشتراكُ بخطّته."""

    model_config = ConfigDict(extra="forbid")

    provider_id: uuid.UUID
    purpose: PaymentRequestPurpose
    #: **الشحنُ وحدَه يرسله** (وخيارٌ من خيارات السوق إن ضبطها) — **والاشتراكُ ثمنُه من الخادم** ولا يُقرأ ما يُرسل هنا (§٧٤-ط/٥)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    plan_id: uuid.UUID | None = None
    wallet: WalletOwnerType | None = None


class PaymentCheckoutOut(BaseModel):
    request: MyPaymentRequestOut
    checkout_url: str
    currency: Currency | None = None
    #: **حين يحمل الدافعُ الرسوم** (§٧٤-ك/١): رسمُها والمجموعُ كما قالهما الوسيط — **تُعرض قبل الدفع**؛ و`null` حين تحملها TAXO
    fee_amount: Decimal | None = None
    total_amount: Decimal | None = None


class AdminPaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    kind: PaymentProviderKind
    code: str
    name: str
    integration: str | None
    enabled: bool
    for_topup: bool
    for_subscription: bool
    account_holder: str | None
    account_number: str | None
    bank_name: str | None
    instructions: str | None
    has_qr: bool
    sort_order: int
    fee_bearer: GatewayFeeBearer
    updated_at: datetime
    account_holder_latin: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    #: **مخفيّةٌ بسببٍ مكتوب** (SPEC §٨٧/١) — آليّاً أو بيد المالك؛ ويعيدها المالكُ وحدَه
    hidden_reason: str | None = None
    hidden_at: datetime | None = None
    hidden_auto: bool = False
    #: **الإخفاقاتُ المتتاليةُ الآن** عند الوسيط — صفرٌ للطريقة اليدويّة
    failure_streak: int = 0


class AdminPaymentMethodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    kind: PaymentProviderKind
    code: str = PROVIDER_CODE
    name: str = Field(min_length=2, max_length=80)
    enabled: bool = False
    for_topup: bool = True
    for_subscription: bool = True
    account_holder: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=999)
    #: **الوسيطُ الآليّ** (المرحلة ٣) — `None` لطريقةٍ يدويّة؛ ويُختار عند الإنشاء ولا يتغيّر بعده
    integration: Literal["chargily", "sofizpay"] | None = None
    fee_bearer: GatewayFeeBearer = GatewayFeeBearer.TAXO


class AdminPaymentMethodUpdate(BaseModel):
    """**كلُّ حقلٍ اختياريّ** — ما لم يُرسل لا يُمسّ. **والنوعُ والمعرّفُ والسوقُ لا تتغيّر بعد الإنشاء**: الطلباتُ تُقرأ بها."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=80)
    enabled: bool | None = None
    for_topup: bool | None = None
    for_subscription: bool | None = None
    account_holder: str | None = Field(default=None, max_length=120)
    account_number: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=120)
    instructions: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=999)
    fee_bearer: GatewayFeeBearer | None = None


class AdminPaymentRequestOut(BaseModel):
    """**طلبُ الدفع في طابور الموظّف الماليّ** — بصاحبه وطريقته وإيصاله وما جرى عليه."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None
    user_phone: str | None
    owner_type: WalletOwnerType
    country_code: CountryCode
    currency: Currency
    provider_id: uuid.UUID
    provider_name: str
    kind: PaymentProviderKind
    purpose: PaymentRequestPurpose
    plan_id: uuid.UUID | None
    amount: Decimal
    credited_amount: Decimal | None
    status: PaymentRequestStatus
    reference: str | None
    external_id: str | None
    has_receipt: bool
    receipt_content_type: str | None
    rejection_reason: str | None
    cancel_reason: str | None
    refund_reason: str | None
    outcome_note: str | None
    transaction_id: uuid.UUID | None
    subscription_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    transfer_date: date | None = None
    public_ref: str | None = None


class PaymentApproveIn(BaseModel):
    """**مبلغُ الموظّف — ما وصل الحسابَ فعلاً** (قرارُ المالك ٢٠٢٦-٠٨-٢٩). و`None` «بمبلغه كما ادّعى»."""

    model_config = ConfigDict(extra="forbid")

    credited_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)


class PaymentReasonIn(BaseModel):
    """**السببُ كما سيقرؤه صاحبُ الدفعة** — للرفض والردّ والإلغاء (قرارُ المالك: كلُّ رفضٍ بسببٍ مكتوب)."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class PaymentCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
