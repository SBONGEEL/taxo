"""enable postgis and pgcrypto extensions

Revision ID: 0001
Revises:
Create Date: 2026-08-09
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # postgis: أعمدة geography للرحلات (المرحلة 3)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    # pgcrypto: gen_random_uuid وتوابع تشفير مساعدة
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # لا نُسقط الامتدادات: قد تعتمد عليها كائنات أخرى في نفس قاعدة البيانات
    pass
