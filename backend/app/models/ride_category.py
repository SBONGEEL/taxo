"""فئاتُ الرحلة لكلِّ دولة (SPEC §٦٧، الترحيلة `0110`) — **الفئةُ بيانٌ لا تعداد**.

**المدمجتان** (`economy` · `comfort`، `is_builtin`) تعملان بقاعدة اليوم حرفاً: فئةُ المركبة = فئةُ الطلب، وأسعارُهما صفّاهما في `pricing_rules`.
**والجديدةُ** يضعها المشرف — **مطفأةً افتراضاً** — بأسعارها في `pricing_rules` نفسِه وشروطِ مركبتها، **ويأخذها من تستوفي مركبتُه شروطَها أو
من مُنحها يدوياً، إلا من نُزعت منه يدوياً** (`DriverCategoryAccess`). والقاعدةُ في `services/categories.py`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ARRAY, Boolean, CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class RideCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ride_categories"
    __table_args__ = (
        UniqueConstraint("country_code", "key"),
        # **مفتاحٌ ثابتٌ لاتينيٌّ صغير** — يُكتب على الرحلات والأسعار والمركبات، فلا يتغيّر بعد الإنشاء (الخدمةُ ترفض تعديلَه)
        CheckConstraint("key ~ '^[a-z][a-z0-9_]{1,31}$'", name="ride_category_key_shape"),
        CheckConstraint(
            "seats BETWEEN 1 AND 20 AND (min_seats IS NULL OR min_seats BETWEEN 1 AND 20) "
            "AND (min_year IS NULL OR min_year BETWEEN 1990 AND 2100)",
            name="ride_category_ranges",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False)
    #: **ما يراه الراكب تحت الاسم** — قصير
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seats: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=4, server_default=text("4"))
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    #: **مطفأةٌ افتراضاً** (§٦٧-ب/١٠) — ولا تُشعَل بلا أسعارٍ موجبة (`categories.require_priced`)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    #: **«اقتصادي» و«مريحة»** — بقاعدة اليوم حرفاً، ومفتاحُهما لا يُحذف
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    # ── شروطُ المركبة للفئة الجديدة — **فارغٌ = لا شرط**؛ وصفةُ مركبةٍ فارغةٌ لا تستوفي شرطاً مكتوباً
    allowed_body_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'")
    )
    allowed_fuels: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list, server_default=text("'{}'"))
    min_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    min_seats: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class DriverCategoryAccess(UUIDMixin, TimestampMixin, Base):
    """**منحُ المشرف فئةً جديدةً لكبتنٍ أو نزعُها منه** — صفٌّ واحدٌ لكلِّ (كبتنٍ، فئة)، والسجلُّ في التدقيق."""

    __tablename__ = "driver_category_access"
    __table_args__ = (UniqueConstraint("driver_id", "category_id"),)

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("ride_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: `True` منحٌ · `False` نزع
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(280), nullable=True)
