"""payment requests: نظامُ الدفع الجديد — طرقُ الدفع صفوفاً لكلِّ دولة، والدفعاتُ بحالاتها الخمس

Revision ID: 0112
Revises: 0111
Create Date: 2026-10-11

**ما تضيفه** (SPEC §٧٣-أ/٥، §٧٣-هـ المرحلة ١): جدولان جديدان — `payment_providers` و`payment_requests` — وثلاثةُ أنواع
(`payment_provider_kind` · `payment_request_status` · `payment_request_purpose`)، **ومُشغّلٌ يرفض `DELETE` على الدفعات** كمُشغّل الدفتر
في `0006`: «لا تُحذف دفعةٌ أبداً» حارسٌ في القاعدة لا وعدٌ في الشيفرة.

**ولا تمسّ صفّاً قائماً**: لا عمودَ يُضاف إلى جدولٍ موجود، ولا قيمةَ تعدادٍ قائم تتغيّر، والجدولان يولدان فارغين — **فدفعُ الأردن وليبيا
لا يقرأ منهما شيئاً**. والمفتاحُ `payment_requests_enabled` نصٌّ في `feature_flags` بلا ترحيلة (غيابُ صفِّه = مطفأ).

**والنزولُ يقف ما دامت دفعةٌ واحدة** — كما يقف نزولُ `0111` ما دام للجزائر صفّ: حذفُ الجدول حذفٌ لكلِّ دفعةٍ فيه، وهو ما يمنعه المُشغّل.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None

_KIND = postgresql.ENUM(
    "cash", "bank_transfer", "purchase_code", "phone_number", name="payment_provider_kind"
)
_STATUS = postgresql.ENUM(
    "pending", "approved", "rejected", "refunded", "cancelled", name="payment_request_status"
)
_PURPOSE = postgresql.ENUM("wallet_topup", "subscription", name="payment_request_purpose")

_LIVE = "status IN ('pending', 'approved', 'refunded')"


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (_KIND, _STATUS, _PURPOSE):
        enum.create(bind, checkfirst=True)

    kind = postgresql.ENUM(name="payment_provider_kind", create_type=False)
    country = postgresql.ENUM("LY", "JO", "DZ", name="country_code", create_type=False)

    op.create_table(
        "payment_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country_code", country, nullable=False),
        sa.Column("kind", kind, nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("integration", sa.String(length=40), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("for_topup", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("for_subscription", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("account_holder", sa.String(length=120), nullable=True),
        sa.Column("account_number", sa.String(length=64), nullable=True),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("qr_image_path", sa.String(length=255), nullable=True),
        sa.Column("qr_content_type", sa.String(length=60), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_providers")),
        sa.UniqueConstraint("country_code", "code", name=op.f("uq_payment_providers_country_code_code")),
    )
    op.create_index(op.f("ix_payment_providers_country_code"), "payment_providers", ["country_code"])

    op.create_table(
        "payment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_type",
            postgresql.ENUM("rider", "driver", name="wallet_owner_type", create_type=False),
            nullable=False,
        ),
        sa.Column("country_code", country, nullable=False),
        sa.Column(
            "currency", postgresql.ENUM("LYD", "JOD", "DZD", name="currency", create_type=False), nullable=False
        ),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", kind, nullable=False),
        sa.Column(
            "purpose", postgresql.ENUM(name="payment_request_purpose", create_type=False), nullable=False
        ),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("credited_amount", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column(
            "status", postgresql.ENUM(name="payment_request_status", create_type=False), nullable=False
        ),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("reference_key", sa.String(length=120), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("receipt_path", sa.String(length=255), nullable=True),
        sa.Column("receipt_content_type", sa.String(length=60), nullable=True),
        sa.Column("receipt_sha256", sa.String(length=64), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("refund_reason", sa.String(length=500), nullable=True),
        sa.Column("refunded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("refund_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome_note", sa.String(length=500), nullable=True),
        *_ts(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payment_requests_payment_request_amount_positive")),
        sa.CheckConstraint(
            "credited_amount IS NULL OR credited_amount > 0",
            name=op.f("ck_payment_requests_payment_request_credited_positive"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR length(btrim(coalesce(rejection_reason, ''))) > 0",
            name=op.f("ck_payment_requests_payment_request_rejection_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'refunded' OR length(btrim(coalesce(refund_reason, ''))) > 0",
            name=op.f("ck_payment_requests_payment_request_refund_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0",
            name=op.f("ck_payment_requests_payment_request_cancel_has_reason"),
        ),
        sa.CheckConstraint(
            "purpose <> 'subscription' OR plan_id IS NOT NULL",
            name=op.f("ck_payment_requests_payment_request_subscription_has_plan"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["payment_providers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["refunded_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["wallet_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_transaction_id"], ["wallet_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["driver_subscriptions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_requests")),
    )
    op.create_index(op.f("ix_payment_requests_user_id"), "payment_requests", ["user_id"])
    op.create_index(op.f("ix_payment_requests_country_code"), "payment_requests", ["country_code"])
    op.create_index(op.f("ix_payment_requests_provider_id"), "payment_requests", ["provider_id"])
    op.create_index(op.f("ix_payment_requests_status"), "payment_requests", ["status"])
    op.create_index(
        "uq_payment_requests_reference_live",
        "payment_requests",
        ["provider_id", "reference_key"],
        unique=True,
        postgresql_where=sa.text(f"reference_key IS NOT NULL AND {_LIVE}"),
    )
    op.create_index(
        "uq_payment_requests_receipt_live",
        "payment_requests",
        ["provider_id", "receipt_sha256"],
        unique=True,
        postgresql_where=sa.text(f"receipt_sha256 IS NOT NULL AND {_LIVE}"),
    )
    op.create_index(
        "uq_payment_requests_external",
        "payment_requests",
        ["provider_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    # **لا تُحذف دفعةٌ أبداً** (قرارُ المالك) — كمُشغّل الدفتر في `0006`، **لكنه يرفض `DELETE` وحدَه**: الحالاتُ الخمسُ تتغيّر بـ`UPDATE`
    op.execute(
        """
        CREATE FUNCTION payment_requests_no_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'payment_requests rows are never deleted (%)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER payment_requests_no_delete
        BEFORE DELETE ON payment_requests
        FOR EACH ROW EXECUTE FUNCTION payment_requests_no_delete()
        """
    )


def downgrade() -> None:
    # **يقف ما دامت دفعةٌ واحدة** — حذفُ الجدول حذفٌ لكلِّ دفعةٍ فيه
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM payment_requests) THEN
                RAISE EXCEPTION 'payment_requests holds rows — downgrade of 0112 refuses to drop payments';
            END IF;
        END
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS payment_requests_no_delete ON payment_requests")
    op.execute("DROP FUNCTION IF EXISTS payment_requests_no_delete()")
    op.drop_index("uq_payment_requests_external", table_name="payment_requests")
    op.drop_index("uq_payment_requests_receipt_live", table_name="payment_requests")
    op.drop_index("uq_payment_requests_reference_live", table_name="payment_requests")
    op.drop_index(op.f("ix_payment_requests_status"), table_name="payment_requests")
    op.drop_index(op.f("ix_payment_requests_provider_id"), table_name="payment_requests")
    op.drop_index(op.f("ix_payment_requests_country_code"), table_name="payment_requests")
    op.drop_index(op.f("ix_payment_requests_user_id"), table_name="payment_requests")
    op.drop_table("payment_requests")
    op.drop_index(op.f("ix_payment_providers_country_code"), table_name="payment_providers")
    op.drop_table("payment_providers")
    op.execute("DROP TYPE IF EXISTS payment_request_purpose")
    op.execute("DROP TYPE IF EXISTS payment_request_status")
    op.execute("DROP TYPE IF EXISTS payment_provider_kind")
