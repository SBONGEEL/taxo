"""ساعاتُ العمل (SPEC §٦٢-ج/٣٧، §٦٤-ج) — دقائقُ يومٍ لكلِّ كبتن ومجموعُ شهرٍ بعد ثلاثةَ عشرَ شهراً. **ولا موقعَ يُحفظ.**

**جدولان جديدان فارغان، ولا جدولَ مالٍ يُمسّ.** **و`downgrade` مقيسٌ لا مقروء.**

Revision ID: 0099
Revises: 0098
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_activity_days",
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("online_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("online_minutes BETWEEN 0 AND 1440", name=op.f("ck_driver_activity_days_activity_day_minutes")),
    )
    op.create_table(
        "driver_activity_months",
        sa.Column("driver_id", sa.Uuid(), sa.ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("month", sa.Date(), primary_key=True),
        sa.Column("online_minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint("online_minutes >= 0", name=op.f("ck_driver_activity_months_activity_month_minutes")),
    )


def downgrade() -> None:
    op.drop_table("driver_activity_months")
    op.drop_table("driver_activity_days")
