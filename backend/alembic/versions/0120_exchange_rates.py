"""أسعارُ الصرف للمجموع التقريبيّ في «المالية العامة» (SPEC §٧٤-أ/٩) — جدولٌ واحد، **ولا جدولَ مالٍ يُمسّ**.

**والتاريخُ يُحفظ**: كلُّ ضبطٍ صفٌّ جديد. **و`downgrade` يقف إن ضُبط سعر** — سعرٌ قرأ به المالكُ رقماً لا يُمحى بنزول.

Revision ID: 0120
Revises: 0119
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None

CURRENCY = postgresql.ENUM(name="currency", create_type=False)


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(3), nullable=False),
        sa.Column("currency", CURRENCY, nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("set_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rate > 0", name="exchange_rate_positive"),
        sa.CheckConstraint("reference ~ '^[A-Z]{3}$'", name="exchange_rate_reference_code"),
    )
    op.create_index("ix_exchange_rates_current", "exchange_rates", ["reference", "currency", "created_at"])


def downgrade() -> None:
    written = op.get_bind().execute(sa.text("SELECT count(*) FROM exchange_rates")).scalar_one()
    if written:
        raise RuntimeError(
            f"في أسعار الصرف {written} صفّاً ضبطها المالك — والنزولُ يمحوها. لا يُمحى ما قُرئ به رقمٌ بنزول."
        )
    op.drop_index("ix_exchange_rates_current", table_name="exchange_rates")
    op.drop_table("exchange_rates")
