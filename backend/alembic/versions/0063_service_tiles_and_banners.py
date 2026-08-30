"""بلاطاتُ الخدمات ولافتاتُ المحتوى — **جدولان يُداران من اللوحة** (قرارُ المالك 2026-08-30).

## ولمَ لا تُخبز في الرسم

**«أريدها فعلاً وسأبنيها وسأزيد عليها»** — فبلاطةٌ مكتوبةٌ في الشيفرة تعني
**نشراً لكلِّ إضافة**، وثلاثةَ تطبيقاتٍ تُبنى لأجل صفٍّ جديد. **والقائمةُ
الحاليّةُ تنزل صفوفاً لا شيفرة.**

## ولمَ جدولان لا جدولٌ بنوعٍ مصرَّح

**البلاطةُ دائمةٌ بلا نافذة، واللافتةُ مؤقّتةٌ بنافذةٍ إلزاميّة** — **وجدولٌ
واحدٌ بنوعٍ مصرَّح يعني عموداً إلزاميّاً لصنفٍ واختياريّاً لآخر، وذاك يُقرأ
«إلزاميٌّ أحياناً» ولا يحرسه شيء** (قرارُ المالك، وهي حجّتُه).

**ومقصداهما مختلفان في النوع لا في القيمة**: البلاطةُ **تفتح خدمةً في
التطبيق**، واللافتةُ قد تفتح **رابطاً خارجيّاً أو لا شيء**.

## والحملاتُ ليست بيتاً لأيّهما — بخمسةِ فروقٍ مقروءةٍ من جدولها

الحملةُ **إرسالٌ** (`notification_deliveries` صفٌّ لكلِّ متلقٍّ، و`sent_count`)
واللافتةُ **سطحٌ لا يُرسل إلى أحد** · وعمرُها **لحظةٌ** (`sent_at`) لا نافذة ·
وحالُها **نهائيّة** (`sent`) · **ولا مقصدَ فيها ولا صورةَ ولا ترتيب** ·
**وساعاتُ الهدوء تحكمها** — ولافتةٌ لا «تصل الثالثةَ فجراً».

## والجمهورُ من مفرداتٍ قائمةٍ لا مخترعة

**`CampaignAudience` يكفي الثلاثة** — مقروءاً من `campaigns.py`:
`all_riders` ⇒ الركاب · `all_drivers` ⇒ الكباتن · **`by_country` ⇒ الاثنان**
(`has_role_clause(RIDER, DRIVER)`). **و`segment` تُرفض هنا كما تُرفض هناك.**

## و«جديد» ليست حالاً ثالثة

**هي فعّالةٌ بشارةٍ مؤقّتة** (قرارُ المالك): `status = active` و`new_until`
تاريخٌ تختفي الشارةُ بعده **بلا نشر**. **وحالٌ ثالثةٌ كانت ستحتاج شرطاً في كلِّ
موضعٍ يسأل «أتُفتح؟»**، والشارةُ لا تغيّر الجواب.

## و«فعّالة بلا مقصد» يمنعها البابُ بعلّته

**قيدُ القاعدة يمنع الفارغ** (`status='active'` ⇒ `destination IS NOT NULL`)،
**والبابُ يمنع ما ليس مبنيّاً**: `SERVICE_DESTINATIONS` قائمةٌ مصرَّحةٌ تقابل
مساراتٍ في التطبيقين. **والقاعدةُ لا تعرف مساراتِ React**، فالطبقتان لازمتان
ولا تغني إحداهما.

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

COUNTRY = postgresql.ENUM(name="country_code", create_type=False)
AUDIENCE = postgresql.ENUM(name="campaign_audience", create_type=False)
TILE_STATUS = postgresql.ENUM(
    "soon", "active", "hidden", name="service_tile_status", create_type=False
)
LINK_KIND = postgresql.ENUM(
    "internal", "external", "none", name="banner_link_kind", create_type=False
)


def upgrade() -> None:
    TILE_STATUS.create(op.get_bind(), checkfirst=True)
    LINK_KIND.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "service_tiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY, nullable=False),
        # **مفتاحٌ ثابتٌ يعرفه التطبيق** — والعنوانُ يتغيّر ولا يتغيّر هو
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=60), nullable=False),
        sa.Column("subtitle", sa.String(length=80), nullable=True),
        # اسمُ أيقونةِ lucide — والتطبيقان يستعملانها أصلاً
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column("audience", AUDIENCE, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("destination", sa.String(length=60), nullable=True),
        sa.Column("status", TILE_STATUS, nullable=False, server_default="hidden"),
        # **شارةُ «جديد» بمدّتها** — تختفي بانقضائها بلا نشر
        sa.Column("new_until", sa.Date(), nullable=True),
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
        sa.UniqueConstraint("country_code", "key", name="service_tile_key_per_market"),
        # **فعّالةٌ بلا مقصدٍ لا تُقبل** — والقاعدةُ تمنع الفارغ، والبابُ يمنع
        # ما ليس مبنيّاً. **و«قريباً» بلا مقصدٍ مقبولةٌ** لأنها لا تُنقر أصلاً.
        sa.CheckConstraint(
            "status <> 'active' OR destination IS NOT NULL",
            name="service_tile_active_needs_destination",
        ),
    )

    op.create_table(
        "promo_banners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country_code", COUNTRY, nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("body", sa.String(length=160), nullable=True),
        # صورةٌ تُرفع أو أيقونةُ lucide — **وإحداهما تكفي، ولا تلزمان**
        sa.Column("icon", sa.String(length=40), nullable=True),
        sa.Column("audience", AUDIENCE, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        # **`nullable=False` هو القرار**: «لافتةٌ بلا مدّةِ انتهاءٍ لا تُقبل»
        # — **وعمودٌ اختياريٌّ هنا يجعل لافتةَ عيدٍ تبقى إلى العيد القادم.**
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("link_kind", LINK_KIND, nullable=False, server_default="none"),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
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
        sa.CheckConstraint("ends_at > starts_at", name="promo_banner_window_forward"),
        # **مقصدٌ معلَنٌ يقابله عنوان** — و«لا شيء» لا يحتاج عنواناً
        sa.CheckConstraint(
            "link_kind = 'none' OR link IS NOT NULL",
            name="promo_banner_link_matches_kind",
        ),
    )
    # **ما يُقرأ في كلِّ فتحةِ شاشة**: الحيُّ في سوقٍ الآن
    op.create_index(
        "promo_banner_live", "promo_banners", ["country_code", "starts_at", "ends_at"]
    )


def downgrade() -> None:
    op.drop_index("promo_banner_live", table_name="promo_banners")
    op.drop_table("promo_banners")
    op.drop_table("service_tiles")
    LINK_KIND.drop(op.get_bind(), checkfirst=True)
    TILE_STATUS.drop(op.get_bind(), checkfirst=True)
