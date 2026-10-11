"""user language: لغةُ الحساب — العربيّةُ والفرنسيّة

Revision ID: 0116
Revises: 0115
Create Date: 2026-10-11

**ما تضيفه** (SPEC §٧٣-هـ المرحلة ٥): `users.language` (`ar` · `fr`) **افتراضُه `ar`** — فكلُّ حسابٍ قائمٍ عربيٌّ كما كان، ولا صفَّ يُكتب
بيد. وقيدٌ يمنع غيرَ اللغتين. **ولا يمسّ جدولَ مال.** والنزولُ يحذف القيدَ والعمود.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(length=2), server_default=sa.text("'ar'"), nullable=False))
    op.create_check_constraint("user_language_valid", "users", "language IN ('ar', 'fr')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_user_language_valid"), "users", type_="check")
    op.drop_column("users", "language")
