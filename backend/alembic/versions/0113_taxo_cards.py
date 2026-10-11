"""taxo cards: بطاقاتُ شحن TAXO — الفئاتُ والمحلّاتُ والدفعاتُ والبطاقات، وقيدُ «شحن ببطاقة TAXO»

Revision ID: 0113
Revises: 0112
Create Date: 2026-10-11

**ما تضيفه** (SPEC §٧٣-أ/٧، §٧٣-هـ المرحلة ٢): ستّةُ جداولَ جديدة (`card_denominations` · `card_shops` · `card_batches` · `taxo_cards` ·
`taxo_card_settings` · `card_guess_alerts`) وثلاثةُ أنواع، **ومُشغّلٌ يرفض `DELETE` على الدفعات والبطاقات** كمُشغّل الدفعات في `0112`.
**ونوعُ قيدٍ دائنٌ جديد** `taxo_card` — بنمط `0097`/`0104`: القيمةُ تُختم قبل أن يُعاد بناءُ قيد الإشارة الذي يقرؤها.

**ولا تمسّ صفّاً قائماً**: الجداولُ تولد فارغة، **ولا فئةَ تُبذر** (لا تُخترع قيم)، وقيدُ الإشارة يُعاد بقوائم `0104` حرفاً مضافاً إليها
النوعُ الجديد في الدائن — **فلا يتغيّر حكمٌ على قيدٍ قائم**.

**والنزولُ يقف ما دامت بطاقةٌ أو دفعة** — ويقف وحدَه إن كُتب قيدٌ من النوع الجديد (قيدُ الإشارة القديم يرفضه).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None

#: **قائمتا `0104` حرفاً** — والجديدُ يُضاف إلى الدائن
CREDITS_BEFORE = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation", "guarantee_fee", "guarantee_refund", "guarantee_compensation",
    "commute_credit", "commute_incentive", "intercity_refund", "intercity_earning", "cashback",
)
CREDITS_AFTER = (*CREDITS_BEFORE, "taxo_card")
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay",
    "intercity_hold",
)
SIGNED = ("adjustment", "rounding")

_CARD_STATUS = postgresql.ENUM("active", "redeemed", "cancelled", name="taxo_card_status")
_BATCH_STATUS = postgresql.ENUM("active", "cancelled", name="taxo_card_batch_status")
_PAY_MODE = postgresql.ENUM("before_receipt", "after_sale", name="card_shop_payment_mode")


def _sign_constraint(credits: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(credits)}) AND amount > 0) OR "
        f"(type IN ({listed(DEBITS)}) AND amount < 0) OR "
        f"(type IN ({listed(SIGNED)}) AND amount <> 0)"
    )


def _rebuild(credits: tuple[str, ...]) -> None:
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check"
    )
    op.create_check_constraint("wallet_amount_sign_by_type", "wallet_transactions", _sign_constraint(credits))


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _no_delete(table: str) -> None:
    op.execute(
        f"""
        CREATE FUNCTION {table}_no_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{table} rows are never deleted (%)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {table}_no_delete()"
    )


def upgrade() -> None:
    # ── نوعُ القيد أوّلاً، ويُختم قبل قيد الإشارة الذي يقرؤه (نمطُ `0097`/`0104`)
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'taxo_card'")
    op.execute("COMMIT")
    _rebuild(CREDITS_AFTER)

    bind = op.get_bind()
    for enum in (_CARD_STATUS, _BATCH_STATUS, _PAY_MODE):
        enum.create(bind, checkfirst=True)

    country = postgresql.ENUM("LY", "JO", "DZ", name="country_code", create_type=False)
    currency = postgresql.ENUM("LYD", "JOD", "DZD", name="currency", create_type=False)
    pay_mode = postgresql.ENUM(name="card_shop_payment_mode", create_type=False)

    op.create_table(
        "card_denominations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_ts(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_card_denominations_card_denomination_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_denominations")),
        sa.UniqueConstraint("country_code", "amount", name=op.f("uq_card_denominations_country_code_amount")),
    )
    op.create_index(op.f("ix_card_denominations_country_code"), "card_denominations", ["country_code"])

    op.create_table(
        "card_shops",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("payment_mode", pay_mode, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_ts(),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent < 100", name=op.f("ck_card_shops_card_shop_discount_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_shops")),
    )
    op.create_index(op.f("ix_card_shops_country_code"), "card_shops", ["country_code"])

    op.create_table(
        "card_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("discount_percent_at_issue", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("payment_mode_at_issue", pay_mode, nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", postgresql.ENUM(name="taxo_card_batch_status", create_type=False), nullable=False),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_ts(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_card_batches_card_batch_amount_positive")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_card_batches_card_batch_quantity_positive")),
        sa.CheckConstraint("expires_at > valid_from", name=op.f("ck_card_batches_card_batch_window")),
        sa.CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0",
            name=op.f("ck_card_batches_card_batch_cancel_has_reason"),
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["card_shops.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_batches")),
        sa.UniqueConstraint("country_code", "number", name=op.f("uq_card_batches_country_code_number")),
    )
    op.create_index(op.f("ix_card_batches_country_code"), "card_batches", ["country_code"])
    op.create_index(op.f("ix_card_batches_shop_id"), "card_batches", ["shop_id"])

    op.create_table(
        "taxo_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("serial", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("status", postgresql.ENUM(name="taxo_card_status", create_type=False), nullable=False),
        sa.Column("redeemed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "redeemed_owner_type",
            postgresql.ENUM("rider", "driver", name="wallet_owner_type", create_type=False),
            nullable=True,
        ),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_taxo_cards_taxo_card_amount_positive")),
        sa.CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0",
            name=op.f("ck_taxo_cards_taxo_card_cancel_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'redeemed' OR (redeemed_by IS NOT NULL AND transaction_id IS NOT NULL)",
            name=op.f("ck_taxo_cards_taxo_card_redeemed_traced"),
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["card_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["redeemed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["wallet_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payment_request_id"], ["payment_requests.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxo_cards")),
        sa.UniqueConstraint("serial", name=op.f("uq_taxo_cards_serial")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_taxo_cards_code_hash")),
    )
    op.create_index(op.f("ix_taxo_cards_batch_id"), "taxo_cards", ["batch_id"])
    op.create_index(op.f("ix_taxo_cards_status"), "taxo_cards", ["status"])

    op.create_table(
        "taxo_card_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("max_wrong_per_account", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("max_wrong_per_ip", sa.Integer(), server_default=sa.text("20"), nullable=False),
        sa.Column("window_minutes", sa.Integer(), server_default=sa.text("60"), nullable=False),
        *_ts(),
        sa.CheckConstraint(
            "max_wrong_per_account >= 1 AND max_wrong_per_ip >= 1 AND window_minutes >= 1",
            name=op.f("ck_taxo_card_settings_taxo_card_settings_positive"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxo_card_settings")),
        sa.UniqueConstraint("country_code", name=op.f("uq_taxo_card_settings_country_code")),
    )

    op.create_table(
        "card_guess_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_guess_alerts")),
    )
    op.create_index(op.f("ix_card_guess_alerts_country_code"), "card_guess_alerts", ["country_code"])

    # **لا تُحذف دفعةٌ ولا بطاقة** — الإلغاءُ بسببٍ مكتوب
    _no_delete("card_batches")
    _no_delete("taxo_cards")


def downgrade() -> None:
    # **يقف ما دامت بطاقةٌ أو دفعة** — وقيدُ الإشارة القديمُ يقف وحدَه إن كُتب قيدٌ من النوع الجديد
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM card_batches) OR EXISTS (SELECT 1 FROM taxo_cards) THEN
                RAISE EXCEPTION 'taxo cards exist — downgrade of 0113 refuses to drop them';
            END IF;
        END
        $$
        """
    )
    for table in ("taxo_cards", "card_batches"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {table}_no_delete()")
    op.drop_index(op.f("ix_card_guess_alerts_country_code"), table_name="card_guess_alerts")
    op.drop_table("card_guess_alerts")
    op.drop_table("taxo_card_settings")
    op.drop_index(op.f("ix_taxo_cards_status"), table_name="taxo_cards")
    op.drop_index(op.f("ix_taxo_cards_batch_id"), table_name="taxo_cards")
    op.drop_table("taxo_cards")
    op.drop_index(op.f("ix_card_batches_shop_id"), table_name="card_batches")
    op.drop_index(op.f("ix_card_batches_country_code"), table_name="card_batches")
    op.drop_table("card_batches")
    op.drop_index(op.f("ix_card_shops_country_code"), table_name="card_shops")
    op.drop_table("card_shops")
    op.drop_index(op.f("ix_card_denominations_country_code"), table_name="card_denominations")
    op.drop_table("card_denominations")
    op.execute("DROP TYPE IF EXISTS card_shop_payment_mode")
    op.execute("DROP TYPE IF EXISTS taxo_card_batch_status")
    op.execute("DROP TYPE IF EXISTS taxo_card_status")
    _rebuild(CREDITS_BEFORE)
