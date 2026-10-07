"""إعداداتُ الخدمات الجديدة لكلِّ سوق (SPEC §٦٣-ج) — **صفٌّ واحدٌ لكلِّ سوق، وعمودٌ لكلِّ مبلغٍ أو عتبة**، تضيفه ترحيلةُ خدمته.

**وأرقامُ المالك افتراضاتٌ للأردن**، **ولليبيا صفرٌ في كلِّ مبلغ** — لم يقل رقماً بالدينار الليبيّ، **والصفرُ يُخفي الخدمةَ ولو اشتعل
مفتاحُها** (سابقةُ البقشيش والإحالة). **ويُقرأ بـ`for_country`**: سوقٌ بلا صفٍّ = كلُّ مبلغٍ صفر، فلا تظهر خدمةٌ بمبلغٍ مخترع.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode


class ServiceSetting(TimestampMixin, Base):
    __tablename__ = "service_settings"
    __table_args__ = (
        CheckConstraint(
            "guarantee_fee >= 0 AND guarantee_late_minutes > 0 AND guarantee_confirm_minutes > 0 "
            "AND guarantee_confirm_window_minutes > 0 AND guarantee_offer_hours > 0 "
            "AND guarantee_ban_threshold > 0 AND guarantee_ban_days > 0",
            name="service_settings_guarantee_valid",
        ),
        CheckConstraint("parcel_fee >= 0", name="service_settings_parcel_fee_valid"),
        CheckConstraint(
            "hourly_rate >= 0 AND hourly_km_per_hour >= 0 AND hourly_cancel_minutes >= 0 AND hourly_max_hours BETWEEN 1 AND 24",
            name="service_settings_hourly_valid",
        ),
        CheckConstraint(
            "commute_discount_percent >= 0 AND commute_discount_percent < 100 AND commute_captain_incentive >= 0 "
            "AND commute_max_suspend_days >= 0",
            name="service_settings_commute_valid",
        ),
        CheckConstraint("intercity_cancel_deadline_hours BETWEEN 1 AND 48", name="service_settings_intercity_valid"),
        CheckConstraint("cashback_amount >= 0 AND cashback_days BETWEEN 2 AND 14", name="service_settings_cashback_valid"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )

    # ------------------------------------------------ الحجزُ المضمون (§٦٣-ج/٣)
    #: **رسمُ الضمان** — للكبتن حين تتمّ الرحلة، ويُردّ إن لم يوجد كبتن. وصفرٌ يُخفي الخدمة
    guarantee_fee: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    #: تأخّرُ الكبتن عن الموعد بأكثر منها ⇒ يُردّ الرسمُ وللراكب أن يلغي مجّاناً
    guarantee_late_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=10, server_default=text("10")
    )
    #: «هل أنت في الطريق؟» قبل الموعد بها
    guarantee_confirm_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=60, server_default=text("60")
    )
    #: وبلا ردٍّ خلالها يُسحب الحجزُ منه بلا عقوبة
    guarantee_confirm_window_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=10, server_default=text("10")
    )
    #: الحجزُ يُعرض على الكباتن في هذه الساعات قبل موعده
    guarantee_offer_hours: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=24, server_default=text("24")
    )
    #: اعتذاراتٌ بعد التأكيد في الأيام نفسِها تحجبه — **اعتذاران في شهر** بنصِّ المالك
    guarantee_ban_threshold: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=2, server_default=text("2")
    )
    guarantee_ban_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=30, server_default=text("30")
    )

    # ------------------------------------------------ الطرد (§٦٣-ج/٤)
    #: **رسمُ الطرد للكبتن** فوق سعر الاقتصادي — وصفرٌ يُخفي الخدمة
    parcel_fee: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )

    # ------------------------------------------------ بالساعة (§٦٣-ج/٥)
    #: **سعرُ الساعة** شاملاً كيلومتراتِها — وصفرٌ يُخفي الخدمة
    hourly_rate: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    hourly_km_per_hour: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=15, server_default=text("15"))
    #: **إلغاءُ الراكب بعد وصول الكبتن**: هذه الدقائقُ من سعر الساعة للكبتن
    hourly_cancel_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=30, server_default=text("30"))
    hourly_max_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8, server_default=text("8"))

    # ------------------------------------------------ المشوارُ الثابت (§٦٣-ج/٦)
    #: **الخصمُ** — يتقاسمه الكبتنُ وTAXO بقدر نسبة العمولة (§٦٣-ب). وصفرٌ يُخفي الخدمة
    commute_discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00"), server_default=text("0")
    )
    #: **حافزُ الكبتن المعتمد لكلِّ رحلة** — من TAXO، وافتراضُه لا شيء (الشارةُ والأولويّة)
    commute_captain_incentive: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    commute_max_suspend_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=4, server_default=text("4"))

    # ------------------------------------------------ بين المدن (§٦٣-ج/٧)
    #: **المهلةُ قبل الانطلاق** — قبلها يلغي الكبتنُ بلا أثر، وعندها تُلغى رحلةٌ لم تبلغ حدَّها. اقتراحي ساعتان
    intercity_cancel_deadline_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2, server_default=text("2"))

    # ------------------------------------------------ الاسترداد الأسبوعي (§٦٣-ج/٨)
    #: **المبلغُ الثابت** — لم يقل المالكُ رقماً، فصفرٌ يُخفي الخدمة حتى يضبطه
    cashback_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    #: **أيامُ «الأسبوع» بلا جمعته** — ٦ افتراضاً (§٦٣-د/٩)
    cashback_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=6, server_default=text("6"))
