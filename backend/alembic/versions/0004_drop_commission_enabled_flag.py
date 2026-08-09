"""drop commission_enabled feature flag rows

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-10 00:00:00.000000

ترحيلة بيانات فقط: `commission_enabled` كان مكرراً بين `feature_flags` و
`commission_settings`، وأُبقي في الثاني وحده (نسبته ونطاقه يسكنان هناك أصلاً).
الصفوف المبذورة سابقاً تُحذف هنا وإلا لظهر المفتاح في `GET /config` رغم أن
التطبيق لم يعد يعرفه.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE feature_key = 'commission_enabled'")


def downgrade() -> None:
    # لا استرجاع: مصدر الحقيقة هو commission_settings، وإعادة إنشاء صفوف
    # بمفتاح لا يعترف به التطبيق تُعيد الازدواجية التي أُزيلت.
    pass
