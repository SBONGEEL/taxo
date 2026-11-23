"""captain cards: بطاقاتُ TAXO يبيعها الكباتن — **إضافيّةٌ وحدَها، والبيعُ مطفأ** (أمرُ المالك ٢٠٢٦-١١-٢٣، `design/CAPTAIN-CARDS-2026-11-23.md`)

Revision ID: 0189
Revises: 0188
Create Date: 2026-11-23

**ما تضيفه — ولا عمودَ يُحذف ولا صفَّ يتغيّر:**
- قيمةٌ في نوع القيد (`wallet_transaction_type`: `card_purchase`) — **مدينٌ بلا دائن**: ثمنُ دفعةٍ يشتريها الكبتنُ من محفظته.
  **وتُختم قبل أيِّ استعمال**، ثمّ يُعاد بناءُ قيد الإشارة بها (نمطُ `0157`/`0187`: القوائمُ منسوخةٌ لا مستوردة).
- `card_batches.seller_driver_id` (فارغٌ لكلِّ دفعةٍ قائمة) + فهرس، ونوعُ الدفعة `captain` في قيد الأنواع، **وقيدٌ يقرن النوعَ بالبائع**.
- `taxo_card_settings.captain_discount_percent` (فارغٌ = البيعُ مغلق) بين ٠ و٥٠.

**ولا مفتاحَ يُكتب**: `taxo_cards_captain_sales` غائبٌ = مطفأ. **ولا خصمَ يُضبط**: المالكُ يضبطه من اللوحة.

**والنزول**: يُعاد قيدُ الإشارة والأنواع كما كانا ويُحذف العمودان — **ويرفض النزولَ إن وُجدت دفعةُ كبتنٍ أو قيدُ شراء**
(حذفُ العمود يمحو من باع، وقيدٌ قائمٌ بنوعٍ خارج القيد يُسقط إعادتَه). **وقيمةُ التعداد تبقى** — Postgres لا يحذف قيمةَ enum.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0189"
down_revision = "0188"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `0187` (آخرُ من أعاد بناء القيد)
_CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card", "goal_reward", "loyalty_reward", "cross_transfer_in",
)
_DEBITS_BEFORE = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
    "rider_plan_payment", "cross_transfer_out", "cross_transfer_fee",
)
_DEBITS_AFTER = (*_DEBITS_BEFORE, "card_purchase")
_SIGNED = ("adjustment", "rounding")


def _listed(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _rebuild(debits: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check")
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        f"(type IN ({_listed(_CREDITS)}) AND amount > 0) OR "
        f"(type IN ({_listed(debits)}) AND amount < 0) OR "
        f"(type IN ({_listed(_SIGNED)}) AND amount <> 0)",
    )


def upgrade() -> None:
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'card_purchase'")
    op.execute("COMMIT")
    _rebuild(_DEBITS_AFTER)

    op.add_column("card_batches", sa.Column("seller_driver_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_card_batches_seller_driver_id_drivers"), "card_batches", "drivers", ["seller_driver_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_card_batches_seller_driver_id"), "card_batches", ["seller_driver_id"])
    op.drop_constraint("card_batches_kind_known", "card_batches", type_="check")
    op.create_check_constraint("card_batches_kind_known", "card_batches", "kind IN ('batch', 'gift', 'pos', 'captain')")
    op.create_check_constraint(
        "card_batches_captain_has_seller", "card_batches", "(kind = 'captain') = (seller_driver_id IS NOT NULL)"
    )

    op.add_column("taxo_card_settings", sa.Column("captain_discount_percent", sa.Numeric(5, 2), nullable=True))
    op.create_check_constraint(
        "taxo_card_settings_captain_discount_range",
        "taxo_card_settings",
        "captain_discount_percent IS NULL OR (captain_discount_percent >= 0 AND captain_discount_percent <= 50)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    sold = bind.execute(sa.text("SELECT count(*) FROM card_batches WHERE kind = 'captain'")).scalar_one()
    charged = bind.execute(sa.text("SELECT count(*) FROM wallet_transactions WHERE type = 'card_purchase'")).scalar_one()
    if sold or charged:
        raise RuntimeError(
            f"لا نزولَ عن 0189 وفيها مالٌ قائم: {sold} دفعةَ كبتن و{charged} قيدَ شراء — يُوقف ويُعرض على المالك"
        )
    op.drop_constraint("taxo_card_settings_captain_discount_range", "taxo_card_settings", type_="check")
    op.drop_column("taxo_card_settings", "captain_discount_percent")
    op.drop_constraint("card_batches_captain_has_seller", "card_batches", type_="check")
    op.drop_constraint("card_batches_kind_known", "card_batches", type_="check")
    op.create_check_constraint("card_batches_kind_known", "card_batches", "kind IN ('batch', 'gift', 'pos')")
    op.drop_index(op.f("ix_card_batches_seller_driver_id"), table_name="card_batches")
    op.drop_constraint(op.f("fk_card_batches_seller_driver_id_drivers"), "card_batches", type_="foreignkey")
    op.drop_column("card_batches", "seller_driver_id")
    _rebuild(_DEBITS_BEFORE)
