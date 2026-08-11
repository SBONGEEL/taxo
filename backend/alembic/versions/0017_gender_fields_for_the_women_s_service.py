"""حقولُ الخدمة النسائية (المرحلة 10-ج)

نوعان جديدان و**سبعةُ أعمدة**: جنسُ صاحب الحساب وختمُه وتفضيلُه الافتراضي
وعدّادُ البلاغات عليه، وتفضيلُ الكبتن الدائم، وتفضيلُ الرحلة الواحدة وسببُ
إلغائها المصنَّف.

`gender_preference` يظهر في **ثلاثة** أعمدة، فيُنشأ النوعان صراحةً في المقدمة
ثم تشير إليهما الأعمدة بـ`create_type=False`: بغير ذلك يعيد autogenerate
`CREATE TYPE` مع كل عمودٍ فيفشل الثاني بـ«type already exists».

وكلُّ الأعمدة تصل بقيمةٍ محايدة: `any` و`0` و`NULL`. فتشغيلُ الترحيلة وحده لا
يغيّر سلوك أحد — والميزةُ نفسها خلف `women_service_enabled` وهو مطفأٌ حتى
تُراجَع أجناسُ الكباتن المعتمدين.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENDER = postgresql.ENUM("male", "female", name="gender")
PREFERENCE = postgresql.ENUM("male", "female", "any", name="gender_preference")

# الإشارة إلى نوعٍ قائم: لا `CREATE TYPE` مع كل عمود
gender_ref = postgresql.ENUM("male", "female", name="gender", create_type=False)
preference_ref = postgresql.ENUM(
    "male", "female", "any", name="gender_preference", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    GENDER.create(bind, checkfirst=True)
    PREFERENCE.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("gender", gender_ref, nullable=True))
    op.add_column(
        "users",
        sa.Column("gender_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "ride_gender_preference",
            preference_ref,
            server_default="any",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "gender_mismatch_reports",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_users_gender"), "users", ["gender"], unique=False)

    op.add_column(
        "drivers",
        sa.Column(
            "gender_preference", preference_ref, server_default="any", nullable=False
        ),
    )
    op.add_column(
        "rides",
        sa.Column(
            "gender_preference", preference_ref, server_default="any", nullable=False
        ),
    )
    op.add_column(
        "rides", sa.Column("cancel_reason_code", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("rides", "cancel_reason_code")
    op.drop_column("rides", "gender_preference")
    op.drop_column("drivers", "gender_preference")
    op.drop_index(op.f("ix_users_gender"), table_name="users")
    op.drop_column("users", "gender_mismatch_reports")
    op.drop_column("users", "ride_gender_preference")
    op.drop_column("users", "gender_verified_at")
    op.drop_column("users", "gender")

    # postgres لا يُسقط النوع مع أعمدته — وبغير هذا تفشل إعادة الترقية
    op.execute("DROP TYPE IF EXISTS gender_preference")
    op.execute("DROP TYPE IF EXISTS gender")
