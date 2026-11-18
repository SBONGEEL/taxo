"""**ما يضيفه الناسُ إلى الخريطة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع): اقتراحاتُ الأماكن (المهمّة ٢-٣) وبلاغاتُ الطريق (المهمّة ٣-٣).

**لا شيءَ هنا يُرى قبل حكم**: الاقتراحُ لا يظهر إلا بموافقة المشرف — فيصير صفّاً في `map_places` بمصدر `community` — **والبلاغُ لا يظهر
إلا بتأكيد كباتنَ آخرين أو موافقة المشرف**، وينتهي وحدَه بعمرِ نوعه. **ولا مالَ هنا ولا حذف**: الرفضُ والإزالةُ حالٌ لا محو.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode
from app.models.map_place import MAP_PLACE_CATEGORIES

SUGGESTION_KINDS = ("add", "fix")
SUGGESTION_STATUSES = ("pending", "approved", "rejected")
ROAD_REPORT_KINDS = ("works", "closed", "accident", "jam")
ROAD_REPORT_STATUSES = ("active", "removed")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class PlaceSuggestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "place_suggestions"
    __table_args__ = (
        CheckConstraint(_in("kind", SUGGESTION_KINDS), name="place_suggestion_kind_valid"),
        CheckConstraint(_in("status", SUGGESTION_STATUSES), name="place_suggestion_status_valid"),
        CheckConstraint(_in("category", MAP_PLACE_CATEGORIES), name="place_suggestion_category_valid"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="place_suggestion_point_valid"),
        CheckConstraint("char_length(btrim(name_ar)) >= 2", name="place_suggestion_name_present"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    #: **صاحبُ الاقتراح للمراجعة وحدَها** — لا يُعرض على الخريطة ولا لأحدٍ غير المشرف
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(80), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    #: **ما يُصحَّح** — الاسمُ كما رآه على الخريطة (لتصحيحٍ)، فيراه المشرفُ بجانب المقترَح
    current_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", server_default=text("'pending'"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: **الصفُّ الذي وُلد من الموافقة** — `map_places.source = 'community'`
    map_place_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("map_places.id"), nullable=True)


class RoadReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "road_reports"
    __table_args__ = (
        CheckConstraint(_in("kind", ROAD_REPORT_KINDS), name="road_report_kind_valid"),
        CheckConstraint(_in("status", ROAD_REPORT_STATUSES), name="road_report_status_valid"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="road_report_point_valid"),
        CheckConstraint("confirmations >= 1", name="road_report_confirmations_positive"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active", server_default=text("'active'"))
    #: **كم كبتناً مختلفاً بلّغ عنه** — من `road_report_votes` لا يُكتب بيد
    confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class RoadReportVote(Base):
    """**كبتنٌ واحدٌ صوتٌ واحد** — المفتاحُ المركّب يمنع أن يؤكّد كبتنٌ بلاغه مرّتين."""

    __tablename__ = "road_report_votes"

    report_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("road_reports.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
