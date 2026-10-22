"""دفعُ الجزائر (SPEC §٨٢، أمرُ المالك ٢٠٢٦-١٠-٢٢) — انقطاعُ Chargily بأمان، وطريقةُ BaridiMob/CCP بمراجعةٍ يدويّة.

**أعمدةٌ تُضاف ولا يُمسّ قائم** — كلُّها تقبل الفراغ، فصفوفُ اليوم تبقى كما هي حرفاً:

- `payment_providers.account_holder_latin` — اسمُ صاحب الحساب بالحروف اللاتينيّة كما تعرضه بريدُ الجزائر وBaridiMob.
- `payment_providers.min_amount` / `max_amount` — حدّا المبلغ لطريقةٍ بعينها (فارغان = بلا حدّ، كما كانت كلُّ طريقة).
- `payment_requests.gateway_paid_at` — **لحظةَ قال الوسيطُ «دُفع» ولم يُقيَّد بعد** («قيد المعالجة»)؛ فارغٌ في كلِّ ما سواه.
- `payment_requests.transfer_date` — تاريخُ التحويل كما يكتبه صاحبُه مع رقمه وإيصاله.
- `user_role` ← `payment_reviewer` — **مراجعُ تحويلات BaridiMob في الجزائر**: صفحةٌ واحدة، والعاملُ الثاني إلزاميّ.

**ولا قيدَ في الدفتر ولا حذفَ ولا تحويلَ لقيمة** — فلا يتغيّر رصيدٌ ولا حالُ دفعة. و`downgrade` يحذف الأعمدةَ الخمسة، **ويقف ما دام
حسابٌ يحمل الدورَ الجديد** (Postgres لا يحذف قيمةً من تعداد — كـ`0127`).

Revision ID: 0132
Revises: 0131
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0132"
down_revision = "0131"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_providers", sa.Column("account_holder_latin", sa.String(120), nullable=True))
    op.add_column("payment_providers", sa.Column("min_amount", sa.Numeric(12, 3), nullable=True))
    op.add_column("payment_providers", sa.Column("max_amount", sa.Numeric(12, 3), nullable=True))
    op.create_check_constraint(
        "payment_provider_amount_bounds_valid",
        "payment_providers",
        "(min_amount IS NULL OR min_amount > 0) AND (max_amount IS NULL OR max_amount > 0) "
        "AND (min_amount IS NULL OR max_amount IS NULL OR min_amount <= max_amount)",
    )
    op.add_column("payment_requests", sa.Column("gateway_paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payment_requests", sa.Column("transfer_date", sa.Date(), nullable=True))
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'payment_reviewer'")
    # **القيمةُ الجديدةُ لا تُستعمل في المعاملة التي أضافتها** — كـ`0127`
    op.execute("COMMIT")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM user_roles WHERE role::text = 'payment_reviewer')
               OR EXISTS (SELECT 1 FROM users WHERE role::text = 'payment_reviewer') THEN
                RAISE EXCEPTION 'a payment reviewer account exists — downgrade of 0132 refuses to strip it';
            END IF;
        END
        $$
        """
    )
    op.drop_column("payment_requests", "transfer_date")
    op.drop_column("payment_requests", "gateway_paid_at")
    op.drop_constraint("payment_provider_amount_bounds_valid", "payment_providers", type_="check")
    op.drop_column("payment_providers", "max_amount")
    op.drop_column("payment_providers", "min_amount")
    op.drop_column("payment_providers", "account_holder_latin")
