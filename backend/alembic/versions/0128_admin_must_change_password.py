"""تغييرُ كلمة المشرف إلزاميٌّ عند أوّل دخول (SPEC §٧٦-م/٢، قرارُ المالك ٢٠٢٦-١٠-١٥).

عمودٌ على `admin_credentials` — **وافتراضُه في القاعدة `false`**: الحسابان القائمان **يبقيان كما هما** (أمرُ المالك في §٧٦-ك)، والقيمةُ
`true` لكلِّ حسابٍ يُنشأ بعد اليوم **تكتبها الشيفرةُ** (`admin_credentials.create`) — كما يُدخَل صفٌّ من `psql` آمناً لا مُلزِماً.
**وحسابُ المالك وحدَه يُعلَّم هنا** (من يحمل الدورَ `owner`): كلمتُه وضعها سكربتُ الإنشاء لا هو. **ولا مالَ هنا.**

Revision ID: 0128
Revises: 0127
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_credentials",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE admin_credentials SET must_change_password = true "
        "WHERE user_id IN (SELECT user_id FROM user_roles WHERE role::text = 'owner')"
    )


def downgrade() -> None:
    op.drop_column("admin_credentials", "must_change_password")
