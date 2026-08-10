"""phone verified at

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10 10:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # لحظةُ إثبات ملكية الرقم (المرحلة 8-ب). **nullable بلا قيمة افتراضية**:
    # الحسابات القائمة قبل هذه الترحيلة لم يُثبَت أيٌّ منها بهذا المعنى، وختمُها
    # محققةً بأثرٍ رجعي كذبٌ في عمودٍ يُبنى عليه اعتمادُ الكباتن. تُعلَّم في
    # اللوحة غير محققة ويُطلب منها التحقق — وهو نفس مسار من أُنشئ حسابه
    # والمفتاح مطفأ.
    op.add_column(
        'users', sa.Column('phone_verified_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'phone_verified_at')
