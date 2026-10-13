"""الدولُ والحدود (SPEC §٧٤-أ/٢–٣) — صلاحيةٌ وثلاثةُ جداول، **ولا عمودَ لحال السوق ولا مال**.

**ما تضيفه**:
- `markets.manage` في `admin_permission` — **لا تُعطى لأحدٍ افتراضاً** (`services/permissions.SENSITIVE`)، فلا صفَّ يُكتب هنا.
- `country_markets` (ظهورُ المغلقة في التسجيل، وغيابُ الصفِّ «قريباً») · `market_borders` (صفٌّ واحد، وغيابُه «الحدودُ مفروضة») ·
  `border_allowances` (السماحُ بالعمل من الخارج، ونزعُه ختم).

**ولا صفَّ يُبذر**: الغيابُ في الثلاثة هو الافتراضُ الآمنُ المكتوب — **فالإنتاجُ بعدها كما قبلها حرفاً**: الأردنُ مفتوح، وليبيا
والجزائرُ مغلقتان (مفتاحُ `country_visible` القائم لا يُمسّ)، والحدودُ مفروضةٌ للجميع.

**و`downgrade` مقيسٌ لا مقروء** (`tests/test_migrations.py`): **يقف إن كان في الجداول صفّ** — قرارُ مالكٍ مكتوبٌ لا يُمحى بنزول —
**ولا يوسّع أحداً** في نزع الصلاحية (قاعدةُ `0103` حرفاً).

Revision ID: 0118
Revises: 0117
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None

_NEW_PERMISSION = "markets.manage"

SIGNUP_DISPLAY = postgresql.ENUM("soon", "hidden", name="signup_display", create_type=False)
COUNTRY_CODE = postgresql.ENUM(name="country_code", create_type=False)


def upgrade() -> None:
    op.execute(f"ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS '{_NEW_PERMISSION}'")
    SIGNUP_DISPLAY.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "country_markets",
        sa.Column("country_code", COUNTRY_CODE, primary_key=True),
        sa.Column("signup_display", SIGNUP_DISPLAY, nullable=False, server_default="soon"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "market_borders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.text("true"), unique=True),
        sa.Column("enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("singleton IS TRUE", name="market_borders_singleton"),
    )

    op.create_table(
        "border_allowances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(btrim(reason)) >= 3", name="border_allowance_reason"),
    )
    op.create_index("ix_border_allowances_user_id", "border_allowances", ["user_id"])
    op.create_index(
        "uq_border_allowance_active",
        "border_allowances",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    held = {
        table: bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in ("country_markets", "market_borders", "border_allowances")
    }
    written = {table: count for table, count in held.items() if count}
    if written:
        raise RuntimeError(
            f"في جداول الدول والحدود صفوفٌ كتبها المالك ({written}) — والنزولُ يمحوها. "
            "لا يُمحى قرارٌ مكتوبٌ بنزول: أعدها إلى افتراضها من صفحة «الدول» بقرارٍ ثمّ أعد النزول."
        )
    op.drop_index("uq_border_allowance_active", table_name="border_allowances")
    op.drop_index("ix_border_allowances_user_id", table_name="border_allowances")
    op.drop_table("border_allowances")
    op.drop_table("market_borders")
    op.drop_table("country_markets")
    SIGNUP_DISPLAY.drop(bind, checkfirst=True)

    # **والنزولُ لا يوسّع أحداً** — من كانت صلاحيتُه هذه وحدَها يُكتب له `read.only` قبل الحذف (قاعدةُ `0103`)
    op.execute(
        "INSERT INTO admin_permissions (id, user_id, permission, granted_at) "
        "SELECT gen_random_uuid(), user_id, 'read.only'::admin_permission, now() FROM admin_permissions "
        f"GROUP BY user_id HAVING bool_and(permission::text = '{_NEW_PERMISSION}')"
    )
    op.execute(f"DELETE FROM admin_permissions WHERE permission::text = '{_NEW_PERMISSION}'")
    members = bind.execute(sa.text("SELECT unnest(enum_range(NULL::admin_permission))::text")).scalars().all()
    values = ", ".join(f"'{value}'" for value in members if value != _NEW_PERMISSION)
    op.execute(sa.text(f"CREATE TYPE admin_permission_old AS ENUM ({values})"))
    op.execute(
        "ALTER TABLE admin_permissions "
        "ALTER COLUMN permission TYPE admin_permission_old "
        "USING permission::text::admin_permission_old"
    )
    op.execute("DROP TYPE admin_permission")
    op.execute("ALTER TYPE admin_permission_old RENAME TO admin_permission")
