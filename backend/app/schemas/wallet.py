from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CountryCode,
    Currency,
    ProviderOrderPurpose,
    ProviderOrderSource,
    ProviderOrderStatus,
    TopupMethod,
    TopupRequestStatus,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalMethod,
    WithdrawalStatus,
)

# نفس قيد الأعمدة المالية معبَّراً عنه في طبقة الإدخال
Money = Field(gt=0, max_digits=12, decimal_places=3)
OptionalLimitMoney = Field(default=None, ge=0, max_digits=12, decimal_places=3)

# مفتاح يولّده العميل ويعيده مع كل محاولة لنفس العملية (SPEC القسم 14)
IdempotencyKey = Field(min_length=8, max_length=64)


# ------------------------------------------------------------------ المحفظة


class WalletOut(BaseModel):
    """رصيد لحظي محسوب من الدفتر — لا عمود يقابله في القاعدة."""

    owner_id: uuid.UUID
    owner_type: WalletOwnerType
    balance: Decimal
    currency: Currency
    frozen: bool
    # **رسومُ إلغاءٍ عليه لم تُحصَّل** (`design/CANCELLATION-FEE.md` §4) — دَينٌ
    # يُسدَّد من أوّل رصيدٍ يدخل، ويُعرض **بجانب** الرصيد لا مطروحاً منه: رقمٌ
    # واحدٌ يجمع مالاً موجوداً وديناً قائماً لا يُقرأ أيّاً منهما
    cancellation_debt: Decimal = Decimal("0.000")
    # **ومستحقاتٌ معلّقةٌ للكبتن** (§8): تُعرض ولا تدخل الرصيدَ المتاح —
    # رصيدٌ يشمل مالاً لم يصل يكذب على صاحبه، وهي قاعدةُ المحتجَز في البند ١٣
    pending_compensation: Decimal = Decimal("0.000")


class WalletTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: WalletTransactionType
    amount: Decimal
    balance_after: Decimal
    ride_id: uuid.UUID | None
    reference: str | None
    created_at: datetime
    # **النسبةُ المجمَّدة لقيد العمولة وحدَه** (§25.11): الكبتنُ يرى «عمولة TAXO
    # ١٠٪» لا مبلغاً بلا سبب. و`None` لكلِّ ما ليس عمولة — **وليست صفراً**:
    # الصفرُ يعني «حوسب بصفر» والغيابُ يعني «لا نسبةَ لهذا القيد أصلاً»، ورقمٌ
    # واحدٌ لا يحملهما (درسُ `NULL` في `commission_percent_from_subscription`)
    commission_percent: Decimal | None = None


# ------------------------------------------------------------------ التحويل


class TransferRecipientOut(BaseModel):
    """اسم المستلم للتأكيد قبل التنفيذ (SPEC القسم 7) — بلا مُعرّفه."""

    phone: str
    name: str


class TransferRequest(BaseModel):
    recipient_phone: str = Field(min_length=6, max_length=20)
    amount: Decimal = Money
    idempotency_key: str = IdempotencyKey


# -------------------------------------------------------------------- الشحن


class TopupRequestCreate(BaseModel):
    # كليك وحدها تُطلب من التطبيق؛ الكاش من اللوحة والبطاقة فورية (المرحلة 6)
    method: TopupMethod = TopupMethod.CLIQ
    amount: Decimal = Money
    reference: str = Field(min_length=3, max_length=120)


class AdminTopupCreate(BaseModel):
    """شحن يُنشئه الموظف مؤكداً — نقطة الكاش المعتمدة.

    **والمرجعُ إلزاميّ** (قرارُ المالك 2026-08-19): هذا الشحنُ مالٌ يدخل رصيدَ
    إنسانٍ بقرارِ موظفٍ لا بحوالةٍ يشهد عليها مزوّد، فما يُطابَق به الإيصالُ
    الورقيُّ بعد شهرٍ هو هذا الحقل وحدَه. وحرسُه في المخطط لا في الشاشة، وإلا
    كان قاعدةً يلتفّ عليها أيُّ نداءٍ آخر.
    """

    method: TopupMethod = TopupMethod.CASH
    amount: Decimal = Money
    reference: str = Field(min_length=3, max_length=120)


class TopupRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    method: TopupMethod
    amount: Decimal
    status: TopupRequestStatus
    reference: str | None
    note: str | None
    transaction_id: uuid.UUID | None
    processed_at: datetime | None
    created_at: datetime


# -------------------------------------------------------------------- السحب


class WithdrawalCreate(BaseModel):
    amount: Decimal = Money
    method: WithdrawalMethod


class WithdrawalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    amount: Decimal
    method: WithdrawalMethod
    status: WithdrawalStatus
    reference: str | None
    note: str | None
    transaction_id: uuid.UUID | None
    processed_at: datetime | None
    created_at: datetime


class DriverWalletOut(WalletOut):
    """محفظة الكبتن + المتاح للسحب بعد حجز الطلبات القائمة."""

    available_for_withdrawal: Decimal
    # **مبلغٌ مستوفى لكبتنٍ آخر في يده** (`CANCELLATION-FEE.md` §6-أ) — قبضه
    # نقداً مع أجرةِ رحلةٍ وعليه تحويله. **لا أجرةٌ ولا خصمٌ عليه**، فسطرُه
    # مستقلٌّ كسطر البقشيش وسطرِ سداد السلفة؛ وهو **مطروحٌ من المتاح للسحب**
    # لأنه ليس ماله — والرقمُ يُقال باسمه، فمن يرى متاحاً أقلَّ من رصيده
    # يستحق أن يعرف لماذا (قاعدةُ الرصيد المحتجَز في البند ١٣)
    carrier_dues: Decimal = Decimal("0.000")
    min_withdrawal_amount: Decimal
    # **يُقال برقمه** (البند ١٣): من يرى رصيداً لا يستطيع سحبَه كلَّه يستحق أن
    # يعرف كم منه محتجَزٌ ولماذا — لا جملةً عامة عن «رصيدٍ غير متاح»
    withdrawal_reserve_amount: Decimal
    # **مجموعُ عمولة الشهر الجاري** — تقويميّاً بمِنطقة الدولة، لا ثلاثين يوماً
    # متدحرجة: من يقرأ «هذا الشهر» يعدّ من أوّله (`commission_view._month_start`)
    commission_this_month: Decimal = Decimal("0.000")


class EarningsOut(BaseModel):
    """ملخّصُ أرباح الكبتن على نافذة (SPEC القسم 9 و12/7).

    **ثلاثةُ أرقامٍ لا رقم**: ما دخل المحفظة، وما اقتُطع عمولةً، وما قبضه
    بيده كاشاً أو كليكاً — والأخيرُ **لا يزيد رصيده** ويُعرض موسوماً، لأن
    كشفاً يخفي نصف دخله كشفٌ لا يُصدَّق (القسم 9).

    **ورابعٌ منذ المرحلة 12-و**: البقشيش. دخلَ المحفظةَ **بلا عمولةٍ عليه**،
    وهو الوحيد كذلك — فسطرٌ مستقلٌّ هو ما يجعل «ما دخل» و«ما خرج عمولةً»
    يتّسقان لمن يجمعهما بيده. وهو داخلٌ في `net` لأنه مالٌ وصل فعلاً.
    """

    period: str
    from_at: datetime
    to_at: datetime
    currency: str

    wallet_earnings: Decimal
    commission: Decimal
    tips: Decimal
    # **وخامسٌ منذ البند ١٥**: ما اقتُطع سداداً لسلفة — ورقمٌ ينقص بلا سببٍ
    # مكتوبٍ في الكشف يُقرأ عطباً. **وصرفُ السلفة نفسُه ليس هنا**: قرضٌ يُعرض
    # في كشف الأرباح يُقرأ ربحاً
    advance_repaid: Decimal
    # **قد يكون سالباً**: عمولةُ رحلةٍ نقدية تُخصم بلا أرباحَ تقابلها
    net: Decimal
    directly_collected: Decimal
    completed_rides: int


# ------------------------------------------------------- إجراءات الإدارة


class CliqTopupCreate(BaseModel):
    """شحن المحفظة بكليك الآلي (المرحلة 8) — المبلغ وحده."""

    amount: Decimal = Field(gt=0)


class CliqTopupOut(BaseModel):
    """ما يُعرض للدافع: رمز الاستجابة السريعة ورابط تطبيق البنك.

    الرمز يحمل alias الشركة والمبلغ ومرجعنا؛ والحسم يأتي من حساب التاجر لا
    من العميل — ولذلك `cart_id` هو ما يُستعلم به لا حالةٌ يرسلها المتصفح.
    """

    cart_id: str
    amount: Decimal
    currency: Currency
    status: ProviderOrderStatus
    qr_payload: str | None
    deep_link: str | None
    transaction_id: uuid.UUID | None


class WithdrawalPayoutOut(BaseModel):
    """نتيجة التحويل الآلي.

    `paid=false` مع طلبٍ ما زال `approved` تعني «قيد التنفيذ عند المزود» —
    لا قيد في الدفتر، والمال ما زال محجوزاً بطلبه.
    """

    request: WithdrawalOut
    paid: bool
    provider_status: str


class ConfirmTopup(BaseModel):
    """**مبلغُ المشرف — ما وصل الحسابَ فعلاً** (قرارُ المالك 2026-08-29).

    **ودعوى المستخدم ليست هنا**: هي في الطلب، تُقرأ ولا تُصرف. و`None` تعني
    «بمبلغه كما ادّعى» — لمن طابق ما وصل.
    """

    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)


class RejectRequest(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class MarkPaidRequest(BaseModel):
    reference: str = Field(min_length=3, max_length=120)


class AdjustmentCreate(BaseModel):
    """تصحيح إداري — الاتجاهان مسموحان، والسبب إلزامي.

    القيد لا يُعدَّل ولا يُحذف، فتصحيحُ خطأٍ سابقٍ قيدٌ مضاد لا محوٌ للتاريخ.
    """

    amount: Decimal = Field(max_digits=12, decimal_places=3)
    reason: str = Field(min_length=3, max_length=120)
    #: **أيَّ محفظةٍ يصحّح** — قرارٌ يكتبه المشرفُ بيده لا يُخمَّن.
    #:
    #: حسابٌ بدورين له محفظتان: محفظةُ الكبتن تحمل الأرباحَ وتخضع للسلَف
    #: والعمولة، ومحفظةُ الراكب تحمل ما شحنه لرحلاته. **وتصحيحٌ في الخاطئة
    #: يحرّك مالاً في غير موضعه** ولا يُمحى (الدفترُ لا يُعدَّل).
    #:
    #: **و`None` مقبولةٌ بقصد**: صاحبُ دورٍ واحدٍ لا محفظةَ ثانيةَ له، فالسؤالُ
    #: لا معنى له — والخلفيةُ تشتقّها. وحاملُ الدورين بلا إعلانٍ يرتدّ بالخطأ
    #: المسمّى، وهو الصواب: **لا تُخمَّن محفظةٌ في قيدٍ لا يُمحى.**
    wallet: WalletOwnerType | None = None


class WalletFreezeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


# ------------------------------------------------------------ حدود المحفظة


class WalletSettingUpdate(BaseModel):
    transfer_daily_limit: Decimal | None = OptionalLimitMoney
    transfer_monthly_limit: Decimal | None = OptionalLimitMoney
    min_withdrawal_amount: Decimal | None = OptionalLimitMoney
    # الرصيدُ المحتجَز (البند ١٣) — صفرٌ يعني «لا احتجاز»
    withdrawal_reserve_amount: Decimal | None = OptionalLimitMoney


class WalletSettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    transfer_daily_limit: Decimal
    transfer_monthly_limit: Decimal
    min_withdrawal_amount: Decimal
    withdrawal_reserve_amount: Decimal
    updated_at: datetime


class CliqClaimOut(BaseModel):
    """مطالبةٌ يدويةٌ كما تراها اللوحة — **ومصدرُها معها** فلا يُخمَّن."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cart_id: str
    user_id: uuid.UUID
    amount: Decimal
    currency: Currency
    status: ProviderOrderStatus
    source: ProviderOrderSource
    purpose: ProviderOrderPurpose
    failure_reason: str | None
    created_at: datetime
    # **من دفع — بالاسم والرقم** (قرارُ المالك 2026-09-01).
    #
    # **وكانت القائمةُ تعرض مبلغاً ومرجعاً ووقتاً ولا شيءَ يقول من**: الحمولةُ
    # تحمل `user_id` (UUID) **والجدولُ لا يعرضه أصلاً**. فالمشرفُ يرى حوالةً
    # ولا يعرف صاحبَها إلا بأن يبحث عن المرجع في مكانٍ آخر.
    #
    # **والرقمُ معه لا الاسمُ وحدَه**: أسماءٌ تتشابه، **والرقمُ هو المُعرِّف**
    # — وهو ما يطابق به المشرفُ الحوالةَ في كشف حسابه.
    payer_name: str | None = None
    payer_phone: str | None = None
    #: **لحظةُ قوله «حوّلتُ»** — و`null` تعني «فتح الشاشةَ ولم يقل شيئاً بعد»
    declared_paid_at: datetime | None = None


class RejectClaimIn(BaseModel):
    """رفضُ مطالبةٍ يدويّة — **بسببٍ مكتوبٍ يقرؤه صاحبُها**."""

    model_config = ConfigDict(extra="forbid")

    #: **ثمانيةُ أحرفٍ حدّاً أدنى** — كسبب إطفاء الحارس: «لا» و«خطأ» ليستا سبباً
    reason: str = Field(min_length=8, max_length=255)
