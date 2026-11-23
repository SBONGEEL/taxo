"""digistore24 card: اشتراكُ الكبتن بالبطاقة عبر Digistore24 في الأردن — **مطفأً بمفتاحين** (أمرا المالك ٢٠٢٦-١١-٢٣)

Revision ID: 0188
Revises: 0187
Create Date: 2026-11-23

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0166` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `digistore24`) — **تُختم قبل أيِّ استعمال**.
- **صفُّ طريقةٍ واحدٌ للأردن** في `payment_providers` (جدولُ إعداد الطرق، لا رصيدَ فيه ولا قيد): `digistore24_card` «الدفع بالبطاقة المصرفية»،
  **للاشتراك وحدَه**، وحدُّه الأعلى 100 دينار (حارسٌ لا سعر). **والمبالغُ المسموحةُ في الشيفرة** (3 · 17 · 45 — حارسُ السعر).
- **مفتاحان للأردن مطفآن** في `feature_flags`: `digistore24_card_enabled` (نسخةُ الموقع) و`digistore24_card_play_enabled` (نسخةُ Play).

**فلا يظهر للكبتن شيء** حتى يُدخَل العقدُ ويُشعَل المفتاح. ولا مفتاحَ ولا سرَّ يُكتب هنا. وليبيا والجزائرُ لا صفَّ لهما ومقفلتان بالشيفرة.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقةَ والمفتاحين، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0188"
down_revision = "0187"
branch_labels = None
depends_on = None

CODE = "digistore24_card"
FLAGS = ("digistore24_card_enabled", "digistore24_card_play_enabled")


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'digistore24'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'digistore24', true, false, true, 'taxo', 1, 100.000)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": CODE, "name": "الدفع بالبطاقة المصرفية"},
    )
    for flag in FLAGS:
        bind.execute(
            sa.text(
                "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
                " VALUES (:id, 'JO', :flag, false) ON CONFLICT (country_code, feature_key) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "flag": flag},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE code = :code"), {"code": CODE})
    for flag in FLAGS:
        bind.execute(sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key = :flag"), {"flag": flag})
