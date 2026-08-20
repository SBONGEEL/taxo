"""تعليماتُ الملاحة على الرحلة — «التعليمة التالية» (البند ٧)

**عمودٌ واحدٌ نصّيٌّ قابلٌ للفراغ**: `rides.route_steps`، يحمل خطواتِ Mapbox
بنصِّها وهندستها ومسافتها، مجمَّدةً مع الخط ومنه لحظةَ القبول.

**ولا فهرسَ عليه**: لا يُبحث به ولا يُرشَّح — يُقرأ بمفتاح الرحلة وحدَه، وفهرسٌ
على عمودٍ نصّيٍّ كبيرٍ كلفةُ كتابةٍ بلا قارئ.

**وما حذفتُه من ناتج التوليد**: اقترح `autogenerate` إسقاطَ الافتراضِ الخادميِّ
عن `otp_message_templates.id` — **وهو ليس من هذا التغيير**. وترحيلةٌ تحمل ما لم
يُقصد تغيّر جدولاً لا أحدَ يراجعه في مراجعةِ ميزةٍ أخرى.

Revision ID: 0052
Revises: 0051
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("route_steps", sa.Text(), nullable=True))


def downgrade() -> None:
    # **يُسقَط بلا حفظ**: التعليماتُ مشتقّةٌ من Mapbox لا بياناتُ مستخدم،
    # وتُطلب من جديد في أول قبولٍ بعد الترقية. ولا شيءَ يُفقد لصاحبه.
    op.drop_column("rides", "route_steps")
