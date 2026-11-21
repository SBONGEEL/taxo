"""**إشعارُ «جديد: ودجات TAXO لشاشتك»** (أمرُ المالك ٢٠٢٦-١١-٢١ الثالث، البند ٦) — **لمن حدّث وحدَه**، خلف `widgets_announce` المطفأ.

* `device_tokens.shell_widgets`: **الجهازُ يقول إن غلافَه يحمل الودجاتِ الجديدة** (طريقةُ التثبيت `pinSupported` في `LauncherPlugin`) — يُكتب في
  كلِّ تسجيل كـ`push_channels`، **والافتراضُ `false`**: غلافٌ أقدمُ لا يقوله فلا يصله إشعارٌ عن ودجاتٍ ليست فيه.
* `notification_campaigns.widgets_only`: **حملةٌ لا تصل إلا تلك الأجهزة** — بابُ الحملات القائم كلُّه (إطفاءُ التسويق، ساعاتُ الهدوء،
  الحدُّ الأسبوعيّ، سطرُ تسليمٍ لكلِّ مستخدم) **ولا بابٌ ثانٍ للإرسال**.
* **لا جدولَ مال، ولا صفَّ يُكتب** — عمودان بافتراضٍ لا يغيّر سلوكَ شيءٍ قائم. **والرجوعُ يرفعهما.**

Revision ID: 0185
Revises: 0184
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0185"
down_revision = "0184"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_tokens", sa.Column("shell_widgets", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_campaigns", sa.Column("widgets_only", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("notification_campaigns", "widgets_only")
    op.drop_column("device_tokens", "shell_widgets")
