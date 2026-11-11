"""nowpay card: أقلُّ دفعةٍ بالبطاقة المصرفية ١٠ دنانير (قرارُ المالك ٢٠٢٦-١١-١١)

Revision ID: 0159
Revises: 0158
Create Date: 2026-11-11

**ما تفعله**: تكتب حدَّ الطريقة الأدنى `min_amount = 10.000` على صفِّ «الدفع بالبطاقة المصرفية» في الأردن (`payment_providers` — جدولُ
إعداد الطرق لا جدولُ مال) **إن كان فارغاً**؛ فقيمةٌ ضبطها المالكُ من اللوحة قبلها لا تُمسّ. **والحدُّ يُعدَّل من اللوحة** («الحدود» في
صفحة الدفع بالبطاقة) — ليس ثابتاً في الشيفرة.

**ولمَ ١٠**: رسمُ الشريك الثابت (٢ دولار) تتحمّله TAXO منذ القرار نفسِه، فالدفعةُ الصغيرةُ تكلّف أكثرَ ممّا تجلب.

**والنزولُ يعيده فارغاً** ما دام ١٠ كما كتبته هذه الترحيلة.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0159"
down_revision = "0158"
branch_labels = None
depends_on = None

CODE = "nowpay_card"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE payment_providers SET min_amount = 10.000"
            " WHERE country_code = 'JO' AND code = :code AND min_amount IS NULL"
        ),
        {"code": CODE},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE payment_providers SET min_amount = NULL"
            " WHERE country_code = 'JO' AND code = :code AND min_amount = 10.000"
        ),
        {"code": CODE},
    )
