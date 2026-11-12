"""whop card: الدفعُ بالبطاقة عبر Whop للكبتن والراكب في الأردن — **مطفأً ومخفيّاً** (أمرُ المالك ٢٠٢٦-١١-١٣)

Revision ID: 0160
Revises: 0159
Create Date: 2026-11-13

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0158` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `whop`) — **تُختم قبل أيِّ استعمال** (نمطُ `0114`).
- **صفُّ طريقةٍ واحدٌ للأردن** في `payment_providers` (جدولُ إعداد الطرق): `whop_card` «الدفع بالبطاقة المصرفية»، للاشتراك وسداد
  المستحقّات، **وحدُّه الأعلى 100 دينار ابتداءً** كأختها (حارسٌ لا سعر — يُعدَّل من اللوحة).
- **وصفٌّ للراكب** `whop_rider_card` «شحن المحفظة بالبطاقة» للشحن وحدَه، **بلا حدٍّ أعلى مكتوبٍ هنا** (حدّاه من اللوحة) — وبه يُدفع
  أيضاً «الدفع بالبطاقة» للرحلة: شحنٌ بقيمتها ثمّ دفعُها من المحفظة (قرارُ المالك ٢٠٢٦-١١-١٣).
- **ثلاثةُ مفاتيحَ للأردن مطفأةً** في `feature_flags`: `whop_card_enabled` (الكباتن) · `whop_rider_topup_enabled` · `whop_rider_trip_enabled`.

**فلا يظهر للكبتن شيءٌ** حتى يؤكّد Whop حسابَ المالك، ويُدخل المالكُ مفاتيحَه الثلاثة في «العقود»، **ويشعل المفتاح**. ولا مفتاحَ يُكتب هنا.
والجزائرُ وليبيا لا صفَّ لهما، ومقفلتان بالشيفرة.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقةَ والمفتاح، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0160"
down_revision = "0159"
branch_labels = None
depends_on = None

CODE = "whop_card"
RIDER_CODE = "whop_rider_card"
FLAGS = ("whop_card_enabled", "whop_rider_topup_enabled", "whop_rider_trip_enabled")


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'whop'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'whop', true, true, true, 'taxo', 1, 100.000)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": CODE, "name": "الدفع بالبطاقة المصرفية"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'whop', true, true, false, 'taxo', 2)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": RIDER_CODE, "name": "شحن المحفظة بالبطاقة"},
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
    for code in (CODE, RIDER_CODE):
        bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE code = :code"), {"code": code})
    for flag in FLAGS:
        bind.execute(sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key = :flag"), {"flag": flag})
