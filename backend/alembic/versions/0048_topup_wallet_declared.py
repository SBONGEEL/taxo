"""طلبُ الشحن يحمل محفظتَه — العمليةُ تعلن، ولا تُشتقّ عند التأكيد.

**والملءُ بأثر رجعيٍّ صحيحٌ هنا** بخلاف نوع الإحالة: عند هذه الترحيلة يملك كلُّ
حسابٍ دوراً واحداً (`0046` نقلت حرفياً)، فمحفظةُ كلِّ طلبٍ قديمٍ معلومةٌ يقيناً
لا استنتاجاً. وتركُها فارغةً كان سيجعل تأكيدَ طلبٍ قديمٍ يشتقّ من الدور — أي
يرتدّ بالخطأ المسمّى يومَ يحمل صاحبُه دورين.

Revision ID: 0048
Revises: 0047
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wallet_topup_requests",
        sa.Column(
            "owner_type",
            postgresql.ENUM(
                "rider", "driver", name="wallet_owner_type", create_type=False
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE wallet_topup_requests r
        SET owner_type = u.role::text::wallet_owner_type
        FROM users u
        WHERE u.id = r.owner_id AND u.role IN ('rider', 'driver')
        """
    )


def downgrade() -> None:
    op.drop_column("wallet_topup_requests", "owner_type")
