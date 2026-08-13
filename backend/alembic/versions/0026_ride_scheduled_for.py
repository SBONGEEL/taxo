"""موعدُ الرحلة المحجوزة مجمَّداً عليها (SPEC القسم 5.11، المرحلة 12-ط)

عمودٌ واحدٌ nullable — والرحلاتُ القائمةُ تبقى `NULL`، وهو معناها الصحيح: لم
تُحجز. فلا تحويلَ بيانات ولا افتراضَ سخيّ.

**ولماذا عمودٌ ولا يُقرأ من جدول الحجز؟** إطارُ العرض الذي يقرؤه الكبتن تسلسلٌ
خالصٌ من صفِّ الرحلة (`RideOut.from_ride`) بلا استعلامات، وبثُّه يقع في مسارٍ
ساخن — فاستعلامٌ عكسيٌّ لكل عرضٍ ثمنٌ يُدفع على طريقٍ لا يحتمله. **وليس بيتاً
ثانياً بل تجميداً** (قرارُ المالك 2026-08-13): الرحلةُ تحمل **ما عُرض على الكبتن**
كما تحمل `commission_percent_at_ride`، فيبقى صحيحاً وإن تغيّر أصلُه بعده.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("rides", "scheduled_for", if_exists=True)
