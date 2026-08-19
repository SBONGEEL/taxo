"""حوافزُ الإحالة — ثلاثةُ برامجَ خلف جدولٍ واحد (SPEC §9.1، و12-ح ثم تعميمُها).

**والتعميمُ نقلُ طرفَي الإحالة من `drivers` إلى `users`، لا عمودُ نوعٍ على
الجدول القائم.** والفرقُ ليس ذوقاً: `driver_referrals` كان طرفاه مفتاحين إلى
`drivers`، **وصفُّ الراكب لا يوجد في `drivers` أصلاً** — فعمودُ نوعٍ عليه يجعله
جدولاً بعمودٍ يكذب (نوعٌ يقول «راكب» ومفتاحٌ يشير إلى كبتن)، ومخرجُه الوحيد
عمودان متوازيان لحقيقةٍ واحدة. وهو بعينه ما يمنعه هذا المشروع في كل موضع: لا
عمودَ رصيدٍ مع دفتر، ولا `waited_minutes` مع `arrived_at`، ولا `budget_spent`
مع دفعات `promo`.

**والطرفان حسابان لا كباتن**، والكودُ كان يقولها قبل التعميم: «حسابُ كبتنٍ
امتدادٌ لحساب مستخدم لا كيانٌ موازٍ له».

**ولا عمودَ `referral_type` على صفِّ الإحالة**: النوعُ **مشتقٌّ من دور المُحال**
(`users.role`). **وقد كان ثابتاً مدى عمر الحساب، فلم يكن يُخزَّن** — ومنذ صارت
الأدوارُ مجموعةً (2026-08-19) صار **واقعةً تاريخيةً تُختم لحظةَ الإحالة**: أيُّ
برنامجٍ انطبق يومَها، لا ما يُشتقّ من أدوارِ اليوم. والصفوفُ الأقدمُ تبقى فارغةً
ولا تُملأ بأثر رجعي — ملؤها كتابةُ استنتاجٍ في عمودِ وقائع.
وحيث يُكتب النوعُ فعلاً هو **الإعدادات**، لأن الصفَّ هناك **هو البرنامج** لا
وصفٌ لحدثٍ وقع.

**ولا `status` ولا `qualified_at`** كما كان: الاستحقاقُ مقارنةٌ حيّةٌ في الخدمة،
فتغييرُ الحدِّ في اللوحة يُعيد تقييمَ الجميع بلا لمس صف — قاعدةُ «flagged» في
تقارير عدم التطابق. **والمدفوعُ وحدَه يُجمَّد**، كـ`commission_percent_at_ride`.
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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# **صفرٌ يعني «لم يُحدَّد بعد»** لا «مكافأةٌ قدرُها لا شيء» — نفسُ قراءةِ أصفار
# `wallet_settings.transfer_*_limit`، وهو قرارُ المالك: تُبنى الآليةُ ويُترك
# المبلغُ له. فبصفرٍ لا يُكتب قيدٌ ولا يُوعَد أحدٌ بمبلغ.
# **مُكمَّمٌ إلى ثلاث خانات**: يُسلسَل نصّاً كما يُسلسَل عمودُ `MONEY`، وصفرٌ
# بلا كسورٍ يخرج `"0"` بين `"0.000"` — الشكلُ السابع في `CLAUDE.md`، وقد أمسكه
# حارسُ `tests/money_format.py` على `GET /me/referrals` في أوّل تشغيلٍ كامل له.
DEFAULT_REWARD_AMOUNT = Decimal("0.000")

# ثلاثُ رحلاتٍ مكتملة لبرنامج السائقين (قرارُ المالك 2026-08-12)، **وواحدةٌ
# للركاب**: أقلُّ يفتح باب حساباتٍ وهمية، وأكثرُ يُبعد الحافزَ عن سببه. وحدُّ
# الراكب أدنى لأن رحلتَه أرخصُ وأقصر — والحارسُ عليه السقفُ والفريدُ لا العدد
DEFAULT_REQUIRED_RIDES = 3
DEFAULT_RIDER_REQUIRED_RIDES = 1

# **أنواعُ البرامج — نصٌّ لا ENUM**، لنفس سبب `feature_flags.feature_key`: نوعٌ
# ثالثٌ يوماً يصير بياناً لا ترحيلة، ولا يُدفع ثمنُ `ALTER TYPE` وذاكرةِ asyncpg
REFERRAL_TYPE_RIDER = "rider"
REFERRAL_TYPE_DRIVER = "driver"
REFERRAL_TYPES: tuple[str, ...] = (REFERRAL_TYPE_RIDER, REFERRAL_TYPE_DRIVER)


class ReferralSetting(UUIDMixin, TimestampMixin, Base):
    """برنامجُ إحالةٍ واحد: دولةٌ ونوع — **والصفُّ هنا هو البرنامج**.

    **جدولٌ مستقلٌّ لا حقولٌ على `wallet_settings`**: ذاك حدودُ محفظة، وهذه
    سياسةُ اكتسابِ حسابات. وخلطُهما يجعل اسمَ الجدول لا يصف محتواه.
    """

    __tablename__ = "referral_settings"
    __table_args__ = (
        # **صفٌّ لكل (دولة، نوع)** — وكان الفريدُ على الدولة وحدها قبل التعميم
        UniqueConstraint(
            "country_code", "referral_type", name="uq_referral_settings_country_type"
        ),
        # لا مبالغَ سالبة ولا حدَّ رحلاتٍ سالب — حارسٌ في القاعدة أيضاً، فمبلغٌ
        # يمرّ من طبقةٍ عليا لا يجوز أن يجد الجدولَ مفتوحاً بعدها.
        # **والعلاوةُ معها بنصِّ شرط المالك** (2026-08-16): لا تُحفظ سالبةً
        CheckConstraint(
            "reward_amount >= 0 AND required_rides >= 0 "
            "AND female_bonus_amount >= 0",
            name="referral_amounts_not_negative",
        ),
        # **والسقفُ قابلٌ للعدم لا صفر**: الصفرُ في هذا المشروع «لم يُحدَّد»،
        # وسقفٌ صفرُه «لا إحالات» — قيمتان متناقضتان لرقمٍ واحد.
        # فـ`NULL` = بلا سقف، كـ`promo_codes.total_usage_limit` حرفياً
        CheckConstraint(
            "monthly_cap IS NULL OR monthly_cap > 0",
            name="referral_cap_positive_or_null",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    referral_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=REFERRAL_TYPE_DRIVER,
        server_default=REFERRAL_TYPE_DRIVER,
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

    # **العلاوةُ النسائية — لا برنامجٌ ثالث** (قرارُ المالك 2026-08-16).
    # تُضاف إلى `reward_amount` حين تكون المُحالةُ **موثَّقةَ الجنس**، والمجموعُ
    # قيدٌ واحدٌ في الدفتر.
    #
    # **وسببُ العلاوة على البرنامج الثالث**: لو كان النسائيُّ برنامجاً بمبلغه،
    # ومبلغُه صفرٌ (لم يُحدَّد) بينما مبلغُ السائقين مئة — لَدفعنا **صفراً** لمن
    # أحال سائقةً ومئةً لمن أحال سائقاً، أي ينقلب الحافزُ على غرضه بصمت.
    # والعلاوةُ تجعل الأسوأَ ممكناً: صفرُ علاوةٍ = مساواةٌ لا عقوبة.
    #
    # **وتُقرأ على صفِّ `driver` وحدَه**: راكبةٌ موثَّقةُ الجنس لا علاوةَ عليها،
    # فغرضُ العلاوة بناءُ عرضِ السائقات لا مكافأةُ جنسٍ في ذاته.
    female_bonus_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=DEFAULT_REWARD_AMOUNT, server_default=text("0")
    )

    monthly_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # كوبونُ ترحيبٍ للمُحال (12-ز) — و`is_public=false` يمنع كتابتَه بيد أحد
    referred_promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True
    )


class Referral(UUIDMixin, TimestampMixin, Base):
    """إحالةٌ واحدة: من أحال، ومن أُحيل، وما دُفع إن دُفع.

    **وطرفاها حسابان** منذ التعميم — فنوعُ البرنامج يُقرأ من دور المُحال، ولا
    يحتاج عموداً يقوله.
    """

    __tablename__ = "referrals"
    __table_args__ = (
        # **لا إحالةَ لنفسه**: حارسٌ في القاعدة لأن الخدمةَ تفحصه أيضاً — وفحصٌ
        # واحدٌ في طبقةٍ واحدة يُنسى يومَ يُكتب بابٌ ثانٍ للإسناد
        CheckConstraint(
            "referrer_user_id <> referred_user_id", name="referral_not_self"
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

    referrer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # **فريدٌ**: حسابٌ واحدٌ يُحال مرةً واحدةً في عمره — **وهو الآن أقوى مما
    # كان**: كان يمنع إحالةَ كبتنٍ مرتين، وصار يمنع إحالةَ **حساب** مرتين مهما
    # تعدّدت البرامج. والحارسُ في القاعدة لا في فحصٍ سابقٍ يمكن أن يُسبَق —
    # تسجيلان متزامنان برمزين لا ينتجان مكافأتين
    referred_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # الرمزُ كما كُتب. **وليس تكراراً لـ`referrer_user_id`**: الرمزُ قد يُبدَّل
    # (رمزٌ سُرّب)، والسجلُ يجيب «بأي رمزٍ جاءت» بعد التبديل
    code_used: Mapped[str] = mapped_column(String(16), nullable=False)

    # **واقعةُ لحظةِ الإحالة**: أيُّ برنامجٍ انطبق يومَها. فارغٌ في الصفوف
    # الأقدمَ من العمود، ويُشتقّ لها من الدور كما كان — ولا تُملأ بأثر رجعي
    referral_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    rewarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    reward_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    reward_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True
    )
