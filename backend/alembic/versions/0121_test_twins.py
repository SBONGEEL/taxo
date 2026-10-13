"""توأمُ حساب التجربة في كلِّ سوق (SPEC §٧٤-أ/١٠) — **عمودٌ واحدٌ على `users`، ولا جدولَ مالٍ يُمسّ**.

**لمَ توأمٌ لا سوقٌ يُبدَّل على الحساب**: المحفظةُ تُقرأ بعملة سوق صاحبها (لا عمودَ عملةٍ في الدفتر) — **فحسابٌ يُنقل سوقُه يقرأ ديناراً
أردنيّاً دنانيرَ جزائريّة**. فلكلِّ سوقٍ حسابُ تجربةٍ بمحفظته وعملته واشتراكه، **و`test_twin_of` يشير إلى الحساب الأوّل** فيعرف مُختارُ السوق
إخوتَه. **ولا يكتبه بابٌ في التطبيقات ولا في اللوحة** — سكربتُ الإنشاء وحدَه، كوسم `is_test`.

**و`downgrade` يقف إن رُبط توأم** — ربطٌ يُمحى يجعل الإخوةَ حساباتٍ متفرّقةً لا يصل بينها المُختار.

Revision ID: 0121
Revises: 0120
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "test_twin_of",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_test_twin_of", "users", ["test_twin_of"])


def downgrade() -> None:
    linked = op.get_bind().execute(sa.text("SELECT count(*) FROM users WHERE test_twin_of IS NOT NULL")).scalar_one()
    if linked:
        raise RuntimeError(f"{linked} حسابَ تجربةٍ مربوطٌ بتوأمه — والنزولُ يفكّ الربط. لا يُفكّ بنزول.")
    op.drop_index("ix_users_test_twin_of", table_name="users")
    op.drop_column("users", "test_twin_of")
