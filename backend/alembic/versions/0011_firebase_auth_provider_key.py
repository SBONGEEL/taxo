"""firebase auth provider key

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10 09:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # مزودٌ سابع في صفحة العقود: التحقق من الهاتف لدى Firebase (المرحلة 8-ب).
    # قيمةٌ على نوعٍ قائم لا نوعٌ جديد، و`IF NOT EXISTS` يجعلها قابلة للإعادة
    # بعد downgrade جزئي — والنوع لا يُسقط هنا لأن `provider_credentials`
    # ما زال يستعمله (نفس درس `0009` و`0010`).
    #
    # ولا صفَّ يُكتب: العقد يُدخل من صفحة العقود أو من `scripts.seed`، ولا
    # يُفعَّل مزودُ دخولٍ بترحيلةٍ تمر في صمت.
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'firebase_auth'")


def downgrade() -> None:
    # قيمةٌ أُضيفت إلى ENUM لا تُحذف منه في postgres، والنوعُ نفسه يُسقطه من
    # أنشأه. وأثرُ هذه الترحيلة الوحيد صفوفُ عقدٍ قد تكون كُتبت بها — تُحذف
    # قبل النزول كي لا يبقى صفٌّ بقيمةٍ لا يعرفها الكود الأقدم.
    op.execute("DELETE FROM provider_credentials WHERE provider_key = 'firebase_auth'")
