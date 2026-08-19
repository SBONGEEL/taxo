"""طلبُ الدفع يحمل التطبيقَ الذي فتحه — والعودةُ تتبعه لا الدور.

**والملءُ بأثر رجعيٍّ صحيحٌ هنا**: كلُّ حسابٍ يملك دوراً واحداً عند هذه الترحيلة
(`0046` نقلت حرفياً)، فتطبيقُ كلِّ طلبٍ قديمٍ معلومٌ يقيناً لا استنتاجاً.

Revision ID: 0049
Revises: 0048
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_orders", sa.Column("opened_from_app", sa.String(16), nullable=True)
    )
    op.execute(
        """
        UPDATE provider_orders o
        SET opened_from_app = u.role::text
        FROM users u
        WHERE u.id = o.user_id AND u.role IN ('rider', 'driver')
        """
    )


def downgrade() -> None:
    op.drop_column("provider_orders", "opened_from_app")
