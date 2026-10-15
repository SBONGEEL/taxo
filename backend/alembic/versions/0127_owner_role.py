"""دورُ المالك (SPEC §٧٦-ك/١) — قيمةٌ رابعةٌ في `user_role`: `owner`.

**قيمةٌ في تعدادٍ لا جدولٌ ولا عمود** — والصلاحياتُ لا تُخزَّن: `permissions.DEFAULTS[OWNER] = ALL`، مشتقّةٌ من التعداد في كلِّ قراءة،
**فصلاحيةٌ تُضاف غداً تصل المالكَ بلا ترحيلة**. **ولا مالَ هنا** — فبوّابةُ المال لا تعنيها.

**و`downgrade` يقف ما دام حسابٌ يحمل الدور**، وإلا لم يفعل شيئاً: Postgres لا يحذف قيمةً من تعداد، **وقيمةٌ لا يحملها صفٌّ لا أثرَ
لها** — كما ترك `0113` قيمته (`taxo_card`) في `wallet_transaction_type`. **وإعادةُ `upgrade` بعده آمنةٌ** (`IF NOT EXISTS`).

Revision ID: 0127
Revises: 0126
"""

from __future__ import annotations

from alembic import op

revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'owner'")
    # **القيمةُ الجديدةُ لا تُستعمل في المعاملة التي أضافتها** — فتُغلق هنا كما في `0113`
    op.execute("COMMIT")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM user_roles WHERE role::text = 'owner')
               OR EXISTS (SELECT 1 FROM users WHERE role::text = 'owner') THEN
                RAISE EXCEPTION 'an owner account exists — downgrade of 0127 refuses to strip it';
            END IF;
        END
        $$
        """
    )
