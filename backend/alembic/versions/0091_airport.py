"""المطار (SPEC §٦٣-ج/٢) — المرافقُ الحيويّة بمضلّعاتها ورسومها، ورسمُ الكبتن مجمَّداً على الرحلة، و«طلبات المطار» على الكبتن.

**ثلاثةُ أشياء، وكلُّها تصف القائمَ حرفاً بافتراضها**: `rides.captain_fees_at_ride = 0` (لا رحلةَ قائمةً تحمل رسماً) ·
`rides.facility_id = NULL` · `drivers.accepts_airport = false` (**مطفأٌ حتى يشعله الكبتنُ بنفسه** — قرارُ المالك) — **فلا تعبئةَ ولا تخمين**.

**ومطارا الإطلاق يُبذران هنا** لا في سكربت البذر: الإنتاجُ يرحّل ولا يبذر، **والمالكُ قال «مطارا الإطلاق»** فيجب أن يوجدا حيث يُشعِل.
**ومضلّعاهما تقريبيّان يضبطهما المالكُ على الخريطة** (صفحةُ «المرافق الحيوية»). **والملكةُ علياء برسم 1.000 د.أ** بنصِّه، **ومعيتيقة
بصفر** — لم يقل رقماً بالدينار الليبيّ، **والصفرُ لا يُطبَّق** (لا رسمَ من تخمين). **والمفتاحُ `airport_enabled` مطفأٌ** فلا يمسّ رحلةً.

**وليس جدولَ مالٍ يُمسّ قائمُه**: `rides` تكتسب عموداً بصفرٍ يصف كلَّ صفٍّ قائم، ولا يتغيّر مبلغٌ ولا قيد.

**و`downgrade` مقيسٌ لا مقروء**: يحذف الجدولَ والأعمدة — وثمنُه أن رحلةً جاريةً تحمل رسمَ مطارٍ تبقى أجرتُها كما جُمّدت (الرسمُ داخل
`estimated_fare` وسطرُه في `fare_lines`) **لكن العمولةَ تُحسب عليه كلِّه**: الاستثناءُ يقرأ العمودَ المحذوف.

Revision ID: 0091
Revises: 0090
"""

from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None

QUEEN_ALIA = "SRID=4326;POLYGON((35.965 31.700, 36.010 31.700, 36.010 31.745, 35.965 31.745, 35.965 31.700))"
MITIGA = "SRID=4326;POLYGON((13.262 32.884, 13.296 32.884, 13.296 32.902, 13.262 32.902, 13.262 32.884))"


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "country_code",
            postgresql.ENUM("LY", "JO", name="country_code", create_type=False),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), server_default=sa.text("'airport'"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "area",
            geoalchemy2.types.Geography(
                geometry_type="POLYGON", srid=4326, spatial_index=False,
                from_text="ST_GeogFromText", name="geography",
            ),
            nullable=False,
        ),
        sa.Column("fee", sa.Numeric(12, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('airport')", name=op.f("ck_facilities_facility_kind_valid")),
        sa.CheckConstraint("fee >= 0", name=op.f("ck_facilities_facility_fee_not_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facilities")),
    )
    op.create_index(op.f("ix_facilities_country_code"), "facilities", ["country_code"])
    op.create_index("ix_facilities_area", "facilities", ["area"], postgresql_using="gist")
    op.execute(
        "INSERT INTO facilities (id, country_code, kind, name, area, fee, is_active) VALUES "
        f"(gen_random_uuid(), 'JO', 'airport', 'مطار الملكة علياء الدولي', ST_GeogFromText('{QUEEN_ALIA}'), 1.000, true), "
        f"(gen_random_uuid(), 'LY', 'airport', 'مطار معيتيقة الدولي', ST_GeogFromText('{MITIGA}'), 0.000, true)"
    )

    op.add_column("rides", sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_rides_facility_id_facilities"), "rides", "facilities", ["facility_id"], ["id"]
    )
    op.add_column(
        "rides",
        sa.Column("captain_fees_at_ride", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        "ride_captain_fees_not_negative", "rides", "captain_fees_at_ride >= 0"
    )
    op.add_column(
        "drivers",
        sa.Column("accepts_airport", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("drivers", "accepts_airport")
    op.drop_constraint(op.f("ck_rides_ride_captain_fees_not_negative"), "rides", type_="check")
    op.drop_column("rides", "captain_fees_at_ride")
    op.drop_constraint(op.f("fk_rides_facility_id_facilities"), "rides", type_="foreignkey")
    op.drop_column("rides", "facility_id")
    op.drop_index("ix_facilities_area", table_name="facilities")
    op.drop_index(op.f("ix_facilities_country_code"), table_name="facilities")
    op.drop_table("facilities")
