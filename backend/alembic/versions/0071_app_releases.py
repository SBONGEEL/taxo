"""سجلُّ إصدارات التطبيقات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.

**والجدولُ فارغٌ يومَ يُنشأ**، وذلك شرطٌ لا تفصيل: **غيابُ الصفِّ يُقرأ «لا
تدخّل»** — فلا شاشةَ تحديثٍ تظهر لأحدٍ حتى يكتب مشرفٌ صفّاً بيده. **وبذرُ صفٍّ
هنا كان يقفل التطبيقاتِ على الناس بترحيلة.**

**و`client_app` تُنشأ هنا لأنها لم تكن في القاعدة قط**: كانت تعداداً في
بايثون يُرسله العميلُ عند الدخول (`core/app_scope.py`)، **ولا عمودَ يحملها** —
فهذا أوّلُ موضعٍ تصير فيه قيمةً مخزَّنة.

Revision ID: 0071
Revises: 0070
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

CLIENT_APP = postgresql.ENUM(
    "rider",
    "driver",
    "panel",
    name="client_app",
    create_type=False,
)


def upgrade() -> None:
    CLIENT_APP.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "app_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app", CLIENT_APP, nullable=False),
        # **`versionCode` لا اسمُ نسخة**: هو ما يقارن به أندرويد، و`versionName`
        # ثابتٌ في هذه الشجرة — قِيست حزمتان بـ`1.0` و`1.1` ورقمُهما `392`
        sa.Column("build", sa.Integer(), nullable=False),
        sa.Column("min_supported_build", sa.Integer(), nullable=False),
        sa.Column("download_url", sa.String(length=500), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=False),
        sa.Column(
            "reminder_hours", sa.Integer(), nullable=False, server_default="24"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("app", "build", name="uq_app_releases_app_build"),
        # **الحدُّ لا يتجاوز الإصدارَ نفسَه**: وإلا قُفل صاحبُ أحدث حزمةٍ
        # خارجَ تطبيقه ولا شيءَ يحمّله ليخرج
        sa.CheckConstraint(
            "min_supported_build <= build", name="ck_app_releases_min_within"
        ),
        sa.CheckConstraint("build > 0", name="ck_app_releases_build_positive"),
        sa.CheckConstraint(
            "min_supported_build > 0", name="ck_app_releases_min_positive"
        ),
        sa.CheckConstraint(
            "reminder_hours >= 1 AND reminder_hours <= 720",
            name="ck_app_releases_reminder_range",
        ),
    )
    op.create_index("ix_app_releases_app", "app_releases", ["app"])


def downgrade() -> None:
    op.drop_index("ix_app_releases_app", table_name="app_releases")
    op.drop_table("app_releases")
    CLIENT_APP.drop(op.get_bind(), checkfirst=True)
