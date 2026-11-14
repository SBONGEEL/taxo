"""polar card: اشتراكُ الكبتن الشهريُّ بالبطاقة عبر Polar في الأردن — **مطفأً ومخفيّاً** (أمرُ المالك ٢٠٢٦-١١-١٤: «ship it OFF»)

Revision ID: 0166
Revises: 0165
Create Date: 2026-11-15

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0160` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `polar`) — **تُختم قبل أيِّ استعمال**.
- **صفُّ طريقةٍ واحدٌ للأردن** في `payment_providers` (جدولُ إعداد الطرق، لا رصيدَ فيه ولا قيد): `polar_card` «الدفع بالبطاقة المصرفية»،
  **للاشتراك وحدَه** (`for_topup = false`: لا مستحقّاتٍ ولا شحن — أمرُ المالك: «No other products … until Polar approves us»)،
  **وحدُّه الأعلى 100 دينار** كأخواته (حارسٌ لا سعر، يُعدَّل من اللوحة).
- **مفتاحٌ للأردن مطفأ** في `feature_flags`: `polar_card_enabled` — **يُشعله المالكُ وحدَه** بعد أن يقبل Polar الحسابَ ويدفع دفعتَه التجريبيّة.

**فلا يظهر للكبتن شيء** حتى يُدخل المالكُ العقدَ في «العقود» ويشعل المفتاح. ولا مفتاحَ ولا سرَّ يُكتب هنا. والجزائرُ وليبيا لا صفَّ لهما،
ومقفلتان بالشيفرة (`payment_gateways.SWITCH_COUNTRIES`).

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقةَ والمفتاح، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0166"
down_revision = "0165"
branch_labels = None
depends_on = None

CODE = "polar_card"
FLAG = "polar_card_enabled"


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'polar'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'polar', true, false, true, 'taxo', 1, 100.000)"
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
