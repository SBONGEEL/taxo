"""حسابُ كليك المستقبِل — عمودٌ لكلِّ سوقٍ في `payment_settings`.

**ولمَ عمودٌ في جدولٍ قائمٍ لا جدولٌ جديد**: `payment_settings` **هو بيتُ
سياسات الدفع لكلِّ دولة** منذ المرحلة السادسة (`cliq_confirmation_hours` فيه)،
وجدولٌ ثانٍ بجانبه يعني موضعين يُقرأ منهما «كيف يُدفع في هذا السوق».

**ولمَ في القاعدة لا في `.env` ولا في الشيفرة** (قرارُ المالك 2026-08-29):
**تعديلُ حسابٍ يستقبل مالَ الناس لا يكون نشراً.** ومن خبزه في حزمةٍ جعل
تصحيحَ رقمٍ خاطئٍ ينتظر بناءً ورفعاً — والمالُ في الطريق أثناء ذلك.

**و`NULL` تعني «لم يُضبط»** لا «فارغ»: السوقُ الذي لا alias له **تُخفى عنه
القناةُ كلُّها** — لا تُعرض بلا رقم. وذاك عطبٌ صريحٌ في قرار المالك: شاشةٌ
تطلب تحويلاً ولا تقول إلى أين تُنتج حوالةً ضائعة.

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_settings",
        sa.Column("cliq_alias", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_settings", "cliq_alias")
