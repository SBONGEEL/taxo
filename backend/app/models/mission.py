"""المهامُّ والمستويات (`design/MISSIONS-LEVELS.md`، البند ٥٣).

**ثلاثةُ أشياء لا شيءٌ واحد**، وفصلُها مقصود: المهمّةَ تكتبها الإدارةُ شهرياً،
والمستوى **حكمٌ آليٌّ على أداءٍ مقيس** تكتبه مهمّةٌ دوريةٌ وحدَها، والشارةُ
**تقديرٌ إنسانيٌّ لما لا يُقاس** بيد المشرف (`models/badge.py`).

وخلطُ الأخيرين يُفسد الاثنين: شارةٌ آليةٌ تصير مستوىً ثانياً بأسماءٍ مختلفة،
ومستوىً يُمنح بيدٍ يصير **محاباةً في ترتيب التوزيع** — أي في المال.

**والتقدّمُ يُقاس حيّاً ولا يُراكَم في عمود** — الدرسُ الذي أسقط `qualified_at`
من الإحالة و`budget_spent` من الكوبونات: عدّادٌ يراكم رقماً محسوباً أصلاً يفترق
عنه يوماً، وتعديلُ الإدارة لهدفِ المهمّة يترك صفوفاً وسمها هدفٌ قديم.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# **معياران مقروءان اليوم، والثالثُ ليس كذلك.** `active_hours` يحتاج التقاطاً
# جديداً (`driver_activity_days`): الحضورُ مفتاحٌ في Redis مهلتُه ٦٠ ثانية،
# و`is_online` يقول «الزرُّ مرفوع» لا «كان هنا ثلاث ساعات». فهو بندٌ مستقلٌّ
# بحجمه، ويُبدأ بما هو مقروء — **ولا يُشحن معيارٌ يقيس من لا شيء**.
METRIC_COMPLETED_RIDES = "completed_rides"
METRIC_MIN_RATING = "min_rating"
MISSION_METRICS: tuple[str, ...] = (METRIC_COMPLETED_RIDES, METRIC_MIN_RATING)

# **مقياسُ كلِّ معيارٍ في بيتٍ واحد.** العمودُ `NUMERIC(12,3)` يُسلسَل «3.000»
# بينما العدُّ المحسوب يُسلسَل «2» — فيقرأ الكبتنُ «أكملتَ ٢ من ٣٫٠٠٠ رحلات»،
# رقمان بشكلين في جملةٍ واحدة. وهو الشكلُ نفسُه الذي أخرج «٠ د.أ» بجانب
# «٥٫٠٠٠ د.أ» في شاشة الإحالة — وقياسُ الرحلاتِ صحيحٌ بلا كسور، والتقييمِ بخانة
METRIC_SCALE: dict[str, str] = {
    METRIC_COMPLETED_RIDES: "1",
    METRIC_MIN_RATING: "0.1",
}


def normalize_metric(metric: str, value: "Decimal") -> "Decimal":
    """يُعيد القيمةَ بمقياس معيارها — ويمرّ منه **الهدفُ والقيمةُ معاً**.

    ومرورُ أحدهما دون الآخر هو بعينه ما ينتج الرقمين المختلفَي الشكل.
    """
    return value.quantize(Decimal(METRIC_SCALE.get(metric, "0.001")))

# ثلاثةٌ فوق الصفر (قرارُ المالك ٣): خمسةٌ تجعل الفرقَ بين متجاورين غيرَ محسوس
# فتُقرأ الشاشةُ ولا تُحرّك أحداً. **والصفرُ مستوىً** لا نقصٌ — كبتنٌ جديدٌ فيه
MAX_LEVEL = 3

# **حدُّ المالك الأقصى: ١٠٠م** (قرارُه ٢). حارسٌ في القاعدة أيضاً، فرقمٌ يمرّ من
# طبقةٍ عليا لا يجوز أن يجد الجدولَ مفتوحاً بعده — والمتجاوزُ يقلب القاعدةَ نفسَها
MAX_LEVEL_DISCOUNT_METERS = 100


class Mission(UUIDMixin, TimestampMixin, Base):
    """مهمّةُ شهرٍ واحدةٍ في سوقٍ واحد.

    **والشهرُ بتقويم الدولة** لا بتقويم الخادم — قاعدةُ «يومِ الدولة» في
    `services/stats.py`: شهرُ عمّان يبدأ قبل شهرِ UTC بثلاث ساعات، وكبتنٌ أنهى
    رحلتَه الأخيرة في الحادية عشرة ليلاً في آخر يومٍ يُحرم منها بلا سبب.
    """

    __tablename__ = "missions"
    __table_args__ = (
        # **معيارٌ واحدٌ لا يتكرر في شهرٍ واحد**: هدفان لمعيارٍ واحدٍ يجعلان
        # «هل أنجزها؟» سؤالاً بجوابين، وأيُّهما يرفع المستوى قرارٌ لم يتّخذه أحد
        UniqueConstraint(
            "country_code", "month", "metric", name="uq_missions_country_month_metric"
        ),
        CheckConstraint("target > 0", name="mission_target_positive"),
        # أوّلُ يومٍ في الشهر — والشهرُ **قيمةٌ** لا مدىً محسوبٌ من تاريخٍ عشوائي
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="mission_month_is_first"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # **نصٌّ لا ENUM** — قاعدةُ `feature_flags.feature_key`: معيارٌ ثالثٌ يوماً
    # يصير بياناً لا ترحيلة، ولا يُدفع ثمنُ `ALTER TYPE` وذاكرةِ asyncpg
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[Decimal] = mapped_column(
        __import__("sqlalchemy").Numeric(12, 3), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class LevelSetting(UUIDMixin, TimestampMixin, Base):
    """أثرُ كلِّ مستوىً بالأمتار، لكل سوق — **صيغةُ الخصم** (قرارُ المالك ١).

    الترتيبُ يصير بـ«المسافةِ المؤثِّرة = المسافة − خصمُ المستوى»، **ولا عتبةَ
    حادّة**: صيغةُ الشرائح المرفوضة كانت تجعل كبتنَين على ٤٩٩م و٥٠١م في شريحتين
    فيقلب فرقُ مترين القاعدة. **وأقصى إزاحةٍ = الخصمُ نفسُه**، فيُقرأ «كم مترٍ
    يساوي هذا المستوى» جواباً مباشراً.

    **وصفرٌ يعني مطفأ بلا شرطٍ في الكود** — وهو الافتراض، فتشحن الميزةُ خامدةً
    مرتين كحافز الإحالة: مفتاحٌ مطفأٌ وأثرٌ صفر.
    """

    __tablename__ = "level_settings"
    __table_args__ = (
        UniqueConstraint("country_code", "level", name="uq_level_settings_country"),
        CheckConstraint(
            f"level >= 0 AND level <= {MAX_LEVEL}", name="level_setting_in_range"
        ),
        # **حدُّ المالك في القاعدة**: «المستوى يقلّص نطاقَ البحث قليلاً لا يلغيه»
        CheckConstraint(
            f"discount_meters >= 0 AND discount_meters <= {MAX_LEVEL_DISCOUNT_METERS}",
            name="level_discount_within_cap",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_meters: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
