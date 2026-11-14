"""moonpay commerce: الدفعُ بالعملات الرقميّة عبر MoonPay Commerce للكبتن والراكب في الأردن (أمرُ المالك ٢٠٢٦-١١-١٤)

Revision ID: 0165
Revises: 0164
Create Date: 2026-11-14

**ما تضيفه — ولا جدولَ مالٍ بينها** (نمطُ `0160` حرفاً):
- قيمةٌ في نوع العقد (`provider_key`: `moonpay`) — **تُختم قبل أيِّ استعمال**.
- **صفّا طريقةٍ للأردن** في `payment_providers` (جدولُ إعداد الطرق، لا رصيدَ فيه ولا قيد): `moonpay_driver` «الدفع بالعملات الرقمية»
  للاشتراك والمستحقّات **وحدُّه الأعلى 100 دينار** كأخواته (حارسٌ لا سعر، يُعدَّل من اللوحة)، و`moonpay_rider` «شحن المحفظة بالعملات
  الرقمية» للشحن وحدَه بباقاتٍ ثابتةٍ من العقد. **وترتيبُهما `0`** فيُعرضان أوّلاً.
- **مفتاحان للأردن مطفآن** في `feature_flags`: `moonpay_driver_enabled` · `moonpay_rider_enabled` — **يُشعلان بعد التحقّق على الإنتاج**
  (أمرُ المالك: «as soon as it's live»)، لا بالترحيلة.
- **ترتيبُ طرق الدفع في الأردن يبدأ بـ`crypto`** (`payment_settings.payment_method_order`، جدولُ سياساتٍ لا مال) — «first payment option in
  Jordan, above CliQ»؛ والبطاقةُ والمحفظةُ وكليكُ والنقدُ تحته كما هي. والجزائرُ وليبيا لا يمسّهما حرف.

**والنزولُ لا يحذف صفّاً** (لا حذفَ على الإنتاج): يُطفئ الطريقتين والمفتاحين، ويُخرج `crypto` من الترتيب، وقيمةُ التعداد تبقى.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0165"
down_revision = "0164"
branch_labels = None
depends_on = None

DRIVER_CODE = "moonpay_driver"
RIDER_CODE = "moonpay_rider"
FLAGS = ("moonpay_driver_enabled", "moonpay_rider_enabled")


def upgrade() -> None:
    op.execute("ALTER TYPE provider_key ADD VALUE IF NOT EXISTS 'moonpay'")
    op.execute("COMMIT")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order, max_amount)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'moonpay', true, true, true, 'taxo', 0, 100.000)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": DRIVER_CODE, "name": "الدفع بالعملات الرقمية"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO payment_providers (id, country_code, kind, code, name, integration, enabled, for_topup,"
            " for_subscription, fee_bearer, sort_order)"
            " VALUES (:id, 'JO', 'bank_transfer', :code, :name, 'moonpay', true, true, false, 'taxo', 0)"
            " ON CONFLICT (country_code, code) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "code": RIDER_CODE, "name": "شحن المحفظة بالعملات الرقمية"},
    )
    for flag in FLAGS:
        bind.execute(
            sa.text(
                "INSERT INTO feature_flags (id, country_code, feature_key, enabled)"
                " VALUES (:id, 'JO', :flag, false) ON CONFLICT (country_code, feature_key) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "flag": flag},
        )
    bind.execute(
        sa.text(
            "UPDATE payment_settings SET payment_method_order = '[\"crypto\"]'::jsonb || payment_method_order"
            " WHERE country_code = 'JO' AND NOT (payment_method_order ? 'crypto')"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for code in (DRIVER_CODE, RIDER_CODE):
        bind.execute(sa.text("UPDATE payment_providers SET enabled = false WHERE code = :code"), {"code": code})
    for flag in FLAGS:
        bind.execute(sa.text("UPDATE feature_flags SET enabled = false WHERE feature_key = :flag"), {"flag": flag})
    bind.execute(sa.text("UPDATE payment_settings SET payment_method_order = payment_method_order - 'crypto'"))
