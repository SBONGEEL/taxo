"""التحصيلُ اليدويُّ بكليك — صورةُ الرمز، ومدّةُ المراجعة، ومصدرُ التأكيد.

**ثلاثةُ أشياءَ في ترحيلةٍ واحدة لأنها فعلٌ واحد**: شاشةُ دفعٍ يدويٍّ لا تقوم
بلا الثلاثة.

## ١) `payment_settings.cliq_qr_path` — **صورةٌ تُرفع لا رمزٌ يُولَّد**

**قِيس قبل أن يُبنى** (2026-08-29): رمزُ كليك **يصدره القابض** — `cliq/acquirer.py`
يأخذ `qr_payload` من جوابه ويرمي «مزود كليك لم يعد برمز الدفع» إن غاب،
**والمحاكي يصنع `CLIQ|alias|amount|ref` وهي صيغةٌ مخترعةٌ للفحص لا معيار**.
فالرمزُ **لا يُشتقّ من alias وحده**، **وباركودٌ لا يعمل أسوأُ من غيابه** —
فالحقلُ صورةٌ يرفعها المالكُ من تطبيق مصرفه.

## ٢) `cliq_review_min_minutes` / `cliq_review_max_minutes`

**المدّةُ وعدٌ لمن يدفع** (قرارُ المالك): «تتم المراجعة خلال ٣ إلى ٥ دقائق»
جملةٌ **تصير كذباً يومَ تكثر الطلباتُ ولا تلحق المراجعة**. فالعددان في
القاعدة **يُعدَّلان بلا نشر**، ويُحقنان في الجملة.

## ٣) `provider_orders.source` — **يدويٌّ أم قابض**

**التحصيلُ خطوةٌ واحدةٌ يقرأها الاشتراك: «تأكيد الدفع»** — يملؤها المشرفُ
اليوم بيده، ويملؤها القابضُ غداً بإشعاره. **وما بعدها لا يعرف مَن ملأها.**
**والمصدرُ يُختم على الصفّ** ليُقرأ في التدقيق من أين جاء التأكيد **ولا
يُخمَّن بعد شهر**.

**و`provider` يبقى `cliq_acquirer`**: القضيبُ قضيبُ كليك، **والمختلفُ من
يحصّل**. فيومَ يصل العقدُ **يتبدّل المصدرُ ولا يُعاد بناء**.

Revision ID: 0059
Revises: 0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

SOURCE = postgresql.ENUM(
    "manual", "acquirer", name="provider_order_source", create_type=False
)


def upgrade() -> None:
    op.add_column(
        "payment_settings",
        sa.Column("cliq_qr_path", sa.String(length=512), nullable=True),
    )
    # **٣ و٥ اليومَ** — قيمتان تُعدَّلان من اللوحة، والافتراضُ ما وعد به المالك
    op.add_column(
        "payment_settings",
        sa.Column(
            "cliq_review_min_minutes",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )
    op.add_column(
        "payment_settings",
        sa.Column(
            "cliq_review_max_minutes",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
    )
    op.create_check_constraint(
        "payment_cliq_review_window",
        "payment_settings",
        "cliq_review_min_minutes > 0 AND cliq_review_max_minutes >= cliq_review_min_minutes",
    )

    SOURCE.create(op.get_bind(), checkfirst=True)
    # **الصفوفُ القائمةُ كلُّها من قابض**: لم يكن ثمّة مصدرٌ آخرُ قبل اليوم
    op.add_column(
        "provider_orders",
        sa.Column("source", SOURCE, nullable=False, server_default="acquirer"),
    )


def downgrade() -> None:
    op.drop_column("provider_orders", "source")
    SOURCE.drop(op.get_bind(), checkfirst=True)
    op.drop_constraint(
        "payment_cliq_review_window", "payment_settings", type_="check"
    )
    op.drop_column("payment_settings", "cliq_review_max_minutes")
    op.drop_column("payment_settings", "cliq_review_min_minutes")
    op.drop_column("payment_settings", "cliq_qr_path")
