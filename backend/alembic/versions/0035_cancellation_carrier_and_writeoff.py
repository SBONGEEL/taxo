"""cancellation carrier, write-off and the carried badge

تكملةُ رسم الإلغاء (`design/CANCELLATION-FEE.md` §5 و§6-أ و§10):

* **مهلةُ الحامل** في سياسة الدولة، و**عمودُ منعه** على `drivers` — بشكلِ
  `advance_blocked` نفسِه ولسببه نفسِه، **ومنفصلٌ عنه**: دَينان لمُقرِضَين
  مختلفَين، وعمودٌ واحدٌ يحملهما يجعل سدادَ أحدهما يرفع منعَ الآخر.
* **إسنادُ الحامل ووقتُه ومهلتُه** على صفِّ الرسم، ومعها أعمدةُ الشطب بشكلِ
  شطبِ السلفة حرفياً (`written_off_at` / `written_off_by` / `writeoff_reason`).
* **وما عُرض على الكبتن قبل أن يقبل** (`rides.carried_cancellation_fee`):
  تجميدٌ لا بيتٌ ثانٍ — المصدرُ يبقى `ride_cancellation_charges`، وهذا ما
  بُني عليه رضاه، كـ`commission_percent_at_ride` و`scheduled_for`.

**والقيدُ الجديدُ اسمُه قصيرٌ عمداً**: Postgres يقصّ ما تجاوز ٦٣ محرفاً ويهشّه،
فيختلف اسمُه في القاعدة عن اسمِه في النموذج و`test_migrations_match_models`
يقرأ ذلك انحرافاً في كل تشغيل.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-15 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cancellation_settings",
        sa.Column(
            "carrier_grace_hours",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "drivers",
        sa.Column(
            "cancellation_carry_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "rides",
        sa.Column(
            "carried_cancellation_fee",
            sa.Numeric(precision=12, scale=3),
            nullable=True,
        ),
    )

    for column in (
        sa.Column("carrier_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("carrier_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("written_off_by_user_id", sa.UUID(), nullable=True),
        sa.Column("writeoff_reason", sa.String(length=500), nullable=True),
    ):
        op.add_column("ride_cancellation_charges", column)

    op.create_foreign_key(
        op.f("fk_ride_cancellation_charges_written_off_by_user_id_users"),
        "ride_cancellation_charges",
        "users",
        ["written_off_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "cancellation_writeoff_needs_reason",
        "ride_cancellation_charges",
        "(status <> 'written_off') OR "
        "(written_off_at IS NOT NULL AND writeoff_reason IS NOT NULL)",
    )
    op.create_index(
        "ix_cancellation_charge_carrier_pending",
        "ride_cancellation_charges",
        ["carrier_driver_id"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cancellation_charge_carrier_pending",
        table_name="ride_cancellation_charges",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_constraint(
        op.f(
            "ck_ride_cancellation_charges_cancellation_writeoff_needs_reason"
        ),
        "ride_cancellation_charges",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_ride_cancellation_charges_written_off_by_user_id_users"),
        "ride_cancellation_charges",
        type_="foreignkey",
    )
    for name in (
        "writeoff_reason",
        "written_off_by_user_id",
        "written_off_at",
        "carrier_due_at",
        "carrier_assigned_at",
    ):
        op.drop_column("ride_cancellation_charges", name)

    op.drop_column("rides", "carried_cancellation_fee")
    op.drop_column("drivers", "cancellation_carry_blocked")
    op.drop_column("cancellation_settings", "carrier_grace_hours")
