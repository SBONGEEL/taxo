"""عميلُ الدافع عند الوسيط (SPEC §٧٦-ع/٢، أمرُ المالك ٢٠٢٦-١٠-١٧).

جدولٌ جديدٌ وحدَه — `gateway_customers`: معرّفُ مستخدم TAXO عميلاً عند Chargily، لكلِّ وضعٍ (تجربة/حيّ) واحد. **ولا مالَ هنا ولا
تعديلَ لجدولٍ قائم**؛ و`downgrade` يحذف الجدولَ ومعه المعرّفاتُ وحدَها (العملاءُ عند Chargily يبقون، ويُنشأ غيرُهم عند الحاجة).

Revision ID: 0130
Revises: 0129
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gateway_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration", sa.String(32), nullable=False),
        sa.Column("livemode", sa.Boolean(), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "integration", "livemode", name="uq_gateway_customers_user_integration_mode"),
    )
    op.create_index("ix_gateway_customers_user_id", "gateway_customers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_gateway_customers_user_id", table_name="gateway_customers")
    op.drop_table("gateway_customers")
