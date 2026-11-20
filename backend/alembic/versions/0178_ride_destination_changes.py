"""**تاريخُ «تعديل الوجهة»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ) — جدولٌ جديدٌ لا يمسّ صفّاً قائماً.

صفٌّ لكلِّ عرضٍ رآه الراكب (قبل التأكيد وبعده)، **ولا يُغيّر جدولاً قائماً ولا صفّاً**: الرحلةُ تتغيّر بتأكيد الراكب في الخدمة، لا هنا.
**ولا مفتاحَ ميزةٍ يُكتب**: غيابُ الصفّ في `feature_flags` = مطفأ، فالدولُ الثلاثُ مطفأةٌ بعد الرفع حتى يشعلها المالك.

**والرجوعُ** يحذف الجدول — وما عليه تاريخُ عروضٍ لا مال: الأجرةُ المؤكَّدةُ مكتوبةٌ على الرحلة نفسِها (`estimated_fare`).

Revision ID: 0178
Revises: 0177
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0178"
down_revision = "0177"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(12, 3)


def upgrade() -> None:
    op.create_table(
        "ride_destination_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("old_lat", sa.Float(), nullable=False),
        sa.Column("old_lng", sa.Float(), nullable=False),
        sa.Column("old_address", sa.String(255), nullable=True),
        sa.Column("new_lat", sa.Float(), nullable=False),
        sa.Column("new_lng", sa.Float(), nullable=False),
        sa.Column("new_address", sa.String(255), nullable=True),
        sa.Column("old_fare", MONEY, nullable=False),
        sa.Column("new_fare", MONEY, nullable=False),
        sa.Column("shown_fare", MONEY, nullable=False),
        sa.Column("new_fare_lines", postgresql.JSONB(), nullable=True),
        sa.Column("new_distance_km", sa.Numeric(8, 3), nullable=False),
        sa.Column("new_duration_min", sa.Numeric(8, 2), nullable=False),
        sa.Column("traveled_km", sa.Numeric(8, 3), nullable=True),
        sa.Column("new_captain_fees", MONEY, nullable=False, server_default=sa.text("0")),
        sa.Column("new_facility_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("facilities.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ride_destination_changes_ride_id", "ride_destination_changes", ["ride_id"])


def downgrade() -> None:
    op.drop_index("ix_ride_destination_changes_ride_id", table_name="ride_destination_changes")
    op.drop_table("ride_destination_changes")
