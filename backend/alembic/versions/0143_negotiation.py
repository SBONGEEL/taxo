"""«تفاوض» على السعر، كبتنٌ واحدٌ في كلِّ مرّة (أمرُ المالك ٢٠٢٦-١١-٠٣، SPEC §٩٢، `design/NEGOTIATE.md`).

- `rides.negotiation_offer` · `rides.negotiated_fare` — **فارغان لكلِّ رحلةٍ قائمة**: لا رحلةَ تصير متفاوَضاً عليها بهذه الترحيلة.
- `negotiation_settings` — صفٌّ لكلِّ دولة، **ولا صفَّ يُبذر**: الغيابُ مطفأ، والميزةُ تُشحن مطفأةً (§٩٢-ب).
- `ride_fare_offers` — سجلُّ الأفعال على سعر رحلة، يُكتب ولا يُعدَّل.

**ولا جدولَ مالٍ يُمسّ**: عمودان فارغان على الرحلة وجدولان جديدان فارغان. **والرجوعُ** يحذف الجدولين والعمودين — **ويسقط عمداً إن وُجدت
رحلةٌ متّفقٌ على سعرها** (لا يُمحى سعرٌ دُفع عليه بتراجعٍ صامت).

Revision ID: 0143
Revises: 0142
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0143"
down_revision = "0142"
branch_labels = None
depends_on = None

COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
MONEY = sa.Numeric(12, 3)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.add_column("rides", sa.Column("negotiation_offer", MONEY, nullable=True))
    op.add_column("rides", sa.Column("negotiated_fare", MONEY, nullable=True))

    op.create_table(
        "negotiation_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("min_percent", sa.SmallInteger(), nullable=False, server_default=sa.text("70")),
        sa.Column("min_amount", MONEY, nullable=True),
        sa.Column("driver_timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("20")),
        sa.Column("rider_timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("20")),
        sa.Column("max_counter_percent", sa.SmallInteger(), nullable=True),
        sa.Column("max_drivers", sa.SmallInteger(), nullable=True),
        sa.Column("categories", postgresql.ARRAY(sa.String(length=32)), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
        sa.UniqueConstraint("country_code", name="negotiation_settings_country"),
        sa.CheckConstraint("min_percent BETWEEN 10 AND 100", name="negotiation_min_percent_range"),
        sa.CheckConstraint("min_amount IS NULL OR min_amount >= 0", name="negotiation_min_amount_non_negative"),
        sa.CheckConstraint("driver_timeout_seconds BETWEEN 5 AND 120", name="negotiation_driver_timeout_range"),
        sa.CheckConstraint("rider_timeout_seconds BETWEEN 5 AND 120", name="negotiation_rider_timeout_range"),
        sa.CheckConstraint(
            "max_counter_percent IS NULL OR max_counter_percent BETWEEN 1 AND 500", name="negotiation_counter_cap_range"
        ),
        sa.CheckConstraint("max_drivers IS NULL OR max_drivers BETWEEN 1 AND 50", name="negotiation_max_drivers_range"),
    )

    op.create_table(
        "ride_fare_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", MONEY, nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["ride_id"], ["rides.id"], ondelete="CASCADE", name=op.f("fk_ride_fare_offers_ride_id_rides")
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["drivers.id"], ondelete="SET NULL", name=op.f("fk_ride_fare_offers_driver_id_drivers")
        ),
        sa.CheckConstraint(
            "kind IN ('rider_offer', 'counter', 'driver_accept', 'driver_decline', 'rider_accept', 'rider_reject', 'expired')",
            name="ride_fare_offer_kind",
        ),
    )
    op.create_index("ix_ride_fare_offers_ride_id", "ride_fare_offers", ["ride_id"])


def downgrade() -> None:
    # **لا يُمحى سعرٌ متّفقٌ عليه بتراجعٍ صامت** — رحلةٌ تحمله تُسقط الرجوعَ بعلّته
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM rides WHERE negotiated_fare IS NOT NULL) THEN "
        "RAISE EXCEPTION 'rides carry negotiated_fare — downgrade of 0143 refused'; END IF; END $$"
    )
    op.drop_index("ix_ride_fare_offers_ride_id", table_name="ride_fare_offers")
    op.drop_table("ride_fare_offers")
    op.drop_table("negotiation_settings")
    op.drop_column("rides", "negotiated_fare")
    op.drop_column("rides", "negotiation_offer")
