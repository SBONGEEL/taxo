"""سلفُ الكباتن — الجدولُ وإعداداتُه (البند ١٥، SPEC القسم 9.2).

**هذه أولُ مرةٍ تُقرض فيها المنصّةُ أحداً**، وكلُّ ما بُني قبلها مكتوبٌ على أن
المحفظةَ لا تَدين: `balance_after >= 0` قيدٌ في القاعدة نفسِها (ترحيلة `0006`)،
ولا عمودَ رصيدٍ أصلاً — الرصيدُ مجموعُ الدفتر.

**فالسلفةُ ليست رصيداً سالباً** (قرارُ المالك 2026-08-14). ثلاثةُ أشكالٍ كانت
ممكنة، والمختارُ ثالثُها:

- **رصيدٌ سالب** — يعني رفعَ `balance_after >= 0`، أي إسقاطَ حارسٍ يحمي كلَّ
  مسارٍ ماليٍّ في المشروع ليخدم ميزةً واحدة. **ثمنٌ لا يُدفع** بنصِّ قراره.
- **محفظةٌ ثانيةٌ للدَّين** — رصيدان لصاحبٍ واحدٍ يُسأل عنهما بسؤالين.
- ✅ **جدولٌ مستقلٌّ وقيدان في الدفتر**: `advance` دائنٌ عند الصرف،
  و`advance_repayment` مدينٌ عند كل اقتطاع. فالدفترُ يبقى صادقاً موجباً،
  والدَّينُ رقمٌ في جدوله.

**ولا عمودَ «المتبقّي»**: يُطرح من الدفتر كما يُطرح رصيدُ المحفظة — والعمودُ
الذي يخزّن مجموعاً يفترق عن مجموعه أوَّلَ قيدٍ يُكتب بلا تحديثه.

**والمُجمَّدُ هو ما لا يُعاد تقييمُه**: المبلغُ والعملةُ و`due_at`. المهلةُ
تُقرأ من الإعدادات **لحظةَ الصرف** ثم لا تُقرأ بعدها — قاعدةُ
`commission_percent_at_ride` و`cliq_confirmation_expires_at`: تعديلُ السياسة
يحكم ما يأتي، لا مهلةً ينظر إليها كبتنٌ في شاشته الآن.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import AdvanceStatus, CountryCode, Currency

# **مهلةُ التحصيل الافتراضية** — أسبوعان: السلفةُ الأولى بقيمة اشتراكٍ يوميّ،
# وأسبوعان عملٍ يسدّدانها باقتطاعٍ لا يُشعر به. وهي حقلٌ في اللوحة لا ثابتٌ في
# الكود، لأن الأسواقَ تختلف — بخلاف مدةِ الشطب أدناه
DEFAULT_TERM_DAYS = 14

# **نسبةُ الاقتطاع الافتراضية** (قرارُ المالك 2026-08-14): ٢٠٪ من أرباح الرحلة
DEFAULT_DEDUCTION_PERCENT = 20

# **حدُّ الأهلية الافتراضي بالرحلات**: صفرٌ يعني «لا شرطَ رحلاتٍ» لا «صفرَ
# رحلات» — كأصفار `wallet_settings`. والشرطُ الحقيقيُّ الذي لا يُعطَّل هو
# اشتراكٌ أسبوعيٌّ أو شهريٌّ **مضى**، وهو في الخدمة لا في الإعدادات
DEFAULT_MIN_COMPLETED_RIDES = 0


class AdvanceSetting(UUIDMixin, TimestampMixin, Base):
    """سياسةُ السلف لكل دولة — تُدار من اللوحة.

    **جدولٌ مستقلٌّ لا حقولٌ على `wallet_settings`**: ذاك حدودُ محفظة، وهذه
    سياسةُ إقراض — نفسُ سببِ استقلال `referral_settings` و`payment_settings`.

    **ولا عمودَ «قيمةِ السلفة»**: أساسُ السقف هو **سعرُ الخطة اليومية** في
    `subscription_plans` بنصِّ قرار المالك. ورقمٌ يُكتب هنا يتقادم يومَ تتغيّر
    الأسعار، فيصير للاشتراك اليوميّ سعران.
    """

    __tablename__ = "advance_settings"
    __table_args__ = (
        CheckConstraint(
            "deduction_percent > 0 AND deduction_percent <= 100 "
            "AND term_days > 0 AND min_kept_amount >= 0 "
            "AND min_completed_rides >= 0 AND min_rating >= 0 "
            "AND growth_percent_per_repaid >= 0 AND max_multiplier_percent >= 100",
            name="advance_settings_sane",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    # نسبةُ ما يُقتطع من أرباح الرحلة الواحدة (قرارُ المالك: ٢٠٪)
    deduction_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DEDUCTION_PERCENT,
        server_default=text("20"),
    )
    # **الحدُّ الأدنى الذي يبقى للكبتن من أرباح الرحلة** — بنصِّ قراره:
    # «الاقتطاعُ الكامل يوقفه عن العمل فيمتنع السدادُ نفسُه». وصفرٌ يعني «لا
    # حدَّ»، فالنسبةُ وحدها تحكم
    min_kept_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    term_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_TERM_DAYS, server_default=text("14")
    )
    # **شروطُ الأهلية بأسمائها** (القرار ١): لا «نقاطَ مصداقية». من يُمنع يقرأ
    # «تحتاج ٥٠ رحلةً مكتملة» فيعرف ماذا يفعل، ولا يقرأ «مصداقيتك ٣٫٢»
    min_completed_rides: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MIN_COMPLETED_RIDES,
        server_default=text("0"),
    )
    min_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    # **النموُّ بعد سدادٍ مُثبَت** (§٧ من المواصفة): كلُّ سلفةٍ سُدِّدت ترفع
    # السقفَ بهذه النسبة من الأساس. وصفرٌ = «لا نموّ» فتبقى عند اليوميّ أبداً
    growth_percent_per_repaid: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # سقفُ النموِّ نفسِه: ١٠٠٪ يعني «لا تتجاوز قيمةَ اليوميّ مهما سدَّد»
    max_multiplier_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default=text("100")
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<AdvanceSetting {self.country_code}>"


class DriverAdvance(UUIDMixin, TimestampMixin, Base):
    """سلفةٌ واحدةٌ صُرفت لكبتن — بمبلغها ومهلتها ومصيرها."""

    __tablename__ = "driver_advances"
    __table_args__ = (
        CheckConstraint("amount > 0", name="advance_amount_positive"),
        # **الشطبُ كلٌّ أو لا شيء**: من شطب ومتى ولماذا تُكتب معاً — قيدُ
        # `driver_referrals` نفسُه على المكافأة المدفوعة. وسطرٌ يقول «شُطب» بلا
        # قرارٍ يحمل اسمَ صاحبه خسارةٌ لا يملكها أحد
        CheckConstraint(
            "(written_off_at IS NULL AND written_off_by IS NULL "
            "AND writeoff_reason IS NULL) OR "
            "(written_off_at IS NOT NULL AND writeoff_reason IS NOT NULL)",
            name="advance_writeoff_all_or_nothing",
        ),
        # **سلفةٌ قائمةٌ واحدةٌ لكل كبتن**: فهرسٌ جزئيٌّ في القاعدة لا فحصٌ
        # يمكن أن تسبقه ضغطةٌ ثانية. وهو أيضاً سببُ وجود `status` عموداً:
        # المتبقّي مجموعٌ في الدفتر، ومجموعٌ لا يُقرأ في مُسنَد فهرس
        Index(
            "uq_advance_outstanding",
            "driver_id",
            unique=True,
            postgresql_where="status = 'outstanding'",
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )
    status: Mapped[AdvanceStatus] = mapped_column(
        pg_enum(AdvanceStatus, "advance_status"),
        nullable=False,
        default=AdvanceStatus.OUTSTANDING,
        index=True,
    )
    # **المهلةُ مجمَّدةٌ لحظةَ الصرف** ولا تُقرأ من الإعدادات بعدها
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # **ولا `transaction_id` هنا** وإن كان في `driver_referrals`: هناك يشير
    # الصفُّ إلى قيدٍ لا يشير إليه أحد، وهنا **الدفترُ يحمل `advance_id`
    # أصلاً** — فعمودٌ عكسيٌّ بيتٌ ثانٍ للعلاقة نفسِها يفترق عن الأول أوَّلَ
    # مرةٍ يُكتب أحدهما بلا الآخر. ومفتاحان متقابلان يصنعان **دورةً** بين
    # الجدولين تعجز عن ترتيبها كلُّ أداةِ إنشاءٍ أو حذف — وهو ما كشفه تحذيرُ
    # SQLAlchemy لحظةَ كتابته
    # **من وافق حين تجاوز السقف** (القرار ٢): فارغٌ للصرف التلقائيِّ داخل
    # السقف — وطابورُ موافقاتٍ على كل دينارٍ يموت بعد أسبوع فيصير البابُ مغلقاً
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    written_off_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    writeoff_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DriverAdvance {self.driver_id} {self.amount} ({self.status})>"
