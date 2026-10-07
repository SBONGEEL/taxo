"""المرافقُ الحيويّة — المطاراتُ أوّلاً (SPEC §٦٣-ج/٢، قرارُ المالك ٢٠٢٦-١٠-٠٧).

**رحلةٌ تبدأ أو تنتهي داخل منطقة مرفقٍ مفعَّل تحمل رسمَه للكبتن** — مجمَّداً لحظةَ إنشائها كالعمولة، **وكاملاً بلا عمولة**
(§٦٣-ب، والسؤالُ ١ يطلب تأكيدَه). **والرسمُ للمرفق لا للسوق**: لكلِّ مطارٍ رسمُه، وافتراضُ الملكة علياء **1.000 د.أ** بنصِّ المالك،
**ومعيتيقة صفرٌ** حتى يضبطه بالدينار الليبيّ — **ومرفقٌ رسمُه صفرٌ لا يُطبَّق** (لا رسمَ من تخمين).

**والمنطقةُ مضلّعٌ يرسمه المالكُ على الخريطة** (`geography(POLYGON)`) — لا دائرةٌ حول نقطة: المطارُ مدرجٌ وطرقٌ ومواقف، ودائرةٌ تبتلع
بلدةً مجاورةً أو تقصّر عن بوابة الوصول. **والسؤالُ «أهذه النقطةُ داخله؟» يُسأل للقاعدة** (`ST_Covers`) لا يُحسب في بايثون.

**ولا حذف**: المرفقُ يُطفأ (`is_active`) ولا يُمحى — رحلاتٌ قديمةٌ تشير إليه، **والحذفُ على جدولٍ يمسّ المال ممنوعٌ على الإنتاج**.
"""

from __future__ import annotations

from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import Boolean, CheckConstraint, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

#: أنواعُ المرافق — **المطارُ وحدَه اليوم**، والعمودُ نصٌّ بقيدٍ فيُضاف غيرُه بتعديل القيد لا بترحيلة نوع
FACILITY_AIRPORT = "airport"


class Facility(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("kind IN ('airport')", name="facility_kind_valid"),
        CheckConstraint("fee >= 0", name="facility_fee_not_negative"),
        Index("ix_facilities_area", "area", postgresql_using="gist"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FACILITY_AIRPORT, server_default=text("'airport'")
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    #: **فهرسٌ مكانيٌّ صريحٌ في `__table_args__`** لا ضمنيٌّ من geoalchemy — فالترحيلةُ والنموذجُ يسمّيانه اسماً واحداً
    area = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    #: **رسمُ الكبتن على رحلةٍ تمسّ هذا المرفق** — بعملة سوقه، وصفرٌ = لا يُطبَّق
    fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.000"))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
