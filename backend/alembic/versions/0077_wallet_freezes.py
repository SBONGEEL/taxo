"""wallet freezes: تجميدٌ لكلِّ محفظةٍ لا للحساب كلِّه

Revision ID: 0077
Revises: 0076
Create Date: 2026-09-20

**ما تنقله**: `users.wallet_frozen` (عمودٌ واحدٌ للحساب) ⇐ `wallet_freezes`
(صفٌّ لكلِّ محفظةٍ مجمَّدة). انظر `app/models/wallet_freeze.py` للعلّة.

**والمجمَّدُ اليومَ يُفرَد صفّاً لكلِّ محفظةٍ يملكها** — فلا يُرفع عنه تجميدٌ في
الطريق. **ومصدرُ «يملكها» هو مصدرُ `User.roles` نفسُه**: صفوفُ `user_roles`
**واتّحادُها مع العمود `users.role`** (`has_role_clause` يضمّه حارساً ضدّ الفقد)
— فحسابٌ كُتب بالعمود وحدَه لا يفلت من تجميده.

**وقياسُ الترحيل** (2026-09-20، قبل تشغيلها): المجمَّدون **صفرٌ على قاعدة
التطوير** (من 43 حساباً) **وصفرٌ على الإنتاج** (من 10) — فهي تكتب صفرَ صفٍّ في
الاثنين. والمكتوبُ هنا لمن يأتي بعدُ، لا لصفوفٍ قائمة.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


# **الدورُ الذي يملك كلَّ محفظة** — وهي `wallet.WALLET_ROLE` نفسُها بلغة SQL.
# ولا تُقرأ من بايثون: ترحيلةٌ تستورد الخدمةَ تتغيّر بتغيّرها بعد شهر
_ROLE_OF_WALLET = {"rider": "rider", "driver": "driver"}


def upgrade() -> None:
    op.create_table(
        "wallet_freezes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_type",
            postgresql.ENUM(
                "rider", "driver", name="wallet_owner_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("frozen_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["frozen_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_freezes")),
        sa.UniqueConstraint("user_id", "owner_type", name="uq_wallet_freezes_wallet"),
    )
    op.create_index(
        op.f("ix_wallet_freezes_user_id"), "wallet_freezes", ["user_id"], unique=False
    )

    # **كلُّ مجمَّدٍ يُفرَد صفّاً لكلِّ محفظةٍ يملكها.** والدورُ يُقرأ من
    # المجموعة **والعمود** معاً (`UNION` يزيل التكرار) كما يقرؤهما `User.roles`
    for wallet, role in _ROLE_OF_WALLET.items():
        op.execute(
            sa.text(
                """
                INSERT INTO wallet_freezes (id, user_id, owner_type, reason)
                SELECT gen_random_uuid(), u.id, CAST(:wallet AS wallet_owner_type),
                       'منقولٌ من users.wallet_frozen (الترحيلة 0077)'
                FROM users u
                WHERE u.wallet_frozen
                  AND (
                        u.role::text = :role
                        OR EXISTS (
                            SELECT 1 FROM user_roles g
                            WHERE g.user_id = u.id AND g.role::text = :role
                        )
                      )
                """
            ).bindparams(wallet=wallet, role=role)
        )

    op.drop_column("users", "wallet_frozen")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "wallet_frozen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # **والرجوعُ يجمع ما فُرِّق**: من جُمِّدت له محفظةٌ واحدةٌ يعود مجمَّداً على
    # حسابه كلِّه — وهو العطبُ الذي خرجنا منه، **ولا مخرجَ منه في عمودٍ واحد**
    op.execute(
        "UPDATE users SET wallet_frozen = true "
        "WHERE id IN (SELECT user_id FROM wallet_freezes)"
    )
    op.alter_column("users", "wallet_frozen", server_default=None)

    op.drop_index(op.f("ix_wallet_freezes_user_id"), table_name="wallet_freezes")
    op.drop_table("wallet_freezes")
