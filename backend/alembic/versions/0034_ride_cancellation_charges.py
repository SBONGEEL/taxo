"""ride cancellation charges

رسمُ الإلغاء بعد القبول (`design/CANCELLATION-FEE.md`): جدولُ الرسوم وإعداداتُه
per-country، **ونوعان جديدان في نوع القيد**.

وثلاثةُ مطبّاتٍ معروفةٍ في هذا المشروع تلتقي هنا، كما في `0018` و`0033`:

- `ALTER TYPE … ADD VALUE` لا يجوز في المعاملة التي **تستعمل** القيمة، و`env.py`
  يلفّ السلسلةَ كلَّها في معاملة — فـ`COMMIT` صريحٌ بعد الإضافة، وما بعده
  `IF NOT EXISTS` لأن ذلك الالتزام يعني أن فشلاً لاحقاً لا يتراجع عمّا سبقه.
- والأنواعُ التي أنشأتها ترحيلاتٌ سابقة (`country_code`، `currency`) تُشار إليها
  بـ`create_type=False`، وإلا فشل `upgrade` بـ«type already exists».
- والنوعان الجديدان يُسقَطان في `downgrade` صراحةً: Postgres لا يُسقط الأنواع
  مع جداولها، فترقيةٌ ثانيةٌ بعد تراجعٍ تفشل بدونها.

**وقيدُ إشارة المبلغ يُعاد بناؤه**: `cancellation_compensation` دائنٌ و
`cancellation_fee` مدين، والقيدُ القديم لا يعرفهما فيرفض كلَّ قيدٍ منهما —
أي أن الميزةَ تُبنى كاملةً ثم لا يمرّ أولُ ديناراً منها.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-15 06:41:32.201840
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0034'
down_revision: str | None = '0033'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTRY = postgresql.ENUM("LY", "JO", name="country_code", create_type=False)
CURRENCY = postgresql.ENUM("LYD", "JOD", name="currency", create_type=False)

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


def _sign_constraint(credits: tuple[str, ...], debits: tuple[str, ...]) -> str:
    def listed(values: tuple[str, ...]) -> str:
        return ", ".join(f"'{value}'" for value in values)

    return (
        f"(type IN ({listed(credits)}) AND amount > 0) OR "
        f"(type IN ({listed(debits)}) AND amount < 0) OR "
        "(type IN ('adjustment') AND amount <> 0)"
    )


def upgrade() -> None:
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS "
        "'cancellation_fee'"
    )
    op.execute(
        "ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS "
        "'cancellation_compensation'"
    )
    op.execute("COMMIT")

    op.create_table('cancellation_settings',
    sa.Column('country_code', COUNTRY, nullable=False),
    sa.Column('exempt_within_meters', sa.Integer(), server_default=sa.text('300'), nullable=False),
    sa.Column('exempt_when_location_unknown', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('block_after_unpaid', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('unpaid_after_days', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('unpaid_outcome', sa.Enum('keep_pending', 'admin_decides', 'company_bears', name='unpaid_cancellation_outcome'), server_default='keep_pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('country_code', name=op.f('pk_cancellation_settings'))
    )
    op.create_table('ride_cancellation_charges',
    sa.Column('ride_id', sa.UUID(), nullable=False),
    sa.Column('payer_user_id', sa.UUID(), nullable=False),
    sa.Column('beneficiary_driver_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('currency', CURRENCY, nullable=False),
    sa.Column('status', sa.Enum('pending', 'settled', 'waived', 'written_off', name='cancellation_charge_status'), server_default='pending', nullable=False),
    sa.Column('collected_from_ride_id', sa.UUID(), nullable=True),
    sa.Column('carrier_driver_id', sa.UUID(), nullable=True),
    sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('waived_by_user_id', sa.UUID(), nullable=True),
    sa.Column('waive_reason', sa.String(length=500), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status <> 'settled') OR settled_at IS NOT NULL", name=op.f('ck_ride_cancellation_charges_cancellation_settled_needs_time')),
    sa.CheckConstraint("(status <> 'waived') OR (waived_by_user_id IS NOT NULL AND waive_reason IS NOT NULL AND settled_at IS NOT NULL)", name=op.f('ck_ride_cancellation_charges_cancellation_waive_needs_actor')),
    sa.ForeignKeyConstraint(['beneficiary_driver_id'], ['drivers.id'], name=op.f('fk_ride_cancellation_charges_beneficiary_driver_id_drivers'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['carrier_driver_id'], ['drivers.id'], name=op.f('fk_ride_cancellation_charges_carrier_driver_id_drivers'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['collected_from_ride_id'], ['rides.id'], name=op.f('fk_ride_cancellation_charges_collected_from_ride_id_rides'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['payer_user_id'], ['users.id'], name=op.f('fk_ride_cancellation_charges_payer_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ride_id'], ['rides.id'], name=op.f('fk_ride_cancellation_charges_ride_id_rides'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['waived_by_user_id'], ['users.id'], name=op.f('fk_ride_cancellation_charges_waived_by_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ride_cancellation_charges'))
    )
    op.create_index('ix_cancellation_charge_payer_pending', 'ride_cancellation_charges', ['payer_user_id'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index(op.f('ix_ride_cancellation_charges_beneficiary_driver_id'), 'ride_cancellation_charges', ['beneficiary_driver_id'], unique=False)
    op.create_index(op.f('ix_ride_cancellation_charges_payer_user_id'), 'ride_cancellation_charges', ['payer_user_id'], unique=False)
    op.create_index(op.f('ix_ride_cancellation_charges_status'), 'ride_cancellation_charges', ['status'], unique=False)
    op.create_index('uq_cancellation_charge_ride', 'ride_cancellation_charges', ['ride_id'], unique=True)

    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"),
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        _sign_constraint(CREDITS, DEBITS),
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('uq_cancellation_charge_ride', table_name='ride_cancellation_charges')
    op.drop_index(op.f('ix_ride_cancellation_charges_status'), table_name='ride_cancellation_charges')
    op.drop_index(op.f('ix_ride_cancellation_charges_payer_user_id'), table_name='ride_cancellation_charges')
    op.drop_index(op.f('ix_ride_cancellation_charges_beneficiary_driver_id'), table_name='ride_cancellation_charges')
    op.drop_index('ix_cancellation_charge_payer_pending', table_name='ride_cancellation_charges', postgresql_where=sa.text("status = 'pending'"))
    op.drop_table('ride_cancellation_charges')
    op.drop_table('cancellation_settings')
    # الأنواعُ لا تُسقط مع جداولها في Postgres
    op.execute("DROP TYPE IF EXISTS cancellation_charge_status")
    op.execute("DROP TYPE IF EXISTS unpaid_cancellation_outcome")
    # وقيدُ الإشارة يعود إلى ما قبل النوعين: قيمةٌ في العمود لا يعرفها القيدُ
    # القديم تجعل التراجعَ نفسَه يفشل — ولذلك يُحذف القيدُ ثم يُبنى
    op.drop_constraint(
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"),
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_amount_sign_by_type",
        "wallet_transactions",
        _sign_constraint(CREDITS[:-1], DEBITS[:-1]),
    )
