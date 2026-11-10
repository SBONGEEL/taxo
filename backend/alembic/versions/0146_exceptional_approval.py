"""الاعتمادُ الاستثنائيّ ومتابعةُ الوثائق (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ١ و٢).

* صلاحيّةُ `drivers.exceptional` (حسّاسة: للمالك ومن يمنحه بالاسم).
* أعمدةُ الوسم على `drivers`: متى اعتُمد دون وثائق ومن اعتمده وسببُه، ومهلةُ الرفع، وتذكيراتُه.
* `document_settings` لكلِّ دولة: المهلةُ وتكرارُ التذكير وأيامُ التنبيه قبل الانتهاء.

**لا جدولَ مالٍ يُمسّ.** والرجوعُ يحذف الأعمدةَ والجدول؛ وقيمةُ التعداد تبقى (Postgres لا ينزعها) بلا أثر.

Revision ID: 0146
Revises: 0145
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0146"
down_revision = "0145"
branch_labels = None
depends_on = None

_COLUMNS = (
    "exceptional_approved_at",
    "exceptional_approved_by",
    "exceptional_reason",
    "documents_deadline_at",
    "document_reminders_enabled",
    "document_reminded_at",
    "deadline_warning_stage",
)


def upgrade() -> None:
    op.execute("ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS 'drivers.exceptional'")
    op.add_column("drivers", sa.Column("exceptional_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drivers", sa.Column("exceptional_approved_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_drivers_exceptional_approved_by_users"), "drivers", "users", ["exceptional_approved_by"], ["id"], ondelete="SET NULL"
    )
    op.add_column("drivers", sa.Column("exceptional_reason", sa.Text(), nullable=True))
    op.add_column("drivers", sa.Column("documents_deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "drivers",
        sa.Column("document_reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("drivers", sa.Column("document_reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "drivers", sa.Column("deadline_warning_stage", sa.SmallInteger(), nullable=False, server_default=sa.text("0"))
    )
    op.create_table(
        "document_settings",
        sa.Column("country_code", postgresql.ENUM(name="country_code", create_type=False), nullable=False),
        sa.Column("exceptional_deadline_days", sa.Integer(), nullable=False, server_default=sa.text("14")),
        sa.Column("exceptional_reminder_days", sa.SmallInteger(), nullable=False, server_default=sa.text("3")),
        sa.Column("expiry_notice_days", postgresql.ARRAY(sa.Integer()), nullable=False, server_default=sa.text("'{30,7,1}'")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_document_settings_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("country_code", name=op.f("pk_document_settings")),
    )


def downgrade() -> None:
    op.drop_table("document_settings")
    op.drop_constraint(op.f("fk_drivers_exceptional_approved_by_users"), "drivers", type_="foreignkey")
    for column in _COLUMNS:
        op.drop_column("drivers", column)
