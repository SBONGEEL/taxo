"""إعداداتُ التوزيع — **نمطُه ومهلتُه وتبريدُه من اللوحة** (قرارُ المالك 2026-08-30).

## ما تغيّر في القاعدة نفسِها، لا في تنفيذها

كانت `services/dispatch.py` تحمل خمسةَ ثوابتَ فوقها تعليقٌ صريح: «**ثوابت SPEC
القسم 5.3 — لا إعدادات: هذه قواعد التوزيع نفسها**». **فنقلُها إلى اللوحة
مخالفةُ مواصفةٍ لا تفصيلُ تنفيذ** — ولذلك عُدِّل §5.3 في الجلسة نفسِها، **قبل
الإيداع**، كما تأمر قاعدةُ الانحراف في `CLAUDE.md`.

## ١) `mode` — تسلسليٌّ أم بثّ

**التسلسليُّ ما كان**: واحدٌ في كلِّ مرّة، والدورُ محفوظ. **والبثُّ** يعرض على
دفعةٍ معاً وأولُ من يقبل يأخذ — أسرعُ استجابةً، **وأقسى على الكبتن** لأن أربعةً
يرون بطاقةً يفوز بها واحد.

**والقيمةُ الافتراضيّةُ تسلسليٌّ** — فالجدولُ الغائبُ لا يغيّر سلوكاً قائماً،
وهي قاعدةُ «الغيابُ لا يُفترض تفعيلاً» في هذا المشروع.

## ٢) `offer_timeout_seconds` — **٧ ثوانٍ بأمر المالك**

وكانت **٢٠**. **والرقمُ يخصّ النمطين معاً**: في البثِّ سبعٌ كافيةٌ لأن أربعةً
ينظرون، وفي التسلسليِّ **قصيرةٌ عمداً** — دورةُ خمسِ محاولاتٍ تكتمل في نحو ٣٥
ثانيةً بدل ١٠٠، فالراكبُ لا ينتظر دقيقتين ليُقال له «لا كبتن».

## ٣) `cooldown_seconds` — **٣٠، ولا استبعادَ دائمٍ بعد اليوم**

**كان المرفوضُ يُستبعد بقيّةَ الرحلة** (`tried: set` في الذاكرة). وقرارُ المالك:
**تبريدٌ قصيرٌ لا استبعاد**. **و٣٠ لا ١٢٠** بحجّته هو: ١٢٠ = مهلةُ الرحلة
كلِّها، **فلا يعود إليه في هذا الطلب أبداً — وذاك الاستبعادُ الدائمُ بعينه**.
و٣٠ تعيده حوالي المحاولة الرابعة أو الخامسة (٧ × ٥ ≈ ٣٥)، فيراه ثانيةً في
الطلب نفسِه **ولا يعود إليه فور رفضه**.

**والحدُّ الأدنى ثانيةٌ واحدة**: صفرٌ يعني «أعِد عليه فوراً» — دورةٌ مغلقةٌ
تعرض على الرافض نفسِه خمسَ مرّاتٍ في ثانية.

## ٤) `broadcast_batch_size` — سقفُ من يُبثُّ إليهم معاً

**بلا سقفٍ يصير البثُّ إشعاراً جماعيّاً** لكلِّ كبتنٍ في المدى: عشرون بطاقةً
لرحلةٍ واحدة، تسعةَ عشرَ منها تُطوى بلا سبب. **والأربعةُ افتراضاً** رقمٌ يُعدَّل
من اللوحة كبقيّته.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
MODE = postgresql.ENUM(
    "sequential", "broadcast", name="dispatch_mode", create_type=False
)


def upgrade() -> None:
    MODE.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "dispatch_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column("mode", MODE, nullable=False, server_default="sequential"),
        # **٧ بأمر المالك** — وكانت ٢٠ ثابتاً في الشيفرة
        sa.Column(
            "offer_timeout_seconds", sa.Integer(), nullable=False, server_default="7"
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "total_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        # **٣٠ بأمر المالك** — تبريدٌ لا استبعادٌ دائم
        sa.Column(
            "cooldown_seconds", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column(
            "broadcast_batch_size", sa.Integer(), nullable=False, server_default="4"
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
        sa.UniqueConstraint("country_code", name="dispatch_settings_country"),
        # **حدودٌ في القاعدة لا في الشاشة**: مهلةُ صفرٍ تعني بطاقةً تُطوى قبل
        # أن تُرى، وتبريدُ صفرٍ يعرض على الرافض نفسِه فوراً
        sa.CheckConstraint(
            "offer_timeout_seconds BETWEEN 3 AND 120",
            name="dispatch_offer_timeout_range",
        ),
        sa.CheckConstraint(
            "max_attempts BETWEEN 1 AND 50", name="dispatch_max_attempts_range"
        ),
        sa.CheckConstraint(
            "total_timeout_seconds BETWEEN 10 AND 900",
            name="dispatch_total_timeout_range",
        ),
        sa.CheckConstraint(
            "cooldown_seconds BETWEEN 1 AND 600", name="dispatch_cooldown_range"
        ),
        sa.CheckConstraint(
            "broadcast_batch_size BETWEEN 1 AND 20",
            name="dispatch_batch_size_range",
        ),
    )


def downgrade() -> None:
    op.drop_table("dispatch_settings")
    MODE.drop(op.get_bind(), checkfirst=True)
