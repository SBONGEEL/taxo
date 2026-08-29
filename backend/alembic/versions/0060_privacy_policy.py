"""سياسةُ الخصوصية — نصٌّ في القاعدة، ونسخةٌ مؤرَّخة، وموافقةٌ تُسجَّل.

## ١) `privacy_policies` — **النصُّ يُعدَّل من اللوحة، فتعديلُ سياسةٍ لا يكون نشراً**

**ولمَ لكلِّ سوقٍ صفٌّ** (قرارُ المالك 2026-08-29): **القانونُ يفترق بين
الأردن وليبيا**، وبيتُ الإعدادات في هذا المشروع لكلِّ دولةٍ أصلاً
(`payment_settings` · `notification_settings`). **ويُنسخ نصُّ الأردن إلى ليبيا
يومَ تُفتح** بدل أن يُخترع.

**والنسخةُ صفٌّ جديدٌ لا تحريرٌ فوق القديم**: من وافق على نسخةِ أمس **لم يوافق
على نسخة اليوم**، **وذاك يُقرأ لا يُخمَّن** — فلا يجوز أن يُمحى النصُّ الذي
وافق عليه.

**و`requires_reconsent` يقرّره الناشرُ عند الحفظ** (قرارُ المالك): **وبلاه يصير
تصحيحُ فاصلةٍ إزعاجاً لكلِّ مستخدم** — وتغييرٌ جوهريٌّ بلا إعادةِ سؤالٍ يجعل
الموافقةَ القديمةَ دعوى.

## ٢) `user_policy_consents` — **أيَّ نسخةٍ قبِل، ومتى**

**فلا يُسأل «متى وافق وعلى ماذا» بلا جواب.** والمفتاحُ الفريدُ
(`user_id`+`policy_id`) يمنع صفَّين لموافقةٍ واحدة.

## ٣) `org_profile` — **بيانُ الجهة، حقولٌ لا تُخبز**

**صفٌّ واحدٌ لا صفٌّ لكلِّ سوق**: الجهةُ واحدةٌ وإن تعدّدت أسواقُها.
**وتُترك فارغةً بلا سقوط**: الصفحةُ تعمل وتقول «لم تُضبط بعد» — **فغيابُ
بيانٍ إداريٍّ لا يُسقط صفحةً قانونيةً يقرؤها المتجر**.

Revision ID: 0060
Revises: 0059
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

COUNTRY = postgresql.ENUM(name="country_code", create_type=False)


def upgrade() -> None:
    op.create_table(
        "privacy_policies",
        # **بلا `server_default`** (صُحِّح 2026-08-30): `UUIDMixin` يولّد
        # المفتاحَ في بايثون، وافتراضٌ في القاعدة بلا مقابلٍ في النموذج
        # **يُقرأ انحرافاً** ويُسقط `test_migrations_match_models`.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY, nullable=False),
        # **رقمٌ متصاعدٌ لكلِّ سوق** — يُقرأ في الشاشة مع تاريخه
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body_ar", sa.Text(), nullable=False),
        # **ولا تُترجم بحدس** (قرارُ المالك): تبقى فارغةً حتى يُكتب نصٌّ إنجليزيّ
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column(
            "requires_reconsent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # **المنشورةُ واحدةٌ لكلِّ سوق** — والباقياتُ تاريخٌ يُقرأ ولا يُعرض
        sa.Column(
            "is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "published_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.UniqueConstraint("country_code", "version", name="privacy_policy_version"),
    )
    # **منشورةٌ واحدةٌ لكلِّ سوق** — يحرسه فهرسٌ جزئيٌّ لا شرطُ تطبيق
    op.create_index(
        "privacy_policy_one_published",
        "privacy_policies",
        ["country_code"],
        unique=True,
        postgresql_where=sa.text("is_published"),
    )

    op.create_table(
        "user_policy_consents",
        # **بلا `server_default`** (صُحِّح 2026-08-30): `UUIDMixin` يولّد
        # المفتاحَ في بايثون، وافتراضٌ في القاعدة بلا مقابلٍ في النموذج
        # **يُقرأ انحرافاً** ويُسقط `test_migrations_match_models`.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            # **لا حذفَ لنسخةٍ وافق عليها أحد** — `RESTRICT` تمنع محوَ الشاهد
            sa.ForeignKey("privacy_policies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.UniqueConstraint("user_id", "policy_id", name="user_policy_consent_once"),
    )

    op.create_table(
        "org_profile",
        # **بلا `server_default`** (صُحِّح 2026-08-30): `UUIDMixin` يولّد
        # المفتاحَ في بايثون، وافتراضٌ في القاعدة بلا مقابلٍ في النموذج
        # **يُقرأ انحرافاً** ويُسقط `test_migrations_match_models`.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(length=160), nullable=True),
        sa.Column("address", sa.String(length=320), nullable=True),
        sa.Column("privacy_email", sa.String(length=160), nullable=True),
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
    )


def downgrade() -> None:
    op.drop_table("org_profile")
    op.drop_table("user_policy_consents")
    op.drop_index("privacy_policy_one_published", table_name="privacy_policies")
    op.drop_table("privacy_policies")
