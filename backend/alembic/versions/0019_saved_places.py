"""الأماكن المحفوظة للراكب (`FUTURE-FEATURES` بند 1)

جدولٌ واحد بلا تعدادٍ جديد ولا عمودٍ على جدولٍ قائم — فلا فخَّ فيه من فخاخ
`0018`: لا `ALTER TYPE` ولا فهرسٌ جزئيٌّ يُعاد بناؤه، والترحيلةُ ذرّيةٌ كما
ينبغي لكل ترحيلة.

و`ON DELETE CASCADE` بخلاف الجداول المالية: بيانُ راحةٍ يذهب مع صاحبه.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_places",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column(
            "point",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("icon", sa.String(24), nullable=False, server_default="star"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "label", name="uq_saved_places_user_label"),
    )
    op.create_index("ix_saved_places_user_id", "saved_places", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_places_user_id", table_name="saved_places")
    op.drop_table("saved_places")
