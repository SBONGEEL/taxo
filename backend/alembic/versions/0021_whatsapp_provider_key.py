"""whatsapp provider key

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-12 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # مزودٌ ثامن في صفحة العقود: واتساب مُحقِّقاً للرقم عبر WhatsApp Cloud API
    # (المرحلة 12-هـ). قيمةٌ على نوعٍ قائم لا نوعٌ جديد، و`IF NOT EXISTS` يجعلها
    # قابلة للإعادة بعد downgrade جزئي — والنوع لا يُسقط هنا لأن
    # `provider_credentials` ما زال يستعمله (درسُ `0009` و`0010` و`0011`).
    #
    # **ولا مفتاحَ ميزةٍ في هذه الترحيلة**: `feature_flags.feature_key` عمودُ
    # `String(64)` عمداً (القسم 4)، فمفتاحُ `whatsapp_otp_enabled` كودٌ لا
    # ترحيلة. و`scripts.seed` هو من يكتب صفَّه **مطفأً بصراحة**.
    #
    # ولا صفَّ عقدٍ يُكتب: يُدخل من صفحة العقود، ولا يُفتح مُحقِّقٌ بترحيلةٍ
    # تمر في صمت.
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'whatsapp'")


def downgrade() -> None:
    # قيمةٌ أُضيفت إلى ENUM لا تُحذف منه في postgres، والنوعُ نفسه يُسقطه من
    # أنشأه. وأثرُ هذه الترحيلة صفوفُ عقدٍ ومفتاحٌ قد يكونان كُتبا بها —
    # يُحذفان قبل النزول كي لا يبقى صفٌّ بقيمةٍ لا يعرفها الكود الأقدم.
    op.execute("DELETE FROM provider_credentials WHERE provider_key = 'whatsapp'")
    op.execute("DELETE FROM feature_flags WHERE feature_key = 'whatsapp_otp_enabled'")
