"""إعداداتُ الخدمات الجديدة لكلِّ سوق (SPEC §٦٣-ج) — **صفٌّ واحدٌ لكلِّ سوق، وعمودٌ لكلِّ مبلغٍ أو عتبة**، تضيفه ترحيلةُ خدمته.

**وأرقامُ المالك افتراضاتٌ للأردن**، **ولليبيا صفرٌ في كلِّ مبلغ** — لم يقل رقماً بالدينار الليبيّ، **والصفرُ يُخفي الخدمةَ ولو اشتعل
مفتاحُها** (سابقةُ البقشيش والإحالة). **ويُقرأ بـ`for_country`**: سوقٌ بلا صفٍّ = كلُّ مبلغٍ صفر، فلا تظهر خدمةٌ بمبلغٍ مخترع.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, SmallInteger, text
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
