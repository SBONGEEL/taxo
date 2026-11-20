"""**مصدرُ الحزمة في سجلِّ الإصدارات** (أمرُ المالك ٢٠٢٦-١١-٢٠ السابع): `app_releases.source`.

* لكلِّ متجرٍ (Galaxy Store · AppGallery · GetApps …) رابطُ «تحديث» وحدٌّ أدنى، **و`default` هو Google Play والموقع**.
* **كلُّ صفٍّ قائمٍ يصير `default`** بالقيمة الافتراضية — فلا يتغيّر حكمٌ ولا رابطٌ لأحدٍ بالترحيلة.
* والمفتاحُ الفريدُ يضمّ المتجر: الرقمُ نفسُه في Play وفي Galaxy Store صفّان لا تكرار.

**لا يمسّ جدولَ مال.** **والرجوعُ** يرفض النزولَ إن وُجد صفٌّ لمتجر — لا يُحذف صفٌّ بنزول.

Revision ID: 0183
Revises: 0182
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0183"
down_revision = "0182"
branch_labels = None
depends_on = None

RELEASE_SOURCE = postgresql.ENUM(
    "default",
    "galaxy",
    "huawei",
    "xiaomi",
    "oppo",
    "vivo",
    "honor",
    "palm",
    "uptodown",
    "aptoide",
    name="release_source",
    create_type=False,
)


def upgrade() -> None:
    RELEASE_SOURCE.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "app_releases",
        sa.Column("source", RELEASE_SOURCE, nullable=False, server_default="default"),
    )
    op.drop_constraint(
        "uq_app_releases_app_platform_build", "app_releases", type_="unique"
    )
    op.create_unique_constraint(
        "uq_app_releases_app_platform_source_build",
        "app_releases",
        ["app", "platform", "source", "build"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    stores = bind.execute(
        sa.text("SELECT count(*) FROM app_releases WHERE source <> 'default'")
    ).scalar_one()
    if stores:
        raise RuntimeError(
            f"في سجلِّ الإصدارات {stores} صفَّ متجر — والجدولُ بلا متجرٍ يجعلها صفوفَ Play. "
            "لا يُحذف صفٌّ بنزول: احذفها من اللوحة بقرارٍ ثمّ أعد النزول."
        )
    op.drop_constraint(
        "uq_app_releases_app_platform_source_build", "app_releases", type_="unique"
    )
    op.create_unique_constraint(
        "uq_app_releases_app_platform_build",
        "app_releases",
        ["app", "platform", "build"],
    )
    op.drop_column("app_releases", "source")
    RELEASE_SOURCE.drop(op.get_bind(), checkfirst=True)
