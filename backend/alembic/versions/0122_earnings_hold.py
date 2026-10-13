"""مدّةُ «قيد التحويل» وخياراتُ الشحن الثابتة لكلِّ سوق (SPEC §٧٤-ي) — **عمودان على `wallet_settings`، ولا جدولَ مالٍ يُمسّ**.

- `earnings_hold_days`: أجرةُ رحلةٍ دُفعت عبر المنصّة تدخل محفظةَ الكبتن فوراً **وتُسحب بعد هذا العدد من الأيّام** — **وصفرٌ «فوري»**.
  **الجزائرُ ثلاثةٌ بأمر المالك** (§٧٤-ط/٦)، **والأردنُ وليبيا صفرٌ** — ما كانا عليه حرفاً.
- `topup_choices`: مبالغُ الشحن عند الوسيط **خياراتٌ ثابتة** — وفارغةٌ «لا خيارات» (السوقُ كما كان). الجزائر: 500 · 1,000 · 2,000 · 5,000.

**شرطٌ على السحب يُحسب لا حركةٌ تُكتب** — فلا قيدَ يُكتب ولا يُمسّ، **والنزولُ يُسقط العمودين** فيعود السحبُ فوريّاً كما كان.

Revision ID: 0122
Revises: 0121
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wallet_settings",
        sa.Column("earnings_hold_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint(
        "wallet_earnings_hold_days_range", "wallet_settings", "earnings_hold_days BETWEEN 0 AND 30"
    )
    op.add_column(
        "wallet_settings",
        sa.Column(
            "topup_choices",
            postgresql.ARRAY(sa.Numeric(12, 3)),
            nullable=False,
            server_default=sa.text("'{}'::numeric(12,3)[]"),
        ),
    )
    # **افتراضُ الجزائر بأمر المالك** — والصفُّ إن لم يوجد بعدُ يُنشأ بهما (`settings_service.MARKET_WALLET_DEFAULTS`)
    op.execute(
        "UPDATE wallet_settings SET earnings_hold_days = 3, topup_choices = '{500,1000,2000,5000}' "
        "WHERE country_code::text = 'DZ'"
    )


def downgrade() -> None:
    op.drop_column("wallet_settings", "topup_choices")
    op.drop_constraint(op.f("ck_wallet_settings_wallet_earnings_hold_days_range"), "wallet_settings", type_="check")
    op.drop_column("wallet_settings", "earnings_hold_days")
