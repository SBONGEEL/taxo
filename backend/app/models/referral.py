"""إحالةُ السائقات — الحافزُ وتتبّعُه (SPEC القسم 9.1، المرحلة 12-ح).

**والغرضُ يحدّد الشكل**: الخدمةُ النسائية (المرحلة 10-ج) محدودةٌ بعدد السائقات
لا بعدد الطالبات، فالحافزُ أداةُ عرضٍ لا أداةُ تسويق.

**ولا عمودَ `status` ولا `qualified_at`**، وهذا هو القرارُ الذي يفرّق هذا الجدول
عن جدولٍ يبدو مثله:

- الاستحقاقُ **مقارنةٌ حيّةٌ في الخدمة** — عددُ رحلاتٍ مكتملةٍ على المُحالة ضدَّ
  حدٍّ في `referral_settings` — لا حالةٌ مكتوبةٌ على الصف. فتغييرُ الحدِّ من
  اللوحة يعيد تقييمَ الجميع، بدل أن يترك صفوفاً وسمها حدٌّ قديم. وهي نفسُ قاعدةِ
  «flagged» في تقارير عدم تطابق الجنس (10-ج): عتبةٌ في الخدمة لا عمودٌ في القاعدة.
- **والمدفوعُ وحده يُجمَّد**: `rewarded_at` و`reward_amount` و`transaction_id`
  تُكتب معاً أو لا تُكتب، والمبلغُ لا يُعاد قراءتُه من الإعدادات بعدها — كـ
  `commission_percent_at_ride`. مالٌ خرج بقيمةٍ كانت، وتعديلُ الإعداد يحكم ما
  يأتي لا ما دُفع.

**والرمزُ عمودٌ على `drivers` لا جدولٌ**: قيمةٌ واحدةٌ لكل كبتن، والبحثُ بها
يحتاج فهرساً فريداً — وهو ما يعطيه العمود.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# **صفرٌ يعني «لم يُحدَّد بعد»** لا «مكافأةٌ قدرُها لا شيء» — نفسُ قراءةِ أصفار
# `wallet_settings.transfer_*_limit`، وهو قرارُ المالك (2026-08-12): تُبنى
# الآليةُ ويُترك المبلغُ له. فبصفرٍ لا يُكتب قيدٌ ولا يُوعَد الكبتنُ بمبلغ.
DEFAULT_REWARD_AMOUNT = Decimal("0")

# ثلاثُ رحلاتٍ مكتملة (قرارُ المالك): أقلُّ يفتح باب حساباتٍ وهمية، وأكثرُ
# يُبعد الحافزَ عن سببه.
DEFAULT_REQUIRED_RIDES = 3


class ReferralSetting(UUIDMixin, TimestampMixin, Base):
    """حافزُ الإحالة لكل دولة — تُدار من اللوحة.

    **جدولٌ مستقلٌّ لا حقولٌ على `wallet_settings`**: ذاك حدودُ محفظة، وهذه
    سياسةُ اكتسابِ سائقات. وخلطُهما يجعل اسمَ الجدول لا يصف محتواه — نفسُ سببِ
    استقلال `payment_settings`.
    """

    __tablename__ = "referral_settings"
    __table_args__ = (
        # لا مبالغَ سالبة ولا حدَّ رحلاتٍ سالب — حارسٌ في القاعدة أيضاً، فمبلغٌ
        # يمرّ من طبقةٍ عليا لا يجوز أن يجد الجدولَ مفتوحاً بعدها
        CheckConstraint(
            "reward_amount >= 0 AND required_rides >= 0",
            name="referral_amounts_not_negative",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    reward_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=DEFAULT_REWARD_AMOUNT, server_default=text("0")
    )
    required_rides: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_REQUIRED_RIDES,
        server_default=text("3"),
    )


class DriverReferral(UUIDMixin, TimestampMixin, Base):
    """إحالةٌ واحدة: من أحال، ومن أُحيل، وما دُفع إن دُفع."""

    __tablename__ = "driver_referrals"
    __table_args__ = (
        # **لا إحالةَ لنفسه**: حارسٌ في القاعدة لأن الخدمةَ تفحصه أيضاً — وفحصٌ
        # واحدٌ في طبقةٍ واحدة يُنسى يومَ يُكتب بابٌ ثانٍ للإسناد
        CheckConstraint(
            "referrer_driver_id <> referred_driver_id",
            name="referral_not_self",
        ),
        # **المكافأةُ كلٌّ أو لا شيء**: لحظةٌ ومبلغٌ وعملةٌ وقيدٌ معاً. وصفٌّ
        # نصفُ مكافأةٍ (لحظةٌ بلا قيد) يجعل «كم دُفع» سؤالاً بجوابين
        CheckConstraint(
            "(rewarded_at IS NULL AND reward_amount IS NULL "
            "AND reward_currency IS NULL AND transaction_id IS NULL) OR "
            "(rewarded_at IS NOT NULL AND reward_amount IS NOT NULL "
            "AND reward_currency IS NOT NULL AND transaction_id IS NOT NULL)",
            name="referral_reward_all_or_nothing",
        ),
        CheckConstraint(
            "reward_amount IS NULL OR reward_amount > 0",
            name="referral_reward_positive",
        ),
    )

    referrer_driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # **فريدٌ**: حسابٌ واحدٌ يُحال مرةً واحدةً في عمره. والحارسُ في القاعدة لا
    # في فحصٍ سابقٍ يمكن أن يُسبَق — تسجيلان متزامنان برمزين لا ينتجان مكافأتين
    referred_driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # الرمزُ كما كُتب. **وليس تكراراً لـ`referrer_driver_id`**: الرمزُ قد يُبدَّل
    # (رمزٌ سُرّب)، والسجلُ يجيب «بأي رمزٍ جاءت» بعد التبديل
    code_used: Mapped[str] = mapped_column(String(16), nullable=False)

    rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    reward_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reward_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True
    )
