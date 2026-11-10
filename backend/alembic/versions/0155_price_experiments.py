"""تجاربُ الأسعار (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤، SPEC §٩٧/٤).

**تمسّ التسعير** — فتُعرض على المالك قبل الرفع:
- جدولٌ جديد `price_experiments` (النسبةُ والنطاقُ والمدّةُ والحال)؛
- **عمودان فارغان على `rides`**: التجربةُ التي سُعِّرت بها الرحلة وذراعُها. **لا صفَّ قائمٌ يتغيّر**، ولا قيدَ في الدفتر.
- **والمفتاحُ `price_experiments_enabled` مطفأ** — لا تجربةَ تُسعِّر رحلةً قبل أن يُشعله المالكُ ويبدأ تجربة.

**والنزولُ** يحذف العمودين والجدول — **ويسقط عمداً إن وُجدت رحلةٌ سُعِّرت بتجربة** (المفتاحُ الأجنبيّ): نزولٌ يمحو سببَ سعرٍ دُفع أسوأُ
من نزولٍ يقف.

Revision ID: 0155
Revises: 0154
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0155"
down_revision = "0154"
branch_labels = None
depends_on = None

_STATUSES = "'draft', 'running', 'stopped', 'applied', 'cancelled'"


def upgrade() -> None:
    op.create_table(
        "price_experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("adjust_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("share_percent", sa.Integer(), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=True),
        sa.Column("center_lng", sa.Float(), nullable=True),
        sa.Column("radius_km", sa.Numeric(6, 2), nullable=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "adjust_percent <> 0 AND adjust_percent BETWEEN -50 AND 50", name=op.f("ck_price_experiments_price_experiment_percent")
        ),
        sa.CheckConstraint("share_percent BETWEEN 1 AND 100", name=op.f("ck_price_experiments_price_experiment_share")),
        sa.CheckConstraint("days BETWEEN 1 AND 60", name=op.f("ck_price_experiments_price_experiment_days")),
        sa.CheckConstraint(
            "(center_lat IS NULL AND center_lng IS NULL AND radius_km IS NULL) OR "
            "(center_lat IS NOT NULL AND center_lng IS NOT NULL AND radius_km > 0)",
            name=op.f("ck_price_experiments_price_experiment_area"),
        ),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name=op.f("ck_price_experiments_price_experiment_status")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_price_experiments_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_experiments")),
    )
    op.create_index(op.f("ix_price_experiments_country_code"), "price_experiments", ["country_code"])
    op.add_column("rides", sa.Column("price_experiment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("rides", sa.Column("price_experiment_arm", sa.String(8), nullable=True))
    op.create_foreign_key(
        op.f("fk_rides_price_experiment_id_price_experiments"), "rides", "price_experiments", ["price_experiment_id"], ["id"]
    )
    op.create_index(op.f("ix_rides_price_experiment_id"), "rides", ["price_experiment_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_rides_price_experiment_id"), table_name="rides")
    op.drop_constraint(op.f("fk_rides_price_experiment_id_price_experiments"), "rides", type_="foreignkey")
    op.drop_column("rides", "price_experiment_arm")
    op.drop_column("rides", "price_experiment_id")
    op.drop_index(op.f("ix_price_experiments_country_code"), table_name="price_experiments")
    op.drop_table("price_experiments")
