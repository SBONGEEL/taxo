"""مركباتُ الكراج والمتجر (قرارُ المالك 2026-08-22).

**وهي زينةٌ لا مركبةٌ حقيقية**: `vehicles` صفٌّ يحمل لوحةً وفئةَ تسعيرةٍ
ووثيقةً تُراجَع، وهذا **شكلٌ يُرسم**. وخلطُهما يجعل تغييرَ شكلٍ يمرّ بمراجعة
وثائق، أو يجعل شراءَ زينةٍ يغيّر تعريفةَ رحلة.

**والمِلكيّةُ للحساب لا للمركبة** (قرارُ المالك): كبتنٌ يملك سيارتين يملك
**مركبةً نشطةً واحدة**، تظهر مهما كانت السيارةُ التي يقودها اليوم.

**والكميّةُ محسوبةٌ لا مخزَّنة**: «المتبقّي» = `max_supply` ناقص عددَ
المالكين — قاعدةُ «لا عمودَ رصيد» نفسُها. عمودُ عدّادٍ يُنقَص يدوياً يفترق
عن الحقيقة أوّلَ منحةٍ إداريةٍ أو استرجاعِ صفّ، **وحينها يبيع المتجرُ ما
ليس عنده أو يمنع ما عنده**.

**والندرةُ نصٌّ لا تعداد Postgres** — كـ`discount_type` في عروض الاشتراكات:
إضافةُ درجةٍ خامسةٍ غداً كودٌ بلا ترحيلة.

**وأين تُرى مكتوبٌ في الصفّ لا مستنتَجٌ من الندرة**: `visible_before_accept`.
النادرةُ والأسطوريةُ لا تُنشران على الخريطة الحرّة لأن **ما يُرى ويندر يصير
معرّفاً** ينقض تجهيلَ §10 — والحقلُ يجعل القاعدةَ **قابلةً للقراءة في صفّ**
بدل أن تكون شرطاً في كودٍ يُنسى عند البابِ الثالث.
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
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode

#: درجاتُ الندرة — **والقيمةُ نصٌّ**، فدرجةٌ جديدةٌ لا تحتاج ترحيلة
RARITY_COMMON = "common"
RARITY_PREMIUM = "premium"
RARITY_RARE = "rare"
RARITY_LEGENDARY = "legendary"
RARITIES = (RARITY_COMMON, RARITY_PREMIUM, RARITY_RARE, RARITY_LEGENDARY)

#: **ما يُنشر على الخريطة الحرّة** — والباقي بعد القبول وحده
PUBLIC_RARITIES = (RARITY_COMMON, RARITY_PREMIUM)

#: مصدرُ التملّك — يُقرأ في التقارير: كم بيع وكم وُهب
SOURCE_GIFT = "gift"
SOURCE_PURCHASE = "purchase"
SOURCE_GRANT = "grant"
SOURCES = (SOURCE_GIFT, SOURCE_PURCHASE, SOURCE_GRANT)


class VehicleSkin(TimestampMixin, Base):
    """مركبةٌ في الكتالوج — **عالميةٌ**، وسعرُها لكلِّ سوقٍ على حدة.

    **ولمَ الكتالوجُ عالميٌّ والسعرُ سوقيّ**: الرسمةُ والاسمُ والندرةُ صفاتُ
    المركبة، والسعرُ والعملةُ **واقعةُ سوق** — والعملةُ في هذا المشروع تُشتقّ
    من الدولة ولا تُقبل من عميل. وصفٌّ لكلِّ سوقٍ يعني رفعَ الرسمة مرتين
    و«أسطوريةً» محدودةً في سوقٍ ووافرةً في آخر، وهي **ندرةٌ لا يفهمها أحد**.
    """

    __tablename__ = "vehicle_skins"
    __table_args__ = (
        CheckConstraint(
            "rarity IN ('common','premium','rare','legendary')",
            name="vehicle_skins_rarity",
        ),
        # **الكميّةُ إمّا غيرُ محدودةٍ (NULL) وإمّا موجبة** — والنفادُ يُقرأ من
        # عدد المالكين لا من تصفير الحقل، وإلا صار للصفر معنيان
        CheckConstraint(
            "max_supply IS NULL OR max_supply > 0",
            name="vehicle_skins_supply",
        ),
        CheckConstraint(
            "level_required IS NULL OR level_required > 0",
            name="vehicle_skins_level",
        ),
        # **نافذةُ الموسم مرتَّبة** — نهايةٌ قبل بدايةٍ نافذةٌ لا تُفتح أبداً،
        # وتُقرأ «لم تبدأ بعد» إلى الأبد
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from",
            name="vehicle_skins_season",
        ),
        Index("ix_vehicle_skins_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #: اسمٌ عربيٌّ له شخصية — لا رقمٌ ولا رمز
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rarity: Mapped[str] = mapped_column(String(16), nullable=False)

    #: **رسمةُ المستودع** — ملفٌّ في `app/assets/skins/` لِما وُلِّد SVGاً،
    #: **أو** مسارٌ في التخزين لِما رُفع من اللوحة. أحدهما لا كلاهما.
    asset_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    store_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    map_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: **نسبةُ عرضٍ على الخريطة** يضبطها المشرف بعد المعاينة (٨٠–١٢٠٪)
    map_scale_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("100")
    )
    #: **أتدور مع الاتجاه؟** — العلويّةُ المرسومةُ تدور، والرندرُ الواقعيُّ لا
    map_rotates: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    #: **أين تُرى** — مكتوبٌ لا مستنتَج (التفصيل فوق الملف)
    visible_before_accept: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    #: `NULL` بلا حدّ
    max_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_required: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: **هديةُ أول اشتراك** — تُمنح مرةً في عمر الحساب
    is_gift: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    #: **البديلُ المنشور** لمن مركبتُه لا تُنشر قبل القبول (التفصيل في الخدمة)
    is_public_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    #: سِمةُ الخدمة النسائية — وظهورُها يضبطه المشرف
    is_feminine: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    feminine_drivers_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class VehicleSkinPrice(TimestampMixin, Base):
    """سعرُ مركبةٍ في سوقٍ — **والعملةُ تُشتقّ من الدولة** ولا تُخزَّن هنا."""

    __tablename__ = "vehicle_skin_prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="vehicle_skin_prices_positive"),
    )

    skin_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vehicle_skins.id", ondelete="CASCADE"),
        primary_key=True,
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class DriverVehicleSkin(TimestampMixin, Base):
    """مركبةٌ يملكها كبتن — **صفٌّ لا يُحذف**.

    **والسعرُ مجمَّدٌ هنا** كـ`commission_percent_at_ride`: تعديلُ سعرِ
    المركبة غداً لا يحرّك ما دُفع أمس، **و«كم أنفق الكباتن»** يبقى له جوابٌ
    واحدٌ بعد أيِّ تعديل.
    """

    __tablename__ = "driver_vehicle_skins"
    __table_args__ = (
        UniqueConstraint("driver_id", "skin_id", name="uq_driver_skin"),
        CheckConstraint(
            "source IN ('gift','purchase','grant')", name="driver_skins_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skin_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # **`RESTRICT` كعروض الاشتراكات**: مركبةٌ اشتراها كباتنُ لا تُحذف —
        # حذفُها يمحو سببَ ما دفعوه
        ForeignKey("vehicle_skins.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    price_paid: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    #: **الورقةُ الاحتفاليةُ تُعرض مرةً** — و`NULL` تعني «لم تُعرض بعد»
    seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
