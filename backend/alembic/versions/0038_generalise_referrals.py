"""generalise referrals to accounts

تعميمُ الإحالة (`design/REFERRALS-GENERALIZATION.md`، وقراراتُ المالك 2026-08-16):
طرفا الإحالة ينتقلان من `drivers` إلى `users`، والإعداداتُ تصير صفّاً لكل
(دولة، نوع)، ويُضاف كوبونُ الترحيب و`promo_codes.is_public`.

**وهذه ترحيلةُ بيانات قبل أن تكون ترحيلةَ شكل**، وثلاثةُ أشياء فيها لا تُهمَل:

1. **الرموزُ القائمةُ تنتقل كما هي.** كبتنٌ نشر رمزَه في مجموعةٍ لا يجوز أن
   يُبطل رمزُه بترحيلةٍ داخلية — فيُنسخ `drivers.referral_code` إلى صاحبه في
   `users` **قبل** أن يُحذف العمود.
2. **وصفوفُ الإحالة تنتقل بمُعرّفات أصحابها**، بضمِّ `drivers` مرتين — مرةً
   للمُحيل ومرةً للمُحال. وصفٌّ يضيع هنا مكافأةٌ لا يعرف أحدٌ أنها كانت.
3. **والصفُّ القديم في `referral_settings` يصير صفَّ `driver`**: هو ما كان
   يعنيه قبل التعميم حرفاً — وقراءتُه صفَّ `rider` كانت ستمنح برنامجَ الركاب
   مبلغاً ضُبط للسائقين.

**والتراجعُ يعيد ما يستطيع**: الجداولُ والأعمدةُ تعود، والصفوفُ تعود بمُعرّفات
الكباتن — **وما لا يعود صفُّ إحالةٍ طرفُه راكب**، إذ لا موضع له في الشكل
القديم. وذلك مكتوبٌ لا مسكوتٌ عنه: تراجعٌ بعد تشغيل برنامج الركاب يفقد صفوفَه،
فمن يتراجع يعرف ثمنَه.

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-16 17:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------- (١) الرمزُ على الحساب
    op.add_column(
        "users", sa.Column("referral_code", sa.String(length=16), nullable=True)
    )
    op.execute(
        """
        UPDATE users
           SET referral_code = drivers.referral_code
          FROM drivers
         WHERE drivers.user_id = users.id
           AND drivers.referral_code IS NOT NULL
        """
    )
    op.create_index(
        op.f("ix_users_referral_code"), "users", ["referral_code"], unique=True
    )
    op.drop_index(op.f("ix_drivers_referral_code"), table_name="drivers")
    op.drop_column("drivers", "referral_code")

    # ------------------------------------------- (٢) الإحالةُ بين حسابين
    op.create_table(
        "referrals",
        sa.Column("referrer_user_id", sa.UUID(), nullable=False),
        sa.Column("referred_user_id", sa.UUID(), nullable=False),
        sa.Column("code_used", sa.String(length=16), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_amount", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("reward_currency", sa.String(length=3), nullable=True),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "referrer_user_id <> referred_user_id",
            name=op.f("ck_referrals_referral_not_self"),
        ),
        sa.CheckConstraint(
            "(rewarded_at IS NULL AND reward_amount IS NULL "
            "AND reward_currency IS NULL AND transaction_id IS NULL) OR "
            "(rewarded_at IS NOT NULL AND reward_amount IS NOT NULL "
            "AND reward_currency IS NOT NULL AND transaction_id IS NOT NULL)",
            name=op.f("ck_referrals_referral_reward_all_or_nothing"),
        ),
        sa.CheckConstraint(
            "reward_amount IS NULL OR reward_amount > 0",
            name=op.f("ck_referrals_referral_reward_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["referred_user_id"], ["users.id"],
            name=op.f("fk_referrals_referred_user_id_users"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referrer_user_id"], ["users.id"],
            name=op.f("fk_referrals_referrer_user_id_users"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["wallet_transactions.id"],
            name=op.f("fk_referrals_transaction_id_wallet_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referrals")),
        sa.UniqueConstraint(
            "referred_user_id", name=op.f("uq_referrals_referred_user_id")
        ),
    )
    op.create_index(
        op.f("ix_referrals_referrer_user_id"), "referrals", ["referrer_user_id"]
    )
    op.create_index(op.f("ix_referrals_rewarded_at"), "referrals", ["rewarded_at"])

    # الصفوفُ تنتقل بمُعرّفات أصحابها — ضمٌّ مرتين، للمُحيل وللمُحال
    op.execute(
        """
        INSERT INTO referrals (
            id, referrer_user_id, referred_user_id, code_used,
            rewarded_at, reward_amount, reward_currency, transaction_id,
            created_at, updated_at
        )
        SELECT r.id, referrer.user_id, referred.user_id, r.code_used,
               r.rewarded_at, r.reward_amount, r.reward_currency, r.transaction_id,
               r.created_at, r.updated_at
          FROM driver_referrals AS r
          JOIN drivers AS referrer ON referrer.id = r.referrer_driver_id
          JOIN drivers AS referred ON referred.id = r.referred_driver_id
        """
    )
    op.drop_table("driver_referrals")

    # ------------------------------------ (٣) الإعداداتُ صفٌّ لكل (دولة، نوع)
    op.add_column(
        "referral_settings",
        sa.Column(
            "referral_type", sa.String(length=32), server_default="driver",
            nullable=False,
        ),
    )
    op.add_column(
        "referral_settings",
        sa.Column(
            "female_bonus_amount", sa.Numeric(precision=12, scale=3),
            server_default=sa.text("0"), nullable=False,
        ),
    )
    op.add_column(
        "referral_settings", sa.Column("monthly_cap", sa.Integer(), nullable=True)
    )
    op.add_column(
        "referral_settings",
        sa.Column("referred_promo_code_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_referral_settings_referred_promo_code_id_promo_codes"),
        "referral_settings", "promo_codes", ["referred_promo_code_id"], ["id"],
        ondelete="SET NULL",
    )

    # الفريدُ ينتقل من الدولة وحدها إلى (دولة، نوع)
    op.drop_index(
        op.f("ix_referral_settings_country_code"), table_name="referral_settings"
    )
    op.create_index(
        op.f("ix_referral_settings_country_code"), "referral_settings",
        ["country_code"],
    )
    op.create_unique_constraint(
        op.f("uq_referral_settings_country_type"), "referral_settings",
        ["country_code", "referral_type"],
    )

    # القيدُ القديم لا يعرف العلاوة، فيُعاد بناؤه ليحرسها
    op.drop_constraint(
        op.f("ck_referral_settings_referral_amounts_not_negative"),
        "referral_settings", type_="check",
    )
    op.create_check_constraint(
        "referral_amounts_not_negative", "referral_settings",
        "reward_amount >= 0 AND required_rides >= 0 AND female_bonus_amount >= 0",
    )
    op.create_check_constraint(
        "referral_cap_positive_or_null", "referral_settings",
        "monthly_cap IS NULL OR monthly_cap > 0",
    )

    # ------------------------------------------------ (٤) كوبونٌ يُمنح ولا يُكتب
    op.add_column(
        "promo_codes",
        sa.Column(
            "is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("promo_codes", "is_public")

    op.drop_constraint(
        op.f("ck_referral_settings_referral_cap_positive_or_null"),
        "referral_settings", type_="check",
    )
    op.drop_constraint(
        op.f("ck_referral_settings_referral_amounts_not_negative"),
        "referral_settings", type_="check",
    )
    op.create_check_constraint(
        "referral_amounts_not_negative", "referral_settings",
        "reward_amount >= 0 AND required_rides >= 0",
    )
    # **وصفوفُ الركاب تُحذف قبل استعادة الفريد على الدولة** — وإلا اصطدم صفّان
    # لدولةٍ واحدة. وهو الثمنُ المكتوب في رأس الملف
    op.execute("DELETE FROM referral_settings WHERE referral_type <> 'driver'")
    op.drop_constraint(
        op.f("uq_referral_settings_country_type"), "referral_settings", type_="unique"
    )
    op.drop_index(
        op.f("ix_referral_settings_country_code"), table_name="referral_settings"
    )
    op.create_index(
        op.f("ix_referral_settings_country_code"), "referral_settings",
        ["country_code"], unique=True,
    )
    op.drop_constraint(
        op.f("fk_referral_settings_referred_promo_code_id_promo_codes"),
        "referral_settings", type_="foreignkey",
    )
    for column in (
        "referred_promo_code_id", "monthly_cap", "female_bonus_amount",
        "referral_type",
    ):
        op.drop_column("referral_settings", column)

    op.create_table(
        "driver_referrals",
        sa.Column("referrer_driver_id", sa.UUID(), nullable=False),
        sa.Column("referred_driver_id", sa.UUID(), nullable=False),
        sa.Column("code_used", sa.String(length=16), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_amount", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("reward_currency", sa.String(length=3), nullable=True),
        sa.Column("transaction_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "referrer_driver_id <> referred_driver_id",
            name=op.f("ck_driver_referrals_referral_not_self"),
        ),
        sa.CheckConstraint(
            "(rewarded_at IS NULL AND reward_amount IS NULL "
            "AND reward_currency IS NULL AND transaction_id IS NULL) OR "
            "(rewarded_at IS NOT NULL AND reward_amount IS NOT NULL "
            "AND reward_currency IS NOT NULL AND transaction_id IS NOT NULL)",
            name=op.f("ck_driver_referrals_referral_reward_all_or_nothing"),
        ),
        sa.CheckConstraint(
            "reward_amount IS NULL OR reward_amount > 0",
            name=op.f("ck_driver_referrals_referral_reward_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["referred_driver_id"], ["drivers.id"],
            name=op.f("fk_driver_referrals_referred_driver_id_drivers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referrer_driver_id"], ["drivers.id"],
            name=op.f("fk_driver_referrals_referrer_driver_id_drivers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["wallet_transactions.id"],
            name=op.f("fk_driver_referrals_transaction_id_wallet_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_referrals")),
        sa.UniqueConstraint(
            "referred_driver_id", name=op.f("uq_driver_referrals_referred_driver_id")
        ),
    )
    op.create_index(
        op.f("ix_driver_referrals_referrer_driver_id"), "driver_referrals",
        ["referrer_driver_id"],
    )
    op.create_index(
        op.f("ix_driver_referrals_rewarded_at"), "driver_referrals", ["rewarded_at"]
    )
    # **وما طرفُه راكبٌ يسقط هنا**: لا موضعَ له في الشكل القديم
    op.execute(
        """
        INSERT INTO driver_referrals (
            id, referrer_driver_id, referred_driver_id, code_used,
            rewarded_at, reward_amount, reward_currency, transaction_id,
            created_at, updated_at
        )
        SELECT r.id, referrer.id, referred.id, r.code_used,
               r.rewarded_at, r.reward_amount, r.reward_currency, r.transaction_id,
               r.created_at, r.updated_at
          FROM referrals AS r
          JOIN drivers AS referrer ON referrer.user_id = r.referrer_user_id
          JOIN drivers AS referred ON referred.user_id = r.referred_user_id
        """
    )
    op.drop_table("referrals")

    op.add_column(
        "drivers", sa.Column("referral_code", sa.String(length=16), nullable=True)
    )
    op.execute(
        """
        UPDATE drivers
           SET referral_code = users.referral_code
          FROM users
         WHERE users.id = drivers.user_id
           AND users.referral_code IS NOT NULL
        """
    )
    op.create_index(
        op.f("ix_drivers_referral_code"), "drivers", ["referral_code"], unique=True
    )
    op.drop_index(op.f("ix_users_referral_code"), table_name="users")
    op.drop_column("users", "referral_code")
