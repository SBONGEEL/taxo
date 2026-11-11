"""nowpay card: «الدفع بالبطاقة المصرفية» للكبتن في الأردن (أمرُ المالك ٢٠٢٦-١١-١١)

Revision ID: 0158
Revises: 0157
Create Date: 2026-11-11

**ما تضيفه — ولا جدولَ مالٍ بينها**:
- قيمةٌ في نوع العقد (`provider_key`: `nowpay`) — **تُختم قبل أيِّ استعمال** (نمطُ `0114`).
- **صفُّ طريقةٍ واحدٌ للأردن** في `payment_providers` (جدولُ إعداد الطرق): `nowpay_card` «الدفع بالبطاقة المصرفية»، مفعَّلٌ للاشتراك
  وسداد المستحقّات، **وحدُّه الأعلى 100 دينار ابتداءً** (حارسٌ لا سعر — يُعدَّل من اللوحة).
- **مفتاحُه الرئيسيُّ للأردن مشتعلاً** في `feature_flags` (`nowpay_card_enabled`) — بأمر المالك «ON by default».

**ولا يظهر للكبتن شيءٌ قبل أن يُدخل المالكُ مفتاحَي العقد** — الطريقةُ بلا عقدٍ تسقط من القائمة كما تسقط في الدفع نفسِه. **ولا مفتاحَ
يُكتب هنا ولا عقد.** والجزائرُ وليبيا لا صفَّ لهما، ومقفلتان بالشيفرة.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقةَ والمفتاح، وقيمةُ التعداد تبقى (لا تُحذف قيمةُ تعدادٍ في PostgreSQL).
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0158"
down_revision = "0157"
branch_labels = None
depends_on = None

CODE = "nowpay_card"
FLAG = "nowpay_card_enabled"


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'nowpay'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'nowpay', true, true, true, 'taxo', 0, 100.000)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": CODE, "name": "الدفع بالبطاقة المصرفية"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
            " VALUES (:id, 'JO', :flag, true) ON CONFLICT (country_code, feature_key) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "flag": FLAG},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE code = :code"), {"code": CODE})
    bind.execute(sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key = :flag"), {"flag": FLAG})
