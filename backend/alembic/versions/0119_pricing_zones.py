"""مناطقُ التسعير (SPEC §٧٤-أ/٥) — جدولان وعمودٌ على الرحلة، **ولا جدولَ مالٍ يُمسّ**.

**ما تضيفه**:
- `pricing_zones` — منطقةٌ بمضلّعها (`geography(MULTIPOLYGON)` بفهرسٍ مكانيّ)، ووسمُ «وعرة»، ووجهُ التعديل (نسبةٌ — افتراضاً ٢٥ — أو جدول).
- `zone_pricing_rules` — جدولُ أسعار منطقةٍ لكلِّ فئةٍ حين يكون وجهُها «جدول».
- `rides.pricing_zone_id` — المنطقةُ التي سُعِّرت بها الرحلة، تُجمَّد لحظةَ الطلب كالمرفق.

**ولا صفَّ يُبذر هنا**: الحدودُ تُحمَّل من ملفّاتها بسكربتٍ مستقلّ (`scripts/load_pricing_zones.py`) — **فالترحيلةُ لا تحمل ثلاثمئة ألف بايتٍ
من الإحداثيّات**، وسوقٌ بلا مناطق سعرُه موحَّدٌ كما كان حرفاً.

**و`downgrade` يقف** إن سُعِّرت رحلةٌ بمنطقة، أو وُسمت منطقةٌ «وعرة»، أو كُتب جدولُ منطقة — قرارُ مالكٍ أو أثرُه على رحلةٍ لا يُمحى بنزول.

Revision ID: 0119
Revises: 0118
"""

from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None

COUNTRY_CODE = postgresql.ENUM(name="country_code", create_type=False)


def upgrade() -> None:
    op.create_table(
        "pricing_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY_CODE, nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name_ar", sa.String(80), nullable=False),
        sa.Column("name_fr", sa.String(80), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column(
            "area",
            geoalchemy2.Geography(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("rugged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("adjustment_mode", sa.String(8), nullable=False, server_default=sa.text("'percent'")),
        sa.Column("adjustment_percent", sa.Numeric(5, 2), nullable=False, server_default=sa.text("25.00")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("country_code", "code", name="uq_pricing_zone_code"),
        sa.CheckConstraint("adjustment_mode IN ('percent', 'table')", name="pricing_zone_mode_valid"),
        sa.CheckConstraint("adjustment_percent >= 0 AND adjustment_percent <= 200", name="pricing_zone_percent_range"),
    )
    op.create_index("ix_pricing_zones_country_code", "pricing_zones", ["country_code"])
    op.create_index("ix_pricing_zones_area", "pricing_zones", ["area"], postgresql_using="gist")

    op.create_table(
        "zone_pricing_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pricing_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_category", sa.String(32), nullable=False),
        sa.Column("base_fare", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_per_km", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_per_min", sa.Numeric(12, 3), nullable=False),
        sa.Column("minimum_fare", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("zone_id", "vehicle_category", name="uq_zone_pricing_rule"),
        sa.CheckConstraint(
            "base_fare >= 0 AND price_per_km >= 0 AND price_per_min >= 0 AND minimum_fare >= 0",
            name="zone_pricing_rule_not_negative",
        ),
    )
    op.create_index("ix_zone_pricing_rules_zone_id", "zone_pricing_rules", ["zone_id"])

    op.add_column(
        "rides",
        sa.Column("pricing_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pricing_zones.id"), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    held = {
        "rides.pricing_zone_id": bind.execute(sa.text("SELECT count(*) FROM rides WHERE pricing_zone_id IS NOT NULL")).scalar_one(),
        "pricing_zones.rugged": bind.execute(sa.text("SELECT count(*) FROM pricing_zones WHERE rugged")).scalar_one(),
        "zone_pricing_rules": bind.execute(sa.text("SELECT count(*) FROM zone_pricing_rules")).scalar_one(),
    }
    written = {name: count for name, count in held.items() if count}
    if written:
        raise RuntimeError(
            f"مناطقُ التسعير تحمل ما لا يُمحى بنزول ({written}) — رحلاتٌ سُعِّرت بها، أو وسمُ «وعرة» وجداولُ كتبها المالك. "
            "أعدها إلى افتراضها من «مناطق التسعير» بقرارٍ ثمّ أعد النزول."
        )
    op.drop_column("rides", "pricing_zone_id")
    op.drop_index("ix_zone_pricing_rules_zone_id", table_name="zone_pricing_rules")
    op.drop_table("zone_pricing_rules")
    op.drop_index("ix_pricing_zones_area", table_name="pricing_zones")
    op.drop_index("ix_pricing_zones_country_code", table_name="pricing_zones")
    op.drop_table("pricing_zones")
