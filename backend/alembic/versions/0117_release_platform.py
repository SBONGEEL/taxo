"""release platform: نظامُ الحزمة في سجلِّ الإصدارات — أندرويد، ثمّ iOS لاحقاً

Revision ID: 0117
Revises: 0116
Create Date: 2026-10-12

**ما تضيفه** (قرارُ المالك 2026-10-12، SPEC §43.8): `app_releases.platform` (`android` · `ios`) **افتراضُه `android`** — فكلُّ صفٍّ قائمٍ
يبقى ما كان: حزمةَ أندرويد. **والمفتاحُ الفريدُ يصير (التطبيق، النظام، الرقم)**: رقمُ iOS يُرقَّم وحدَه فيلتقي برقم أندرويد.

**والنزولُ لا يحذف صفّاً**: صفُّ iOS لا مكانَ له في جدولٍ بلا نظام — **فيقف النزولُ ما بقي منه صفٌّ** ويقول ذلك، ولا يمحوه.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None

RELEASE_PLATFORM = postgresql.ENUM(
    "android",
    "ios",
    name="release_platform",
    create_type=False,
)


def upgrade() -> None:
    RELEASE_PLATFORM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "app_releases",
        sa.Column(
            "platform", RELEASE_PLATFORM, nullable=False, server_default="android"
        ),
    )
    op.drop_constraint("uq_app_releases_app_build", "app_releases", type_="unique")
    op.create_unique_constraint(
        "uq_app_releases_app_platform_build",
        "app_releases",
        ["app", "platform", "build"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    ios = bind.execute(
        sa.text("SELECT count(*) FROM app_releases WHERE platform = 'ios'")
    ).scalar_one()
    if ios:
        raise RuntimeError(
            f"في سجلِّ الإصدارات {ios} صفَّ iOS — والجدولُ بلا نظامٍ يجعلها أندرويد. "
            "لا يُحذف صفٌّ بنزول: احذفها من اللوحة بقرارٍ ثمّ أعد النزول."
        )
    op.drop_constraint(
        "uq_app_releases_app_platform_build", "app_releases", type_="unique"
    )
    op.create_unique_constraint(
        "uq_app_releases_app_build", "app_releases", ["app", "build"]
    )
    op.drop_column("app_releases", "platform")
    RELEASE_PLATFORM.drop(op.get_bind(), checkfirst=True)
