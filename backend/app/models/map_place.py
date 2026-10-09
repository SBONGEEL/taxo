"""**أماكنُ المالك على الخريطة** (SPEC §٧١-د/١٤) — اسمٌ عربيٌّ وإنجليزيّ، وفئةٌ، وموقعٌ، ودولة، وإخفاء.

**ولمَ جدولٌ جديدٌ لا أعمدةٌ في `facilities`** (§٧١-ز/د): ذاك جدولُ **رسمِ مال** — مضلّعٌ ورسمُ كبتنٍ يُحسب على الرحلة — **وصفُّ مكانٍ
يُضاف ليُقرأ اسمُه لا يجوز أن يقف على بُعد عمودٍ من رسمٍ يُحصَّل**. والمطاراتُ تظهر مع الأماكن **قراءةً** من بيتها
(`facilities.airports_for_rider`) لا نسخةً هنا.

**وما يفعله الصفّ**: يُرسم اسمُه على خرائط التطبيقين **فوق أسماء المزوّد** (فيصحّح اسماً خاطئاً أو ناقصاً هناك)، **ويتقدّم نتائجَ
البحث** حين يطابق. **والمخفيُّ لا يُرسم ولا يُبحث** ويبقى في اللوحة. **ولا حذف**: الإخفاءُ هو الإيقاف — كسائر ما في المشروع.

**والموقعُ رقمان لا `geography`**: لا استعلامَ مكانيَّ في القاعدة — الأماكنُ مئاتٌ لا ملايين، **والقربُ يُحسب بعد القراءة** في الخدمة.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, MapPlaceCategory

#: **الفئاتُ من التعداد** (`MapPlaceCategory`) — **ونصٌّ محروسٌ بقيدٍ لا `ENUM`** في القاعدة (سابقةُ `saved_places.icon`).
MAP_PLACE_CATEGORIES: tuple[str, ...] = tuple(category.value for category in MapPlaceCategory)


def _categories_check() -> str:
    return "category IN (" + ", ".join(f"'{value}'" for value in MAP_PLACE_CATEGORIES) + ")"


class MapPlace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "map_places"
    __table_args__ = (
        CheckConstraint(_categories_check(), name="map_place_category_valid"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="map_place_point_valid"),
        CheckConstraint("char_length(btrim(name_ar)) >= 2", name="map_place_name_ar_present"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    #: **اختياريّ** — يُبحث به ويُعرض حيث يغيب العربيّ في غير هذا الجدول؛ وهنا العربيُّ إلزاميّ
    name_en: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<MapPlace {self.country_code} {self.name_ar}>"
