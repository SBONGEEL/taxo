"""التحقق الثنائي لدخول اللوحة — TOTP (SPEC القسم 14.1، المرحلة 12-د)

ثلاثةُ جداولٍ جديدة ولا عمودَ على جدولٍ قائم، **ولا نوعَ ENUM جديد** — فلا
ينطبق عليها شيءٌ من فخاخ `0018`: لا `ALTER TYPE` يحتاج commit صريحاً، ولا فهرسٌ
جزئيٌّ يُعاد بناؤه، ولا قيدٌ يستعمل قيمةَ تعدادٍ وُلدت في نفس المعاملة.
والترحيلةُ ذرّيةٌ كما ينبغي لكل ترحيلة.

وحدَها `security_settings` تحتاج قيدَ «صفٍّ واحد»: عمودٌ ثابتُ القيمة عليه
`unique` + `CHECK`، فالصفُّ الثاني يرتدّ من القاعدة لا من نيّة المستدعي.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# القيم نفسُها في `models/security_setting.py` — والقيدُ في القاعدة كي لا
# يكفي حارسُ الطبقة العليا وحده (نفسُ منهج قيود الدفتر في `0006`)
MIN_IDLE_TIMEOUT_MINUTES = 5
MAX_IDLE_TIMEOUT_MINUTES = 60
DEFAULT_IDLE_TIMEOUT_MINUTES = 30


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "user_totp",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_encrypted", postgresql.JSONB(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recovery_codes_verified_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_step", sa.BigInteger(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_totp_user_id"),
    )

    op.create_table(
        "user_recovery_codes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_user_recovery_codes_user_id", "user_recovery_codes", ["user_id"]
    )
    # البصمةُ مفهرسةٌ لأن الاستهلاك يستعلم بها عن **الصفِّ الواحد** ثم يقفله؛
    # بلا الفهرس يصير الاستهلاك مسحاً للجدول تحت قفل
    op.create_index(
        "ix_user_recovery_codes_code_hash", "user_recovery_codes", ["code_hash"]
    )

    op.create_table(
        "security_settings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "singleton", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "admin_totp_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "admin_idle_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(DEFAULT_IDLE_TIMEOUT_MINUTES)),
        ),
        *_timestamps(),
        sa.UniqueConstraint("singleton", name="uq_security_settings_singleton"),
        # الأسماء **مجرّدةٌ من البادئة** هنا كما في النموذج: اصطلاحُ التسمية في
        # `models/base.py` يضيف `ck_<table>_` بنفسه، واسمٌ مُبادَأٌ سلفاً يخرج
        # مضاعفاً ومقطوعاً بترقيمٍ عشوائي — فيراه `test_migrations_match_models`
        # فرقاً بين النموذج والقاعدة
        sa.CheckConstraint("singleton IS TRUE", name="security_settings_singleton"),
        sa.CheckConstraint(
            f"admin_idle_timeout_minutes BETWEEN {MIN_IDLE_TIMEOUT_MINUTES} "
            f"AND {MAX_IDLE_TIMEOUT_MINUTES}",
            name="security_idle_timeout_range",
        ),
    )
    # **ولا صفَّ يُبذَر هنا**: الغيابُ يُقرأ بالافتراضات (لا إلزام، ثلاثون
    # دقيقة)، فصفٌّ مبذورٌ لا يضيف إلا موضعاً ثانياً تُكتب فيه الافتراضات


def downgrade() -> None:
    op.drop_table("security_settings")
    op.drop_index(
        "ix_user_recovery_codes_code_hash", table_name="user_recovery_codes"
    )
    op.drop_index("ix_user_recovery_codes_user_id", table_name="user_recovery_codes")
    op.drop_table("user_recovery_codes")
    op.drop_table("user_totp")
