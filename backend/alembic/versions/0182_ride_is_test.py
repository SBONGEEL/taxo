"""**رحلةُ تجربة** (قرارُ المالك ٢٠٢٦-١١-٢٠ الخامس، SPEC §٦٥-ج/٧): `rides.is_test`.

* عمودٌ منطقيٌّ **مطفأٌ للجميع** بعد الترحيلة — فلا يتغيّر عدٌّ ولا تقريرٌ حتى يُكتب.
* `test_accounts.real_ride()` يستثنيه، فيخرج من الإحصاءات والتقارير كما تخرج رحلاتُ حسابات التجربة.

**لا يمسّ مبلغاً ولا جدولَ دفتر**. **والرجوعُ** يحذف العمود: الرحلاتُ المعلَّمةُ يدويّاً تعود إلى العدّ — سلوكُ ما قبل الترحيلة حرفاً.

Revision ID: 0182
Revises: 0181
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0182"
down_revision = "0181"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("is_test", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("rides", "is_test")
