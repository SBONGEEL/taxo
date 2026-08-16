"""مخطّطاتُ حوافز الإحالة (SPEC §9.1، 12-ح ثم تعميمُها)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode


class ReferralStageOut(BaseModel):
    """أين وصلت إحالةٌ واحدة — **حقائقُ لا جملةُ حالة**.

    الواجهةُ تبني النصَّ من هذه الحقول («بانتظار اعتماد حسابه»، «أكمل رحلةً من
    ٣»، «مكافأةٌ مدفوعة»)، ولا تأتي الجملةُ من الخلفية — نفسُ سببِ بناء نصِّ
    الإشعار من `data` بدل جملةٍ يؤلّفها الخادم: الخلفيةُ لا تعرف من يقرأ.
    """

    id: uuid.UUID
    created_at: datetime
    # **نوعُ البرنامج مع كل صف**: رمزٌ واحدٌ يعمل في البرنامجين، فالشاشةُ
    # تحتاج أن تقول «سائق» أو «راكب» بجانب كل إحالة — **وشرطُ المالك الثاني
    # بنصِّه**: من دعا سائقاً لا يُفاجأ بمبلغٍ غير الذي توقّعه
    referral_type: str
    driver_approved: bool
    has_subscription: bool
    female_verified: bool
    rides_done: int
    rides_required: int
    qualifies: bool
    rewarded: bool
    # **فوق سقفِ شهرها**: تُعرض صراحةً — «لا صمتَ ولا رقمٌ يختفي» (شرطُ المالك)
    over_monthly_cap: bool = False
    reward_amount: Decimal | None = None
    reward_currency: str | None = None
    rewarded_at: datetime | None = None


class ReferralProgramOut(BaseModel):
    """سياسةُ برنامجٍ واحد كما تُعرض لصاحب الرمز.

    **والسقفُ يُعلن قبل أن يدعو لا بعد أن يُرفض دفعُه** (شرطُ المالك الثالث
    بنصِّه): `monthly_cap` وما بقي منه هذا الشهر.
    """

    referral_type: str
    enabled: bool
    reward_amount: Decimal
    required_rides: int
    # **العلاوةُ تُعرض بجانب الأساس لا منفصلةً عنه** (حارسُ المالك الأول):
    # مشرفٌ — أو مُحيلٌ — يرى رقمين منفصلين قد يظنّ الثاني بديلاً عن الأول
    female_bonus_amount: Decimal
    # **المُحصَّلُ محسوبٌ في الخلفية** (§14): جمعُه في الواجهة يمرّ بالمال عبر
    # عائم، وقد أخرج «٨» بلا كسورٍ بجانب «٥٫٠٠٠» في أول فتحةٍ للشاشة
    female_total_amount: Decimal
    monthly_cap: int | None = None


class MyReferralsOut(BaseModel):
    """قسمُ الإحالة في حساب أيِّ مستخدم — راكباً كان أو كبتناً.

    **و`reward_amount` قد تكون صفراً وهذا مقصود**: الشاشةُ لا تعرض مبلغاً حينها
    ولا تَعِد به — ووعدٌ بمالٍ لم يقرّره أحدٌ أسوأُ من صمت.
    """

    code: str
    # **برنامجان يُعرضان معاً**: الرمزُ واحدٌ والمكافأةُ تختلف بحسب من يسجّل به
    programs: list[ReferralProgramOut]
    # كم دُفع له هذا الشهر — مقابلَ `monthly_cap` في البرنامج المعروض
    paid_this_month: int
    total_rewarded: Decimal
    referrals: list[ReferralStageOut]


class ReferralSettingsIn(BaseModel):
    """ما يعدّله المشرف لكل (دولة، نوع) — والصفرُ «لم يُحدَّد» لا «صفر»."""

    reward_amount: Decimal | None = Field(default=None, ge=0, le=10000)
    required_rides: int | None = Field(default=None, ge=0, le=100)
    female_bonus_amount: Decimal | None = Field(default=None, ge=0, le=10000)
    monthly_cap: int | None = Field(default=None, gt=0, le=10000)
    # **بابٌ صريحٌ للعدم**: غيابُ `monthly_cap` من الطلب يعني «لا تلمسه»،
    # و«بلا سقف» حالةٌ أخرى — وحقلٌ واحدٌ لا يحمل المعنيين
    clear_monthly_cap: bool = False


class ReferralSettingsOut(BaseModel):
    country_code: CountryCode
    referral_type: str
    reward_amount: Decimal
    required_rides: int
    female_bonus_amount: Decimal
    monthly_cap: int | None = None


class AdminReferralRow(BaseModel):
    """صفٌّ في جدول اللوحة — ومعه اسمُ الطرفين، فمعرِّفٌ لا يُقرأ."""

    id: uuid.UUID
    created_at: datetime
    referral_type: str
    referrer_name: str
    referrer_phone: str
    referred_name: str
    referred_phone: str
    code_used: str
    driver_approved: bool
    has_subscription: bool
    female_verified: bool
    rides_done: int
    rides_required: int
    qualifies: bool
    rewarded: bool
    reward_amount: Decimal | None = None
    reward_currency: str | None = None
    rewarded_at: datetime | None = None


class ReferralSummaryOut(BaseModel):
    """مجاميعُ سوقٍ واحد — **محسوبةٌ في القاعدة** لا مجموعةً في المتصفح."""

    country_code: CountryCode
    total_rewarded: Decimal
    rewarded_count: int
    pending_count: int
