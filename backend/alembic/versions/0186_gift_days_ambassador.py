"""**«عدد أيام» و«سفير TAXO»** (أمرُ المالك ٢٠٢٦-١١-٢١ الخامس، البند ٣؛ SPEC §١١١-د/٤) — **إضافةٌ لا تمسّ صفّاً قائماً**.

* `custom_days`: **أيّامٌ يحدّدها المشرفُ بدل مدّة الخطّة** (١–٣٦٥) — فارغٌ لكلِّ صفٍّ قائمٍ وكلِّ شراءٍ عاديّ.
* `is_permanent`: **«سفير TAXO» صفُّ اشتراكٍ دائم** لا علمٌ على الكبتن — فكلُّ من يسأل «أمغطّى؟» يجده بلا تعديل.
  وافتراضُه `false`، فلا صفَّ قائمٌ يتغيّر معناه.
* **دائمٌ واحدٌ ساري لكلِّ كبتن** (فهرسٌ فريدٌ جزئيّ) — حارسُ القاعدة خلف قفل صفِّ الكبتن، فمنحان معاً لا يكتبان صفّين.
* **«شحن ببطاقة TAXO» في الدول الثلاث** (أمرُ المالك ٢٠٢٦-١١-٢١): طريقةُ «بطاقات TAXO» (`purchase_code`) **صفُّ إعدادٍ** يُضاف لكلِّ دولةٍ
  ليس لها طريقةُ بطاقاتٍ أصلاً — فالاستعمالُ يحتاجها (`payment_requests.provider_id` غيرُ فارغ). **والمفتاحُ `taxo_cards_enabled` مطفأٌ**
  إلا حيث كانت البطاقاتُ تعمل فعلاً قبله (الجزائر: نظامُ الدفع العامّ مشتعلٌ وطريقةُ بطاقاتٍ مفعَّلة) — فالحالُ تبقى كما هي، **ولا سوقَ
  يُفتح بالترحيلة**. والطريقةُ وحدَها لا تفتح شيئاً **ولا تُنشئ مالاً** — الرصيدُ من بطاقةٍ مطبوعةٍ اشتُريت وحدَها.
  **وصفُّ المفتاح يبقى في الرجوع**: نصٌّ في جدول إعدادٍ لا يقرؤه بنيانُ ما قبل الترحيلة.
* **ولا مالَ يتحرّك ولا صفَّ مالٍ يُكتب** بهذه الترحيلة. **والرجوعُ** يرفع الفهرسَ والقيدين والعمودين — ويُقاس في الاتّجاهين قبل الرفع.

Revision ID: 0186
Revises: 0185
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0186"
down_revision = "0185"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("driver_subscriptions", sa.Column("custom_days", sa.Integer(), nullable=True))
    op.add_column(
        "driver_subscriptions",
        sa.Column("is_permanent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "subscription_custom_days_range",
        "driver_subscriptions",
        "custom_days IS NULL OR (custom_days >= 1 AND custom_days <= 365)",
    )
    op.create_check_constraint(
        "subscription_permanent_no_days",
        "driver_subscriptions",
        "NOT is_permanent OR custom_days IS NULL",
    )
    op.create_index(
        "uq_driver_subscriptions_one_permanent",
        "driver_subscriptions",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text("is_permanent AND status = 'active'"),
    )
    # **طريقةُ «بطاقات TAXO» حيث لا طريقةَ بطاقاتٍ أصلاً** — ولا تمسّ طريقةً قائمة (الجزائر إن كانت لها).
    # والدولُ ثوابتُ مكتوبةٌ هنا لا مُدخَل — فتُكتب حرفيّةً كما في `0158` (الوسيطُ المربوطُ نصٌّ لا يُقبل في عمود تعداد)
    for country in ("JO", "DZ", "LY"):
        op.execute(
            sa.text(
                "INSERT INTO payment_providers (id, country_code, kind, code, name, enabled, for_topup, for_subscription, sort_order) "
                f"SELECT gen_random_uuid(), '{country}', 'purchase_code', :code, :name, true, true, false, 50 "
                f"WHERE NOT EXISTS (SELECT 1 FROM payment_providers WHERE country_code = '{country}' AND kind = 'purchase_code') "
                "ON CONFLICT (country_code, code) DO NOTHING"
            ).bindparams(code=AUTO_CODE, name="بطاقات TAXO")
        )
    # **حالُ الجزائر كما هي** — البطاقاتُ تعمل فيها اليوم بنظام الدفع العامّ وطريقةٍ مفعَّلة؛ والبابُ صار يسأل مفتاحَه وحدَه،
    # فيُكتب المفتاحُ مشتعلاً **حيث كانت تعمل فعلاً** لئلّا ينقطع الشحنُ بين الرفع وإشعاله من اللوحة. ولا سوقَ يُفتح بهذا
    op.execute(
        sa.text(
            "INSERT INTO feature_flags (id, country_code, feature_key, enabled) "
            "SELECT gen_random_uuid(), p.country_code, :flag, true FROM payment_providers p "
            "JOIN feature_flags g ON g.country_code = p.country_code AND g.feature_key = 'payment_requests_enabled' AND g.enabled "
            "WHERE p.kind = 'purchase_code' AND p.enabled AND p.code <> :code "
            "GROUP BY p.country_code "
            "ON CONFLICT (country_code, feature_key) DO NOTHING"
        ).bindparams(flag=CARDS_FLAG, code=AUTO_CODE)
    )


#: **علامةُ ما أضافته هذه الترحيلةُ وحدَه** — فالرجوعُ لا يمسّ طريقةً أنشأها مشرف
AUTO_CODE = "taxo_cards_auto"
CARDS_FLAG = "taxo_cards_enabled"


def downgrade() -> None:
    # ما لم يُستعمل وحدَه — طريقةٌ عليها طلبٌ (بطاقةٌ استُعملت) سجلُّ مالٍ لا يُمحى
    op.execute(
        sa.text(
            "DELETE FROM payment_providers WHERE code = :code AND kind = 'purchase_code' "
            "AND NOT EXISTS (SELECT 1 FROM payment_requests WHERE payment_requests.provider_id = payment_providers.id)"
        ).bindparams(code=AUTO_CODE)
    )
    op.drop_index("uq_driver_subscriptions_one_permanent", table_name="driver_subscriptions")
    op.drop_constraint(op.f("ck_driver_subscriptions_subscription_permanent_no_days"), "driver_subscriptions", type_="check")
    op.drop_constraint(op.f("ck_driver_subscriptions_subscription_custom_days_range"), "driver_subscriptions", type_="check")
    op.drop_column("driver_subscriptions", "is_permanent")
    op.drop_column("driver_subscriptions", "custom_days")
