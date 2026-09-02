"""إلغاءُ اشتراكٍ من اللوحة — حالٌ ثالثة، وأثرُ القرار على الصفّ (البند ٢).

**وهذا نقضٌ صريحٌ لقرارٍ مكتوب** (قرارُ المالك 2026-09-02): كان توثيقُ
`SubscriptionStatus` يقول «حالتان لا ثالثة … لا `cancelled`: اشتراكٌ مدفوعٌ
مقدماً لا يُلغى». **والقرارُ الجديد يعكسه بعلّته**: «ألغيتُه» يجب أن تعني
«أوقفتُه» وإلا كذب الزرّ، **والإلغاء بيد الإدارة لا بيد الكبتن** — فاحتجازُ
مالٍ عن مدّةٍ منعناه من استعمالها شكوى بلا جواب.

## ولمَ `cancelled` حالٌ ثالثة ولا يكفي `expired`

**لأن الفرق يُقرأ بعد شهر**: `expired` تقول «انقضى وقتُه»، و`cancelled` تقول
«أوقفناه نحن ورددنا مالَه». **ودمجُهما يمحو من دفع مقابل مدّةٍ لم يأخذها**،
ويجعل أهليةَ السلفة تقرأ إلغاءً على أنه دورةُ عملٍ اكتملت.

**والقيمةُ تُقرأ في ثلاثة مواضع بلا تعديلٍ فيها**: `coverage_condition`
و`coverage_until` يرشِّحان `status == ACTIVE` أصلاً — **فالملغى يخرج من
التوزيع لحظتَه، ولا يبدأ اشتراكُه القادمُ من نهاية الملغى**.

## والأعمدةُ الأربعة — قرارٌ يُقرأ من صفّه

- `cancelled_at` · `cancelled_by` · `cancel_reason`: **السببُ إلزاميٌّ في
  الباب**، وهو من صنف «الاستثناءُ الصريح» في قاعدة التدقيق — نصٌّ هو **محتوى
  القرار** لا قيمةٌ مخزَّنة.
- `refund_transaction_id`: **مؤشِّرٌ إلى القيد لا نسخةٌ من مبلغه** — و
  `transaction_id` فوقَه يفعل هذا للشراء منذ يومه. **ولا عمودَ `refund_amount`
  بقصد**: المبلغُ بيتُه الدفتر، **ورقمٌ ثانٍ له يفترق عنه أوّلَ تسوية**.
  و`NULL` هنا معناها **«لا قيد»** لا «لم يُردّ شيء» — وهي حالُ الشهر المجاني
  حرفاً: المدفوعُ صفرٌ فلا قيدَ يُكتب.

Revision ID: 0069
Revises: 0068
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # **`ADD VALUE` ثمّ `COMMIT` صريح** — والقاعدةُ مكتوبةٌ في `0018`: القيمةُ
    # لا تُستعمل في المعاملة التي أنشأتها، و`env.py` يلفّ السلسلةَ كلَّها في
    # معاملةٍ واحدة. **ولا شيءَ بعده يستعمل القيمة**، لكنّ الفصلَ يبقى شرطاً
    # كي لا يسقط أوّلُ مستعملٍ يُضاف بعد اليوم.
    op.execute(
        "ALTER TYPE subscription_status ADD VALUE IF NOT EXISTS 'cancelled'"
    )
    op.execute("COMMIT")

    # **وكلُّ ما بعد `COMMIT` يُعاد بلا ضرر** (`IF NOT EXISTS`): سقوطٌ في
    # السطر الأخير لا يترك ترحيلةً لا تُعاد — درسُ `0018` بحرفه.
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD COLUMN IF NOT EXISTS cancelled_by UUID"
    )
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD COLUMN IF NOT EXISTS cancel_reason VARCHAR(300)"
    )
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD COLUMN IF NOT EXISTS refund_transaction_id UUID"
    )

    # **`SET NULL` للمشرف، و`RESTRICT` للقيد**: حسابُ مشرفٍ يُحذف لا يمحو
    # القرار، **وقيدُ دفترٍ يشير إليه صفٌّ لا يُحذف أصلاً** (الدفترُ لا يُعدَّل).
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "DROP CONSTRAINT IF EXISTS fk_driver_subscriptions_cancelled_by_users"
    )
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD CONSTRAINT fk_driver_subscriptions_cancelled_by_users "
        "FOREIGN KEY (cancelled_by) REFERENCES users(id) ON DELETE SET NULL"
    )
    # **والاسمُ مصرَّحٌ لا مولَّد**: المولَّدُ ٦٥ محرفاً و`Postgres` يقصّ عند ٦٣
    op.execute(
        "ALTER TABLE driver_subscriptions DROP CONSTRAINT IF EXISTS "
        "fk_driver_subscriptions_refund_tx"
    )
    op.execute(
        "ALTER TABLE driver_subscriptions "
        "ADD CONSTRAINT fk_driver_subscriptions_refund_tx "
        "FOREIGN KEY (refund_transaction_id) REFERENCES wallet_transactions(id) "
        "ON DELETE RESTRICT"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_driver_subscriptions_refund_tx",
        "driver_subscriptions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_driver_subscriptions_cancelled_by_users",
        "driver_subscriptions",
        type_="foreignkey",
    )
    op.drop_column("driver_subscriptions", "refund_transaction_id")
    op.drop_column("driver_subscriptions", "cancel_reason")
    op.drop_column("driver_subscriptions", "cancelled_by")
    op.drop_column("driver_subscriptions", "cancelled_at")
    # **ولا تُنزع قيمةُ التعداد**: Postgres لا يحذف عضواً من نوع، والنوعُ
    # نفسُه تُسقطه الترحيلةُ التي أنشأته — والقاعدةُ مكتوبةٌ في `COMMANDS.md`.
    # **وصفٌّ `cancelled` بعد النزول يصير حالاً لا يعرفها التعداد**، فتُعاد
    # إلى `expired`: الأقربُ صدقاً — انقضى ولم يعد ساري المفعول.
    op.execute(
        "UPDATE driver_subscriptions SET status = 'expired' "
        "WHERE status = 'cancelled'"
    )
