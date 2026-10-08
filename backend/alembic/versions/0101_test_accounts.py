"""حسابا التجربة على الإنتاج (SPEC §٦٥-ج) — **عمودٌ واحدٌ يسمّيهما، وفهرسٌ جزئيٌّ لا يحمل غيرَهما**.

**ما تضيفه**: `users.is_test BOOLEAN NOT NULL DEFAULT false`، وفهرسٌ جزئيٌّ `ix_users_is_test` على الصفوف الموسومة وحدَها.

**ولمَ فهرسٌ جزئيّ**: السؤالُ الوحيدُ الذي يُطرح عليه «مَن الموسوم؟» — والجوابُ صفّان في جدولٍ بالآلاف. فهرسٌ على العمود كلِّه
يحمل آلافَ `false` لا يُسأل عنها أحد، **والجزئيُّ يحمل الصفَّين وحدَهما** فيجيب الاستثناءَ في كلِّ عدٍّ بلا كلفة.

**لا تمسّ جدولَ مال** (`users` ليس دفتراً)، **ولا تكتب صفّاً قائماً**: الافتراضُ في القاعدة يجعل كلَّ حسابٍ قائمٍ «حقيقيّاً» كما
كان — **ولا حسابَ تجربةٍ يوجد قبل أن يكتبه سكربتُ الإنشاء** (`scripts/provision_test_accounts.py`).

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): يحذف الفهرسَ ثمّ العمود. **وما يضيع بالتراجع هو الوسمُ وحدَه** —
فيعود حسابا التجربة حسابين عاديّين يدخلان التوزيعَ والإحصاءات. **فلا يُتراجع عنها والحسابان قائمان على الإنتاج** إلا بعد
تعليقهما (`is_blocked`) — والتعليقُ لا الحذفُ كما هو مبنيّ.

Revision ID: 0101
Revises: 0100
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_test", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "ix_users_is_test",
        "users",
        ["is_test"],
        postgresql_where=sa.text("is_test"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_is_test", table_name="users")
    op.drop_column("users", "is_test")
