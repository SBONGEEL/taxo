"""حمايةُ الدفع — الموجةُ الأولى (SPEC §٨٧، أمرُ المالك ٢٠٢٦-١٠-٢٨): الإخفاءُ الآليُّ وسجلُّ المطابقة اليوميّة وصلاحيةُ دفتر الوسيط.

**ولا مساسَ بجدول مال** — أعمدةٌ تقبل الفراغ على `payment_providers` (جدولُ إعداد)، وجدولٌ جديدٌ للتقارير، وقيمةُ صلاحية:

- `payment_providers.hidden_reason` / `hidden_at` / `hidden_auto` — **طريقةٌ أُخفيت بسببٍ مكتوب** (آليّاً بثلاث إخفاقاتٍ متتالية، أو بيد
  المالك). **ومن يعيدها المالكُ وحدَه بسببٍ ووقت** (`POST /admin/payment-methods/{id}/restore`).
- `gateway_reconciliations` — **تقريرُ المطابقة اليوميّة** لكلِّ وسيطٍ وسوق: ما سُئل عنه، وما طابق، وما افترق بتفصيله. **تقريرٌ لا يكتب
  في الدفتر** ولا يغيّر حالَ دفعة.
- `admin_permission` ← `gateway_ledger.read` — **دفترُ SofizPay** (المعاملاتُ من Stellar). لا تُعطى افتراضاً، والمالكُ يملكها بدوره.

**وChargily في الجزائر** أخفاه المالكُ ٢٠٢٦-١٠-٢٨ (§٨٦) — يُكتب سببُه في العمود الجديد فيقع تحت القفل نفسِه: لا يعيده غيرُ المالك.

Revision ID: 0133
Revises: 0132
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0133"
down_revision = "0132"
branch_labels = None
depends_on = None

_COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
_NEW_PERMISSION = "gateway_ledger.read"
_CHARGILY_DZ_REASON = "أخفاه المالك ٢٠٢٦-١٠-٢٨ — دفعاتُ Edahabia تفشل عند Chargily، حتى يجيب دعمُه"


def upgrade() -> None:
    op.execute(f"ALTER TYPE admin_permission ADD VALUE IF NOT EXISTS '{_NEW_PERMISSION}'")
    op.add_column("payment_providers", sa.Column("hidden_reason", sa.String(500), nullable=True))
    op.add_column("payment_providers", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "payment_providers",
        sa.Column("hidden_auto", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "gateway_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("integration", sa.String(40), nullable=False),
        sa.Column("country_code", _COUNTRY, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("matched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("mismatched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("unreachable", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trigger", sa.String(16), nullable=False, server_default=sa.text("'daily'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_gateway_reconciliations_created_at", "gateway_reconciliations", ["created_at"])
    # **إخفاءُ المالك القائمُ يُكتب سببُه** — فلا يعيده غيرُه من الباب العامّ
    op.execute(
        sa.text(
            "UPDATE payment_providers SET hidden_reason = :reason, hidden_at = now(), hidden_auto = false "
            "WHERE integration = 'chargily' AND country_code = 'DZ' AND enabled = false"
        ).bindparams(reason=_CHARGILY_DZ_REASON)
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_reconciliations_created_at", table_name="gateway_reconciliations")
    op.drop_table("gateway_reconciliations")
    op.drop_column("payment_providers", "hidden_auto")
    op.drop_column("payment_providers", "hidden_at")
    op.drop_column("payment_providers", "hidden_reason")
    # **والنزولُ لا يوسّع أحداً** — قاعدةُ `0131` حرفاً
    bind = op.get_bind()
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
