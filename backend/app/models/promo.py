"""الكوبونات (SPEC القسم 6.6، المرحلة 12-ز).

**ثلاثةُ أعمدةٍ ليست هنا، وغيابُها قرارٌ لا سهو:**

- **لا `budget_spent`**: المصروفُ مجموعُ دفعات `promo` على رحلات هذا الرمز.
  وعمودٌ يراكم رقماً موجوداً أصلاً يفترق عنه يوماً — نفسُ سبب ألّا يكون في
  المشروع عمودُ رصيدٍ للمحفظة (القسم 4).
- **لا جدولَ «استعمالات»**: الرحلةُ تحمل الرمز والدفعةُ تحمل المبلغ، فالعدُّ
  والمصروفُ استعلامان على ما هو مكتوبٌ أصلاً. وجدولٌ ثالث يعني ثلاثةَ مواضعَ
  لحقيقةٍ واحدة.
- **لا `bearer`**: الشركةُ تتحمّل الخصمَ دائماً في هذه المرحلة، واللوحةُ تقولها
  نصّاً. وعمودٌ بقيمةٍ واحدةٍ ممكنة هو نفسُ ما حُذف من جدول البقشيش
  (`status` الذي لا يُكتب أبداً) — ويُضاف يومَ يظهر متحمّلٌ ثانٍ بافتراضِ
  `company`، فتُقرأ الصفوفُ القديمة صحيحةً بلا تخمين.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
from app.models.enums import CountryCode, PromoDiscountType


class PromoCode(UUIDMixin, TimestampMixin, Base):
    """رمزُ خصمٍ واحدٌ في سوقٍ واحد."""

    __tablename__ = "promo_codes"
    __table_args__ = (
        # **فريدٌ لكل دولة** لا فريدٌ عالمياً: حملةٌ في سوقٍ لا تمنع اسمَها في
        # الآخر، والمطابقةُ بالرمز والدولة معاً فلا يُستعمل رمزُ الأردن في ليبيا
        UniqueConstraint("country_code", "code", name="uq_promo_codes_country_code"),
        CheckConstraint("discount_value > 0", name="promo_value_positive"),
        CheckConstraint("budget_total >= 0", name="promo_budget_not_negative"),
        CheckConstraint("per_user_limit > 0", name="promo_per_user_positive"),
        CheckConstraint(
            "max_discount IS NULL OR max_discount > 0", name="promo_cap_positive"
        ),
        CheckConstraint(
            "discount_type <> 'percent' OR discount_value <= 100",
            name="promo_percent_within_hundred",
        ),
    )

    # يُخزَّن بالحروف الكبيرة دائماً (`services/promo.normalize`): الرمزُ يُقرأ من
    # ملصقٍ أو رسالة ويكتبه الناسُ بحالاتٍ مختلفة، ومطابقةٌ حسّاسةٌ للحالة تجعل
    # الرمزَ الصحيح يُرفض
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )

    discount_type: Mapped[PromoDiscountType] = mapped_column(
        pg_enum(PromoDiscountType, "promo_discount_type"), nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # سقفُ خصمِ النسبة. و`null` يعني «حتى الأجرة كلها» — وهو ما يجعل «الرحلة
    # الأولى مجاناً» ممكنةً بلا حالةٍ خاصة (قرارُ المالك)
    max_discount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    # سقفُ الحملة (شرطُ المالك). **ويحدّ التطبيقَ الجديد لا رحلةً تحمل الرمز**:
    # المبلغُ لا يُعرف قبل الإنهاء، ورفضٌ عنده يحاسب راكباً بسعرٍ غير المعروض
    budget_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    per_user_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    # `null` = بلا حدٍّ غير الميزانية
    total_usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PromoCode {self.code} {self.country_code}>"
