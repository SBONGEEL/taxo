"""الحجزُ المضمون (SPEC §٦٣-ج/٣) — كبتنٌ محجوزٌ مسبقاً، ورسمٌ يحفظه TAXO، واعتذارٌ بعد التأكيد بغرامةٍ وإنذارٍ وحجب.

**وأوّلُ صفِّ إعداداتٍ للخدمات الجديدة** (`service_settings`، لكلِّ سوق): **أرقامُ المالك افتراضاتٌ للأردن** (الرسمُ ١٫٠٠٠ · التأخّرُ ١٠
دقائق · العتبةُ اعتذاران · الحجبُ شهر) **ولليبيا رسمٌ صفر** — لم يقل رقماً بالدينار الليبيّ، والصفرُ يُخفي الخدمة. **والخدماتُ التالية
تضيف أعمدتَها إليه** بترحيلاتها، فلوحةٌ واحدةٌ لا ستّ.

**ونوعا الدفتر الجديدان خمسة**: `guarantee_hold` (مدينٌ على الراكب لحظةَ الحجز، بلا دائن — المالُ عند TAXO) · `guarantee_fee` (دائنٌ
للكبتن حين تتمّ الرحلة، بلا مدين — يخرج مما حُفظ) · `guarantee_refund` (دائنٌ للراكب حين يُردّ) · `guarantee_penalty` و
`guarantee_compensation` (من الكبتن المعتذر إلى الراكب). **ومعها إعادةُ بناء قيد الإشارة** كـ`0056` — وبغيرها لا يمرّ ديناراً.

**وليس جدولَ مالٍ يُمسّ قائمُه**: أعمدةُ الحجز بافتراضٍ يصف كلَّ حجزٍ قائمٍ حرفاً (`guaranteed = false`)، ولا قيدَ يُكتب.

**و`downgrade` مقيسٌ لا مقروء**: يحذف الجداولَ والأعمدة ويعيد قيدَ الإشارة — **وقيمُ التعداد لا تُنزع** (Postgres)، **وقيدٌ بنوعٍ جديدٍ
يُسقط التراجعَ** عمداً: رسمٌ محفوظٌ لم يُحسم لا يُمحى أثرُه بتراجع.

Revision ID: 0092
Revises: 0091
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None

CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance",
    "cancellation_compensation",
)
DEBITS = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment",
    "advance_repayment", "cancellation_fee", "skin_purchase",
)
NEW_CREDITS = ("guarantee_fee", "guarantee_refund", "guarantee_compensation")
NEW_DEBITS = ("guarantee_hold", "guarantee_penalty")


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
        op.f("ck_wallet_transactions_wallet_amount_sign_by_type"), "wallet_transactions", type_="check"
    )
    op.create_check_constraint("wallet_amount_sign_by_type", "wallet_transactions", _sign_constraint(credits, debits))


def upgrade() -> None:
    for value in NEW_CREDITS + NEW_DEBITS:
        op.execute(f"ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS '{value}'")
    op.execute("COMMIT")
    _rebuild(CREDITS + NEW_CREDITS, DEBITS + NEW_DEBITS)

    op.create_table(
        "service_settings",
        sa.Column("country_code", postgresql.ENUM("LY", "JO", name="country_code", create_type=False), nullable=False),
        sa.Column("guarantee_fee", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("guarantee_late_minutes", sa.SmallInteger(), server_default=sa.text("10"), nullable=False),
        sa.Column("guarantee_confirm_minutes", sa.SmallInteger(), server_default=sa.text("60"), nullable=False),
        sa.Column("guarantee_confirm_window_minutes", sa.SmallInteger(), server_default=sa.text("10"), nullable=False),
        sa.Column("guarantee_offer_hours", sa.SmallInteger(), server_default=sa.text("24"), nullable=False),
        sa.Column("guarantee_ban_threshold", sa.SmallInteger(), server_default=sa.text("2"), nullable=False),
        sa.Column("guarantee_ban_days", sa.SmallInteger(), server_default=sa.text("30"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "guarantee_fee >= 0 AND guarantee_late_minutes > 0 AND guarantee_confirm_minutes > 0 "
            "AND guarantee_confirm_window_minutes > 0 AND guarantee_offer_hours > 0 "
            "AND guarantee_ban_threshold > 0 AND guarantee_ban_days > 0",
            name=op.f("ck_service_settings_service_settings_guarantee_valid"),
        ),
        sa.PrimaryKeyConstraint("country_code", name=op.f("pk_service_settings")),
    )
    op.execute(
        "INSERT INTO service_settings (country_code, guarantee_fee) VALUES ('JO', 1.000), ('LY', 0.000)"
    )

    op.add_column("ride_bookings", sa.Column("guaranteed", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column(
        "ride_bookings",
        sa.Column("guarantee_fee_at_booking", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("ride_bookings", sa.Column("guarantee_state", sa.String(length=16), nullable=True))
    op.add_column("ride_bookings", sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("ride_bookings", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ride_bookings", sa.Column("confirm_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ride_bookings", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_ride_bookings_driver_id_drivers"), "ride_bookings", "drivers", ["driver_id"], ["id"]
    )
    op.create_index(op.f("ix_ride_bookings_driver_id"), "ride_bookings", ["driver_id"])
    op.create_check_constraint(
        "booking_guarantee_valid",
        "ride_bookings",
        "guarantee_fee_at_booking >= 0 AND (guarantee_state IS NULL OR guarantee_state IN "
        "('held', 'paid', 'refunded')) AND (guaranteed OR (driver_id IS NULL AND guarantee_state IS NULL))",
    )

    op.add_column("drivers", sa.Column("guarantee_banned_until", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "driver_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("penalty_amount", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("penalty_shortfall", sa.Numeric(12, 3), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('guarantee_withdrawal') AND penalty_amount >= 0 AND penalty_shortfall >= 0",
            name=op.f("ck_driver_warnings_driver_warning_valid"),
        ),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booking_id"], ["ride_bookings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_warnings")),
    )
    op.create_index(op.f("ix_driver_warnings_driver_id"), "driver_warnings", ["driver_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_driver_warnings_driver_id"), table_name="driver_warnings")
    op.drop_table("driver_warnings")
    op.drop_column("drivers", "guarantee_banned_until")
    op.drop_constraint(op.f("ck_ride_bookings_booking_guarantee_valid"), "ride_bookings", type_="check")
    op.drop_index(op.f("ix_ride_bookings_driver_id"), table_name="ride_bookings")
    op.drop_constraint(op.f("fk_ride_bookings_driver_id_drivers"), "ride_bookings", type_="foreignkey")
    for column in (
        "confirmed_at", "confirm_requested_at", "accepted_at", "driver_id", "guarantee_state",
        "guarantee_fee_at_booking", "guaranteed",
    ):
        op.drop_column("ride_bookings", column)
    op.drop_table("service_settings")
    _rebuild(CREDITS, DEBITS)
