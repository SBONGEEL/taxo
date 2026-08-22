"""skin purchase ledger type

**قيدُ شراء المركبة** (`vehicle_skins`, 2026-08-22): قيمةٌ جديدةٌ في نوع القيد
**ومعها إعادةُ بناء قيد الإشارة** — وهذا ما لا يراه التوليدُ الآلي.

**ولمَ ترحيلةٌ ثانيةٌ بعد `0055`**: تلك أنشأت الجداولَ الثلاثةَ و`active_skin_id`
ولم تمسّ الدفتر. **وقد قِيس أن الميزةَ بلا هذه لا يمرّ منها ديناراً واحد**:
`invalid input value for enum wallet_transaction_type: "skin_purchase"` — أي
أن المتجرَ كلَّه يُبنى ثم يسقط عند أول شراء. وهو حرفياً ما وقع في `0034` مع
رسم الإلغاء، ومكتوبٌ هناك: «تُبنى الميزةُ كاملةً ثم لا يمرّ أولُ ديناراً منها».

وثلاثةُ مطبّاتٍ معروفةٍ في هذا المشروع تلتقي هنا كما في `0018` و`0033` و`0034`:

- `ALTER TYPE … ADD VALUE` لا يجوز في المعاملة التي **تستعمل** القيمة، و`env.py`
  يلفّ السلسلةَ كلَّها في معاملة — فـ`COMMIT` صريحٌ بعد الإضافة.
- والقيمةُ لا تُنزع في `downgrade` (Postgres لا يحذف قيمةَ تعداد)، **فيُعاد
  قيدُ الإشارة وحدَه** إلى ما قبلها: قيدٌ قديمٌ لا يعرف القيمةَ يرفض كلَّ صفٍّ
  يحملها، فالتراجعُ نفسُه يفشل إن لم يُحذف القيدُ ثم يُبنى.
- والقيدُ يُسمّى مضاعفاً داخل `op.f(...)` باصطلاح تسمية المشروع.

Revision ID: 0056
Revises: 0055
Create Date: 2026-08-22 05:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# نسخةُ اللحظة من الثلاثيات في `models/wallet.py` — الترحيلةُ تصف قاعدةً في
# زمنٍ لا نموذجاً يتغيّر
CREDITS = (
    "topup",
    "ride_earning",
    "transfer_in",
    "refund",
    "tip",
    "referral_bonus",
    "advance",
    "cancellation_compensation",
)
DEBITS = (
    "ride_payment",
    "commission",
    "transfer_out",
    "withdrawal",
    "subscription_payment",
    "tip_payment",
    "advance_repayment",
    "cancellation_fee",
)
NEW_DEBIT = "skin_purchase"


def _sign_constraint(credits: tuple[str, ...], debits: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(credits)}) AND amount > 0) OR "
        f"(type IN ({listed(debits)}) AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0)"
    )


def _rebuild(credits: tuple[str, ...], debits: tuple[str, ...]) -> None:
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"),
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        _sign_constraint(credits, debits),
    )


def upgrade() -> None:
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS "
        f"'{NEW_DEBIT}'"
    )
    op.execute("COMMIT")
    _rebuild(CREDITS, DEBITS + (NEW_DEBIT,))


def downgrade() -> None:
    _rebuild(CREDITS, DEBITS)
