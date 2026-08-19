"""نوعُ برنامج الإحالة يُختم عند الإحالة — واقعةٌ تاريخية لا اشتقاق.

**ولا ملءَ بأثر رجعي** (شرطُ المالك 2026-08-19): الصفوفُ القائمةُ تبقى فارغةً
ويُشتقّ نوعُها من الدور كما كان — وهو صحيحٌ لها بالضبط، لأنها كُتبت يوم كان
`users.role` ثابتاً مدى العمر. وملؤها اليوم يكتب **استنتاجاً** في عمودِ وقائع.

Revision ID: 0047
Revises: 0046
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `VARCHAR` لا ENUM: النوعُ قيمةُ سياسةٍ في `referral_settings`، ونوعٌ ثالثٌ
    # يوماً ما يكون شيفرةً بلا ترحيلة — استثناءُ `feature_flags.feature_key`
    op.add_column(
        "referrals", sa.Column("referral_type", sa.String(16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("referrals", "referral_type")
