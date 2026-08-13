"""مخطّطاتُ إحالة السائقات (SPEC القسم 9.1، المرحلة 12-ح)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode


class ReferralStageOut(BaseModel):
    """أين وصلت إحالةٌ واحدة — **حقائقُ لا جملةُ حالة**.

    الواجهةُ تبني النصَّ من هذه الحقول («بانتظار اعتماد حسابها»، «أكملت رحلةً
    من ٣»، «مكافأةٌ مدفوعة»)، ولا تأتي الجملةُ من الخلفية — نفسُ سببِ بناء نصِّ
    الإشعار من `data` بدل جملةٍ يؤلّفها الخادم (`services/notifications.py`):
    الخلفيةُ لا تعرف من يقرأ ولا بأي لغة.
    """

    id: uuid.UUID
    created_at: datetime
    driver_approved: bool
    gender_ready: bool
    rides_done: int
    rides_required: int
    qualifies: bool
    rewarded: bool
    reward_amount: Decimal | None = None
    reward_currency: str | None = None
    rewarded_at: datetime | None = None


class MyReferralsOut(BaseModel):
    """قسمُ الإحالة في حساب الكبتن.

    **و`reward_amount` قد تكون صفراً وهذا مقصود**: الشاشةُ لا تعرض مبلغاً حينها
    ولا تَعِد به (قرارُ المالك: الآليةُ تُبنى والمبلغُ يُحدَّد لاحقاً) — ووعدٌ
    بمالٍ لم يقرّره أحدٌ أسوأُ من صمت.
    """

    code: str
    enabled: bool
    reward_amount: Decimal
    required_rides: int
    total_rewarded: Decimal
    referrals: list[ReferralStageOut]


class ReferralSettingsIn(BaseModel):
    """ما يعدّله المشرف per-country — والصفرُ «لم يُحدَّد» لا «صفر»."""

    reward_amount: Decimal | None = Field(default=None, ge=0, le=10000)
    required_rides: int | None = Field(default=None, ge=0, le=100)


class ReferralSettingsOut(BaseModel):
    country_code: CountryCode
    reward_amount: Decimal
    required_rides: int


class AdminReferralRow(BaseModel):
    """صفٌّ في جدول اللوحة — ومعه اسمُ الطرفين، فمعرِّفٌ لا يُقرأ."""

    id: uuid.UUID
    created_at: datetime
    referrer_name: str
    referrer_phone: str
    referred_name: str
    referred_phone: str
    code_used: str
    driver_approved: bool
    gender_ready: bool
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
