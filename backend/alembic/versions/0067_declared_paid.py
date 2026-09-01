"""«حوّلتُ» فعلٌ يُختم — لا يُشتقّ من فتح الشاشة (قرارُ المالك 2026-09-01).

**`status = created` تعني «فُتحت الشاشة»، لا «حوّلتُ»** — فقائمةُ المشرف كانت
تخلط **من فتح ونسي** بـ**من دفع فعلاً وينتظر تأكيداً لمالٍ خرج من حسابه**.
والأولُ لا ينتظر شيئاً.

**وعمودُ لحظةٍ لا رايةٌ ثنائية**: صفحةُ المدفوعات ترتّب بـ«وقت الضغط»،
**ورايةٌ لا تقول متى**. وهو ما يجعل الضغطةَ الثانيةَ لا تُنشئ شيئاً أيضاً:
الحقلُ مختومٌ فيُعاد الصفُّ نفسُه بلا صياح.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_orders",
        sa.Column("declared_paid_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_orders", "declared_paid_at")
