"""**ما يضيفه الناسُ إلى الخريطة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع): `place_suggestions` و`road_reports` و`road_report_votes`، ومصدرٌ
ثالثٌ لـ`map_places` هو `community` (اقتراحٌ وافق عليه المشرف).

**لا جدولَ مالٍ هنا ولا عمودَ في جدول مال** — ولا صفَّ قائماً يتغيّر: ثلاثةُ جداولَ فارغة، وقيدُ `source` يتّسع ولا يضيق.
**والرجوعُ** يحذف الثلاثة ويعيد القيدَ كما كان — **ويُرفض إن وُجد صفٌّ بمصدر `community`** (فلا يُمحى ما وافق عليه المشرف بصمت).

Revision ID: 0175
Revises: 0174
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0175"
down_revision = "0174"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — الترحيلةُ تبقى كما كُتبت
_CATEGORIES = (
    "market", "shop", "mall", "mosque", "church", "hospital", "clinic", "school", "university", "hotel",
    "restaurant", "landmark", "government", "station", "neighborhood", "street", "other", "airport", "pickup",
)
_COUNTRY = postgresql.ENUM(name="country_code", create_type=False)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # **العمودُ يتّسع قبل القيد**: «community» تسعةُ أحرف و`source` كان `VARCHAR(8)` — توسيعٌ لا يعيد كتابةَ صفّ
    op.alter_column("map_places", "source", existing_type=sa.String(8), type_=sa.String(16), existing_nullable=False)
    op.drop_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", "source IN ('owner', 'osm', 'community')")

    op.create_table(
        "place_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", _COUNTRY, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("current_name", sa.String(120), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(300), nullable=True),
        sa.Column("map_place_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("kind", ("add", "fix")), name=op.f("ck_place_suggestions_place_suggestion_kind_valid")),
        sa.CheckConstraint(_in("status", ("pending", "approved", "rejected")), name=op.f("ck_place_suggestions_place_suggestion_status_valid")),
        sa.CheckConstraint(_in("category", _CATEGORIES), name=op.f("ck_place_suggestions_place_suggestion_category_valid")),
        sa.CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name=op.f("ck_place_suggestions_place_suggestion_point_valid")),
        sa.CheckConstraint("char_length(btrim(name_ar)) >= 2", name=op.f("ck_place_suggestions_place_suggestion_name_present")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_place_suggestions_user_id_users")),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_place_suggestions_reviewed_by_users")),
        sa.ForeignKeyConstraint(["map_place_id"], ["map_places.id"], name=op.f("fk_place_suggestions_map_place_id_map_places")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_suggestions")),
    )
    op.create_index(op.f("ix_place_suggestions_country_code"), "place_suggestions", ["country_code"])
    op.create_index(op.f("ix_place_suggestions_user_id"), "place_suggestions", ["user_id"])

    op.create_table(
        "road_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", _COUNTRY, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default=sa.text("'active'")),
        sa.Column("confirmations", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("kind", ("works", "closed", "accident", "jam")), name=op.f("ck_road_reports_road_report_kind_valid")),
        sa.CheckConstraint(_in("status", ("active", "removed")), name=op.f("ck_road_reports_road_report_status_valid")),
        sa.CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name=op.f("ck_road_reports_road_report_point_valid")),
        sa.CheckConstraint("confirmations >= 1", name=op.f("ck_road_reports_road_report_confirmations_positive")),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_road_reports_reviewed_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_road_reports")),
    )
    op.create_index(op.f("ix_road_reports_country_code"), "road_reports", ["country_code"])
    op.create_index(op.f("ix_road_reports_expires_at"), "road_reports", ["expires_at"])

    op.create_table(
        "road_report_votes",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["road_reports.id"], name=op.f("fk_road_report_votes_report_id_road_reports")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_road_report_votes_user_id_users")),
        sa.PrimaryKeyConstraint("report_id", "user_id", name=op.f("pk_road_report_votes")),
    )


def downgrade() -> None:
    community = op.get_bind().execute(sa.text("SELECT count(*) FROM map_places WHERE source = 'community'")).scalar()
    if community:
        raise RuntimeError(f"{community} مكاناً وافق عليه المشرفُ بمصدر community — لا يُرجَع عنها بصمت")
    op.drop_table("road_report_votes")
    op.drop_index(op.f("ix_road_reports_expires_at"), table_name="road_reports")
    op.drop_index(op.f("ix_road_reports_country_code"), table_name="road_reports")
    op.drop_table("road_reports")
    op.drop_index(op.f("ix_place_suggestions_user_id"), table_name="place_suggestions")
    op.drop_index(op.f("ix_place_suggestions_country_code"), table_name="place_suggestions")
    op.drop_table("place_suggestions")
    op.drop_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", type_="check")
    op.create_check_constraint(op.f("ck_map_places_map_place_source_valid"), "map_places", "source IN ('owner', 'osm')")
    op.alter_column("map_places", "source", existing_type=sa.String(16), type_=sa.String(8), existing_nullable=False)
