"""profile photo document type

الصورةُ الشخصية للسائق (البند ٥٢، SPEC تحت `driver_documents`) — **قيمةٌ في
تعدادٍ قائم لا جدولٌ جديد**: هي مستندٌ يُراجَع كبقية المستندات، وما يميّزها أنها
**تُنشر أيضاً** — وذلك مسارُ قراءةٍ في الكود لا عمودٌ في القاعدة.

**ولا شيءَ يُشترط بأثرٍ رجعيّ** (قرارُ المالك 2026-08-16): الترحيلةُ تضيف قيمةً
ولا تمسّ صفّاً. والشرطُ يسري على من يُعتمد بعده لأن `drivers.approve` لا تُنادى
إلا عند اعتمادٍ جديد، ومن اعتُمد قبله يظهر في شاشة السائقين متراكماً يُلاحَق.

**والمطبُّ المعروف**: `ALTER TYPE … ADD VALUE` لا يجوز في المعاملة التي
**تستعمل** القيمة، و`env.py` يلفّ السلسلةَ كلَّها في معاملة — فـ`COMMIT` صريحٌ
بعدها. ولا يحتاج ما بعده `IF NOT EXISTS` هنا لأن لا شيءَ بعده.

**ولا تُحذف القيمةُ في التراجع**: Postgres لا يحذف قيمةً من تعداد، والنوعُ
نفسُه تُسقطه الترحيلةُ التي أنشأته. و`IF NOT EXISTS` هو ما يجعل ترقيةً بعد
تراجعٍ جزئيٍّ تمرّ.

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-16 16:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'profile_photo'"
    )
    op.execute("COMMIT")


def downgrade() -> None:
    # قيمةُ تعدادٍ لا تُحذف في Postgres — والتراجعُ هنا لا شيء، لا إغفالاً بل
    # لأن البديلَ إعادةُ بناء النوع كلِّه بجداوله وهو أثقلُ من أن يُبرَّر
    pass
