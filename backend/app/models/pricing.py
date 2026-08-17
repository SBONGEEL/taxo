from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, VehicleCategory


class PricingRule(UUIDMixin, TimestampMixin, Base):
    """تسعيرة فئة مركبة في دولة.

    التسعير كله يُحسب في الخلفية من هذه القيم (SPEC القسم 5) — الواجهة تعرض فقط.
    """

    __tablename__ = "pricing_rules"
    __table_args__ = (
        UniqueConstraint("country_code", "vehicle_category"),
        CheckConstraint(
            "base_fare >= 0 AND price_per_km >= 0 AND price_per_min >= 0 "
            "AND minimum_fare >= 0 AND cancellation_fee >= 0",
            name="pricing_amounts_non_negative",
        ),
        CheckConstraint(
            "stop_fee >= 0 AND stop_price_per_min >= 0 "
            "AND stop_free_minutes >= 0 AND stop_max_wait_minutes >= 0",
            name="pricing_stop_amounts_non_negative",
        ),
        CheckConstraint(
            "pause_price_per_min >= 0 AND arrival_free_minutes >= 0 "
            "AND pause_max_minutes >= 0",
            name="pricing_pause_amounts_non_negative",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    vehicle_category: Mapped[VehicleCategory] = mapped_column(
        pg_enum(VehicleCategory, "vehicle_category"), nullable=False
    )

    base_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_km: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_min: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cancellation_fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    # --- المحطات الوسيطة (المرحلة 12-ب، SPEC القسم 5.10) ---
    # كلُّها **صفرٌ افتراضاً**: لا تُفتح كلفةٌ على راكبٍ بالسكوت، كما لا
    # تُفعَّل عمولةٌ بالسكوت. والمشرف يضبطها per-country من شاشة التسعيرة
    stop_fee: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    stop_free_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    stop_price_per_min: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    # **صفرٌ يعني «لا سقف»** لا «سقفٌ مقداره صفر» — كما يُقرأ صفرُ حدِّ
    # التحويل «لم يُضبط» (SPEC القسم 7). وسقفٌ مقداره صفرٌ كان سينبّه الطرفين
    # لحظةَ الوصول
    stop_max_wait_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    # --- الوقفةُ غير المخطَّطة وانتظارُ الوصول (SPEC §5.10-ب) ---
    # **صفرٌ افتراضاً** كسابقاتها: لا تُفتح كلفةٌ على راكبٍ بالسكوت.
    #
    # **وقيمةُ الدقيقة واحدةٌ للحالتين** — وقفةٍ في منتصف الرحلة وانتظارٍ عند
    # الوصول: دقيقةُ الكبتن الواقف تساوي دقيقتَه الواقفة، سواءٌ نزل الراكبُ إلى
    # محلٍّ أم لم ينزل بعد. ورقمان لمفهومٍ واحدٍ يفترقان أوّلَ تعديلٍ لأحدهما،
    # ثم يُسأل «لماذا اختلفا؟» فلا جواب.
    #
    # **ومستقلةٌ عن `stop_price_per_min`** وإن تشابه الحساب: تلك محطةٌ **دخلت
    # التقدير** فالراكبُ رآها قبل أن يطلب، وهذه لم تُقدَّر أصلاً
    pause_price_per_min: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default="0"
    )
    # **مهلةُ الوصول المجانية وحدَها** — ولا مهلةَ لوقفةِ منتصف الرحلة: تلك
    # يطلبها الراكبُ صراحةً بعد أن قُدِّرت أجرتُه، فالعدّادُ يبدأ بالضغطة
    arrival_free_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    # **صفرٌ = لا سقف** (قرارُ المالك في الفرع أ): يُنبَّه الطرفان عنده **ولا
    # تُنهى الرحلة** — الإنهاءُ فعلُ الكبتن
    pause_max_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PricingRule {self.country_code}/{self.vehicle_category}>"
