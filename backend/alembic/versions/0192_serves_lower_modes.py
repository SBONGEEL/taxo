"""«الأعلى يأخذ الأدنى» بنمطين لكلِّ دولة (SPEC §١٢٠، قرارُ المالك ٢٠٢٦-١١-٢٦ — `design/OWNER-2026-11-26-SERVES-LOWER.md`).

- `dispatch_settings.serves_lower_mode`: `off` (كما كان — علمُ الفئة `serves_lower` وحدَه) · `choice` (النمط أ «باختيار الكابتن») ·
  `mandatory` (النمط ب «إلزامي للجميع»).
- `serves_lower_choice_default`: افتراضُ مفتاح الكابتن في النمط أ (مشتعل).
- `serves_lower_order`: `same_first` (كابتنُ الفئة المطلوبة أوّلاً عند تقارب المسافة) · `nearest` (الأقربُ أيّاً كانت فئتُه)،
  و`serves_lower_margin_meters` ما يُعدّ «تقارباً».
- `drivers.serves_lower_prefs`: اختياراتُ الكابتن الصريحة في النمط أ (`{"economy": false}`) — والغائبُ يأخذ الافتراض.

**والأردنُّ على النمط ب من الآن** (نصُّ القرار)، وليبيا والجزائر كما هما (`off`). **ولا جدولَ مالٍ هنا**: الأجرةُ تُجمَّد عند إنشاء
الرحلة بفئة الطلب، فيأخذ كابتنُ الفئة الأعلى أجرةَ الأدنى بلا سطرٍ جديد.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0192"
down_revision = "0191"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dispatch_settings", sa.Column("serves_lower_mode", sa.String(16), nullable=False, server_default="off"))
    op.add_column(
        "dispatch_settings", sa.Column("serves_lower_choice_default", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "dispatch_settings", sa.Column("serves_lower_order", sa.String(16), nullable=False, server_default="same_first")
    )
    op.add_column(
        "dispatch_settings", sa.Column("serves_lower_margin_meters", sa.Integer(), nullable=False, server_default="500")
    )
    op.create_check_constraint(
        "dispatch_serves_lower_mode_valid", "dispatch_settings", "serves_lower_mode IN ('off', 'choice', 'mandatory')"
    )
    op.create_check_constraint(
        "dispatch_serves_lower_order_valid", "dispatch_settings", "serves_lower_order IN ('same_first', 'nearest')"
    )
    op.create_check_constraint(
        "dispatch_serves_lower_margin_range", "dispatch_settings", "serves_lower_margin_meters BETWEEN 0 AND 5000"
    )
    op.add_column(
        "drivers",
        sa.Column("serves_lower_prefs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    # **الأردنُّ على النمط ب** — صفٌّ قائمٌ يُحدَّث، وغائبٌ يُنشأ بقيمه الافتراضيّة من القاعدة
    op.execute(
        "INSERT INTO dispatch_settings (id, country_code, serves_lower_mode, created_at, updated_at) "
        "VALUES (gen_random_uuid(), 'JO', 'mandatory', now(), now()) "
        "ON CONFLICT (country_code) DO UPDATE SET serves_lower_mode = 'mandatory'"
    )


def downgrade() -> None:
    op.drop_column("drivers", "serves_lower_prefs")
    op.drop_constraint("dispatch_serves_lower_margin_range", "dispatch_settings", type_="check")
    op.drop_constraint("dispatch_serves_lower_order_valid", "dispatch_settings", type_="check")
    op.drop_constraint("dispatch_serves_lower_mode_valid", "dispatch_settings", type_="check")
    op.drop_column("dispatch_settings", "serves_lower_margin_meters")
    op.drop_column("dispatch_settings", "serves_lower_order")
    op.drop_column("dispatch_settings", "serves_lower_choice_default")
    op.drop_column("dispatch_settings", "serves_lower_mode")
