"""freemius card: بوّابةُ بطاقةٍ احتياطيّةٌ لاشتراك الكبتن عبر Freemius في الأردن — **مطفأةً بمفتاحها** (أمرُ المالك ٢٠٢٦-١١-٢٦)

Revision ID: 0194
Revises: 0193
Create Date: 2026-11-27

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0188` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `freemius`) — **تُختم قبل أيِّ استعمال**.
- **صفُّ طريقةٍ واحدٌ للأردن** في `payment_providers` (جدولُ إعداد الطرق، لا رصيدَ فيه ولا قيد): `freemius_card` «الدفع بالبطاقة المصرفية»،
  **للاشتراك وحدَه**، وحدُّه الأعلى 100 دينار (حارسٌ لا سعر). **والمبالغُ المسموحةُ في الشيفرة** (3 · 17 · 45 · 60 — حارسُ السعر نفسُه).
- **مفتاحٌ للأردن مطفأ** في `feature_flags`: `freemius_card_enabled` — **نسخةُ الموقع وحدَها**، ولا مفتاحَ لنسخة Play بقرار.

**فلا يظهر للكبتن شيء** حتى يُدخَل العقدُ ويُختار Freemius في «بوابة الدفع بالبطاقة». ولا مفتاحَ ولا سرَّ يُكتب هنا. وليبيا والجزائرُ لا صفَّ
لهما ومقفلتان بالشيفرة.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقةَ والمفتاح، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0194"
down_revision = "0193"
branch_labels = None
depends_on = None

CODE = "freemius_card"
FLAG = "freemius_card_enabled"


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'freemius'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'freemius', true, false, true, 'taxo', 1, 100.000)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": CODE, "name": "الدفع بالبطاقة المصرفية"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
            " VALUES (:id, 'JO', :flag, false) ON CONFLICT (country_code, feature_key) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "flag": FLAG},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE code = :code"), {"code": CODE})
    bind.execute(sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key = :flag"), {"flag": FLAG})
