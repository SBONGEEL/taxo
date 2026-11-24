"""نقاطُ الالتزام، وحملةُ الإطلاق، وعروضُ الركاب — **إضافيّةٌ وحدَها، وكلُّ مفتاحٍ مطفأ** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس،
`design/OWNER-2026-11-24-SIXTH-POINTS-LAUNCH-OFFERS-VIDEOS.md`، SPEC §١١٤)

Revision ID: 0190
Revises: 0189
Create Date: 2026-11-24

**ما تضيفه — ولا عمودَ يُحذف ولا صفَّ قائمٌ يتغيّر معناه:**

* **ب — نقاطُ الالتزام**: `commitment_rules` (قاعدةٌ لكلِّ دولة، `is_enabled = false` وقيمُ النقاط والتحويل **فارغةٌ** حتى يضعها المالك،
  وقيدٌ يمنع التشغيلَ بلا قيم) · `driver_duty_days` (يومُ الكبتن وحكمُه وسببُه) · `driver_points_entries` (النقاط: كسبٌ بباقيه
  وتاريخِ انتهائه، واستهلاكٌ الأقدمُ أوّلاً) · `subscription_credit_entries` (**رصيدُ الاشتراك — دفترٌ مستقلٌّ لا يُكتب فيه إلا
  إلحاقاً**: لا يُسحب ولا يُحوَّل لأنه ليس في `wallet_transactions` أصلاً) · قيمةُ `subscription_credit` في `payment_method`.
* **ج — حملةُ الإطلاق**: `launch_campaigns` (لكلِّ دولة، **مطفأة**، تاريخُ الإطلاق ٢٠٢٧-٠١-٠١ و٦٠ و٧ أيّامٍ افتراضاً) ·
  `launch_campaign_grants` (منحةٌ واحدةٌ لكلِّ كبتن) · `drivers.first_approved_at` (يُملأ للمعتمَدين القائمين من سجلّ التدقيق) ·
  `drivers.launch_partner_ack_at`.
* **د — عروضُ الركاب**: `promo_codes.kind` (`code` افتراضاً — **كلُّ رمزٍ قائمٍ يبقى رمزاً كما كان**) و`bearer_after_free`
  (`company` افتراضاً — **كما كان**) و`points_per_ride` · `rides.discount_bearer` · `rider_offer_entitlements` · `partner_coupons` ·
  `rider_perks` (فارغةٌ = مطفأة) · وقيمةُ القيد `rider_offer_share` (مدينٌ: حصّةُ الكبتن من خصمٍ يتحمّله).

**والنزول**: يرفض إن وُجد مالٌ أو نقاطٌ أو منحةٌ قائمة — يُوقف ويُعرض على المالك. وقيمُ التعداد تبقى (Postgres لا يحذفها).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0190"
down_revision = "0189"
branch_labels = None
depends_on = None

#: **منسوخةٌ لا مستوردة** — قوائمُ `0189`
_CREDITS = (
    "topup", "ride_earning", "transfer_in", "refund", "tip", "referral_bonus", "advance", "cancellation_compensation",
    "guarantee_fee", "guarantee_refund", "guarantee_compensation", "commute_credit", "commute_incentive", "intercity_refund",
    "intercity_earning", "cashback", "taxo_card", "goal_reward", "loyalty_reward", "cross_transfer_in",
)
_DEBITS_BEFORE = (
    "ride_payment", "commission", "transfer_out", "withdrawal", "subscription_payment", "tip_payment", "advance_repayment",
    "cancellation_fee", "skin_purchase", "guarantee_hold", "guarantee_penalty", "commute_prepay", "intercity_hold",
    "rider_plan_payment", "cross_transfer_out", "cross_transfer_fee", "card_purchase",
)
_DEBITS_AFTER = (*_DEBITS_BEFORE, "rider_offer_share")
_SIGNED = ("adjustment", "rounding")

_UUID = postgresql.UUID(as_uuid=True)
_MONEY = sa.Numeric(12, 3)


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


def _country() -> postgresql.ENUM:
    return postgresql.ENUM(name="country_code", create_type=False)


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.execute("ALTER TYPE wallet_transaction_type ADD VALUE IF NOT EXISTS 'rider_offer_share'")
    op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'subscription_credit'")
    op.execute("COMMIT")
    _rebuild(_DEBITS_AFTER)

    # ---------------------------------------------------------------- ب — نقاطُ الالتزام
    op.create_table(
        "commitment_rules",
        *_stamps(),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("window_start", sa.Time(), nullable=False, server_default=sa.text("'07:00'")),
        sa.Column("window_end", sa.Time(), nullable=False, server_default=sa.text("'23:59'")),
        sa.Column("span_minutes", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("max_break_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_total_break_minutes", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("points_per_day", sa.Integer(), nullable=True),
        sa.Column("points_per_credit_unit", sa.Integer(), nullable=True),
        sa.Column("credit_unit_value", _MONEY, nullable=True),
        sa.Column("daily_points_cap", sa.Integer(), nullable=True),
        sa.Column("monthly_points_cap", sa.Integer(), nullable=True),
        sa.Column("points_expiry_days", sa.Integer(), nullable=True),
        sa.Column("credit_expiry_days", sa.Integer(), nullable=True),
        sa.Column("require_service_area", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_accounts_per_device", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("country_code", name="uq_commitment_rules_country"),
        sa.CheckConstraint(
            "span_minutes BETWEEN 60 AND 1020 AND max_break_minutes BETWEEN 0 AND 240 "
            "AND max_total_break_minutes BETWEEN 0 AND 600 AND max_break_minutes <= max_total_break_minutes "
            "AND max_total_break_minutes < span_minutes AND window_start < window_end",
            name="commitment_rules_shape",
        ),
        sa.CheckConstraint(
            "(points_per_day IS NULL OR points_per_day > 0) AND (points_per_credit_unit IS NULL OR points_per_credit_unit > 0) "
            "AND (credit_unit_value IS NULL OR credit_unit_value > 0) AND (daily_points_cap IS NULL OR daily_points_cap > 0) "
            "AND (monthly_points_cap IS NULL OR monthly_points_cap > 0) "
            "AND (points_expiry_days IS NULL OR points_expiry_days BETWEEN 1 AND 1095) "
            "AND (credit_expiry_days IS NULL OR credit_expiry_days BETWEEN 1 AND 1095) AND max_accounts_per_device >= 1",
            name="commitment_rules_values",
        ),
        # **لا تشغيلَ بلا قيمٍ يضعها المالك** — مفتاحٌ مشتعلٌ بلا قيمة نقاطٍ يَعِد الكبتنَ بلا شيء
        sa.CheckConstraint(
            "NOT is_enabled OR (points_per_day IS NOT NULL AND points_per_credit_unit IS NOT NULL "
            "AND credit_unit_value IS NOT NULL)",
            name="commitment_rules_enabled_needs_values",
        ),
    )
    op.create_table(
        "driver_duty_days",
        *_stamps(),
        sa.Column("driver_id", _UUID, sa.ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("online_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("break_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("span_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("span_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("flags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rides_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("driver_id", "day", name="uq_driver_duty_days_driver_day"),
        sa.CheckConstraint("status IN ('met', 'not_met', 'disqualified')", name="driver_duty_days_status"),
    )
    op.create_index("ix_driver_duty_days_country_day", "driver_duty_days", ["country_code", "day"])
    op.create_table(
        "driver_points_entries",
        *_stamps(),
        sa.Column("driver_id", _UUID, sa.ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "duty_day_id", _UUID, sa.ForeignKey("driver_duty_days.id", ondelete="RESTRICT"), nullable=True, unique=True
        ),
        sa.Column("ride_id", _UUID, sa.ForeignKey("rides.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("credit_entry_id", _UUID, nullable=True),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint(
            "kind IN ('daily', 'discounted_ride', 'conversion', 'expiry', 'adjustment')", name="driver_points_kind"
        ),
        sa.CheckConstraint(
            "(kind IN ('daily', 'discounted_ride') AND points > 0 AND remaining BETWEEN 0 AND points) OR "
            "(kind IN ('conversion', 'expiry') AND points < 0 AND remaining = 0) OR "
            "(kind = 'adjustment' AND ((points < 0 AND remaining = 0) OR (points > 0 AND remaining BETWEEN 0 AND points)))",
            name="driver_points_sign",
        ),
    )
    op.create_table(
        "subscription_credit_entries",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("driver_id", _UUID, sa.ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("currency", postgresql.ENUM(name="currency", create_type=False), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("amount", _MONEY, nullable=False),
        sa.Column("balance_after", _MONEY, nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column(
            "subscription_id", _UUID, sa.ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=True,
            unique=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(300), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=True, unique=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.CheckConstraint(
            "kind IN ('points_conversion', 'subscription_payment', 'expiry', 'adjustment')", name="subscription_credit_kind"
        ),
        sa.CheckConstraint(
            "(kind = 'points_conversion' AND amount > 0) OR (kind IN ('subscription_payment', 'expiry') AND amount < 0) "
            "OR (kind = 'adjustment' AND amount <> 0)",
            name="subscription_credit_sign",
        ),
        sa.CheckConstraint("balance_after >= 0", name="subscription_credit_non_negative"),
    )
    op.execute(
        """
        CREATE FUNCTION subscription_credit_entries_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'subscription_credit_entries is append-only (%)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER subscription_credit_entries_append_only
        BEFORE UPDATE OR DELETE ON subscription_credit_entries
        FOR EACH ROW EXECUTE FUNCTION subscription_credit_entries_append_only()
        """
    )

    # ---------------------------------------------------------------- ج — حملةُ الإطلاق
    op.create_table(
        "launch_campaigns",
        *_stamps(),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("launch_date", sa.Date(), nullable=False, server_default=sa.text("'2027-01-01'")),
        sa.Column("pre_launch_free_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("post_launch_free_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("zero_commission", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_banner", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("country_code", name="uq_launch_campaigns_country"),
        sa.CheckConstraint(
            "pre_launch_free_days BETWEEN 0 AND 365 AND post_launch_free_days BETWEEN 0 AND 365",
            name="launch_campaign_days",
        ),
    )
    op.create_table(
        "launch_campaign_grants",
        *_stamps(),
        sa.Column("driver_id", _UUID, sa.ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column(
            "subscription_id", _UUID, sa.ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('pre', 'post')", name="launch_campaign_grant_kind"),
        sa.CheckConstraint("ends_at > starts_at", name="launch_campaign_grant_span"),
    )
    op.add_column("drivers", sa.Column("first_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drivers", sa.Column("launch_partner_ack_at", sa.DateTime(timezone=True), nullable=True))
    # **أوّلُ اعتمادٍ من سجلّ التدقيق** — وإلا تاريخُ الإنشاء؛ كلُّهم قبل الإطلاق على أيِّ حال
    op.execute(
        """
        UPDATE drivers d SET first_approved_at = COALESCE(
            (SELECT min(a.created_at) FROM admin_audit_logs a
              WHERE a.entity_type = 'driver' AND a.entity_id = d.id AND a.details->>'status' = 'approved'),
            d.created_at)
        WHERE d.status = 'approved'
        """
    )

    # ---------------------------------------------------------------- د — عروضُ الركاب
    op.add_column("promo_codes", sa.Column("kind", sa.String(16), nullable=False, server_default="code"))
    op.add_column("promo_codes", sa.Column("bearer_after_free", sa.String(16), nullable=False, server_default="company"))
    op.add_column("promo_codes", sa.Column("points_per_ride", sa.Integer(), nullable=True))
    op.create_check_constraint("promo_codes_kind", "promo_codes", "kind IN ('code', 'launch', 'first_ride', 'invite')")
    op.create_check_constraint("promo_codes_bearer", "promo_codes", "bearer_after_free IN ('company', 'captain')")
    op.create_check_constraint(
        "promo_codes_points_per_ride", "promo_codes", "points_per_ride IS NULL OR (points_per_ride > 0 AND kind = 'launch')"
    )
    op.add_column("rides", sa.Column("discount_bearer", sa.String(16), nullable=True))
    op.create_check_constraint(
        "rides_discount_bearer", "rides", "discount_bearer IS NULL OR discount_bearer IN ('company', 'captain')"
    )
    op.create_table(
        "rider_offer_entitlements",
        *_stamps(),
        sa.Column("rider_id", _UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("promo_code_id", _UUID, sa.ForeignKey("promo_codes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("referral_id", _UUID, nullable=True),
        sa.Column("used_ride_id", _UUID, sa.ForeignKey("rides.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.UniqueConstraint("rider_id", "promo_code_id", "source", name="uq_rider_offer_entitlement"),
        sa.CheckConstraint("source IN ('invite_friend', 'invite_inviter')", name="rider_offer_entitlement_source"),
    )
    op.create_table(
        "partner_coupons",
        *_stamps(),
        sa.Column("country_code", _country(), nullable=False, index=True),
        sa.Column("shop_name", sa.String(120), nullable=False),
        sa.Column("shop_area", sa.String(120), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("coupon_code", sa.String(40), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_table(
        "rider_perks",
        *_stamps(),
        sa.Column("country_code", _country(), nullable=False),
        sa.Column("free_cancel_seconds", sa.Integer(), nullable=True),
        sa.Column("premium_after_rides", sa.Integer(), nullable=True),
        sa.Column("premium_priority", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("country_code", name="uq_rider_perks_country"),
        sa.CheckConstraint(
            "(free_cancel_seconds IS NULL OR free_cancel_seconds BETWEEN 30 AND 900) "
            "AND (premium_after_rides IS NULL OR premium_after_rides BETWEEN 1 AND 1000)",
            name="rider_perks_values",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    held = {
        table: bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in (
            "driver_points_entries", "subscription_credit_entries", "launch_campaign_grants", "rider_offer_entitlements"
        )
    }
    shared = bind.execute(sa.text("SELECT count(*) FROM wallet_transactions WHERE type = 'rider_offer_share'")).scalar_one()
    bearers = bind.execute(sa.text("SELECT count(*) FROM rides WHERE discount_bearer IS NOT NULL")).scalar_one()
    credited = bind.execute(
        sa.text("SELECT count(*) FROM driver_subscriptions WHERE payment_method = 'subscription_credit'")
    ).scalar_one()
    if any(held.values()) or shared or bearers or credited:
        raise RuntimeError(
            f"لا نزولَ عن 0190 وفيها ما قام: {held} · قيودُ حصّة الكبتن {shared} · رحلاتٌ بمتحمِّل {bearers} · "
            f"اشتراكاتٌ برصيد {credited} — يُوقف ويُعرض على المالك"
        )
    op.drop_table("rider_perks")
    op.drop_table("partner_coupons")
    op.drop_table("rider_offer_entitlements")
    op.drop_constraint("rides_discount_bearer", "rides", type_="check")
    op.drop_column("rides", "discount_bearer")
    for name in ("promo_codes_points_per_ride", "promo_codes_bearer", "promo_codes_kind"):
        op.drop_constraint(name, "promo_codes", type_="check")
    for column in ("points_per_ride", "bearer_after_free", "kind"):
        op.drop_column("promo_codes", column)
    op.drop_column("drivers", "launch_partner_ack_at")
    op.drop_column("drivers", "first_approved_at")
    op.drop_table("launch_campaign_grants")
    op.drop_table("launch_campaigns")
    op.execute("DROP TRIGGER IF EXISTS subscription_credit_entries_append_only ON subscription_credit_entries")
    op.execute("DROP FUNCTION IF EXISTS subscription_credit_entries_append_only()")
    op.drop_table("subscription_credit_entries")
    op.drop_table("driver_points_entries")
    op.drop_index("ix_driver_duty_days_country_day", table_name="driver_duty_days")
    op.drop_table("driver_duty_days")
    op.drop_table("commitment_rules")
    _rebuild(_DEBITS_BEFORE)
