"""**اسمٌ عربيٌّ يكتبه المشرفُ لمكانٍ على الخريطة بلا اسمٍ عربيّ** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب).

المكانُ من مربّعاتنا المفتوحة (`places-search`)، **ومفتاحُه `okey` ثابتٌ عبر البناءات** (`n123` · `w456` · `r789` من OSM، و`o<id>`
من Overture). **والتطبيقان يرسمان هذا الاسمَ فوق اسم المربّع** بالمفتاح — فلا ينتظر البناءَ الشهريّ القادم.
**ولا مالَ هنا**: اسمٌ يُرسم وحدَه. **والإزالةُ حذفُ صفِّ اسمٍ لا بيانات مستخدم**، ويُختم في التدقيق.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode


class MapNameFix(TimestampMixin, Base):
    __tablename__ = "map_name_fixes"

    okey: Mapped[str] = mapped_column(String(40), primary_key=True)
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    #: الاسمُ كما في المربّع يومَ كُتب العربيّ — ليقرأ المشرفُ ما صحّحه
    original_name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
