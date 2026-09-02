"""نواقصُ §34 الثلاثة — **تُسدُّ في الشكل قبل أن يُبنى عليه** (قرارُ المالك 2026-09-02).

`0060` أنشأت الجداولَ الثلاثة **ولم يُبنَ عليها شيءٌ بعد**: صفرُ خدمةٍ وصفرُ
بابٍ وصفرُ قارئ. **فهذه الترحيلةُ تُصلح الشكلَ لا تُرمّم بيانات** — وهو الفرقُ
الذي جعلها ممكنةً اليوم ومستحيلةً بعد أوّل نصٍّ يوافق عليه إنسان.

## ١) عمودٌ يفرّق الوثيقتين — `doc_type`

**المستخدمُ يوافق على زرّين لا زرٍّ واحد** (قرارُ المالك): «سياسةُ الخصوصية»
و«شروطُ الاستخدام» وثيقتان مستقلّتان، **لكلٍّ نسخُها وموافقتُها**. والفهرسُ
الجزئيُّ في `0060` كان يفرض **منشورةً واحدةً لكلِّ سوق** — أي أن نشرَ الشروط
كان **يُطفئ** سياسةَ الخصوصية في السوق نفسِه، صامتاً، بقيدٍ في القاعدة.

## ٢) عمودٌ يفرّق التطبيقات — `app`

**ما يخصّ الوثائقَ والمركبةَ لا يُعرض على راكب**: نصُّ الكبتن يذكر رفعَ رخصةٍ
وبياناتِ مركبةٍ وحسابَ صرف، ولا شيءَ من ذلك يخصّ راكباً — **ونصٌّ واحدٌ
للاثنين إمّا يَعِد الراكبَ بما لا يقع أو يسكت عمّا يلزم الكبتن**.

**ولا قيمةَ للمشرف** (رأيٌ عرضتُه وأقرّه المالك 2026-09-02): اللوحةُ علاقةُ
عملٍ لا استهلاك، **ولا شاشةَ قبولٍ فيها**. وقيمةٌ في التعداد بلا سطحٍ ينشرها
**«بابٌ بلا زرّ» في القاعدة**. وإضافتُها يومَ يلزم `ALTER TYPE … ADD VALUE`
وهو نمطٌ مكتوبٌ في هذا المستودع (`0009` و`0018`).

## ٣) «أيُّ نسخةٍ يلزم قبولُها الآن» — صريحةٌ لا محسوبة

**والصفُّ الواجبُ يُعرَّف بنصِّ المالك**: «أحدثُ منشورٍ لكلِّ (نوع + تطبيق +
سوق)». **فيصير الفهرسُ الجزئيُّ هو الجوابَ نفسَه** لا وسيلةً إليه: منشورةٌ
واحدةٌ لكلِّ ثلاثيّةٍ بقيدٍ في القاعدة، **فلا يُحسب `MAX(version)` ولا يُقرأ
أحدثُ رقمٍ ويُفترض أنه المنشور**.

**ومعه `min_accepted_version` — «أدنى نسخةٍ تُبرئ»**، وبلاه يبقى نصفُ الجواب
محسوباً: `requires_reconsent` تقول «تُسأل ثانيةً»، **والسؤالُ الحقيقيُّ «أوافق
هذا الشخصُ على ما يكفي؟»** — وجوابُه بلا عمودٍ يعني **المشيَ رجوعاً في
النسخ** حتى تُوجد آخرُ نسخةٍ طلبت الموافقةَ ثانيةً، وهو حسبةٌ على تاريخٍ يطول.

**والعمودُ يُكتب مرّةً ويُقرأ كثيراً** كما يقول §5-ج حرفاً، **وثمنُه مكتوبٌ
هناك أيضاً**: «فكلُّ عمودٍ محضَّرٍ يُسمّى مَن يكتبه ومتى، ويُختبر أنّ كلَّ
كاتبٍ يُحدِّثه». **فكاتبُه واحدٌ ومسمّى**: بابُ النشر (البند ١٠) عند كلِّ حفظ —
`requires_reconsent` ? نسخةُ الصفِّ نفسِه : قيمةُ المنشورةِ التي قبله.

## وما لم يُغيَّر، بعلّته

**اسمُ الجدول `privacy_policies` يبقى** وإن صار يحمل الشروطَ أيضاً: تغييرُه
يُعيد كتابةَ نصِّ §34 نفسِه وأسماءَ نماذجِه ومفتاحَه الأجنبيَّ **لِقارئٍ لا
وجودَ له بعد** — **والمعنى يحمله `doc_type` لا الاسم**. وهو قرارٌ يبقى رخيصاً
ما دامت الجداولُ فارغة.

**والمفتاحُ الفريدُ للموافقة يبقى `(user_id, policy_id)`** — **وهو مفتاحُ
المالك نفسُه لا غيرُه**: `policy_id` يحلّ إلى (سوق + نوع + تطبيق + نسخة) بقيدِ
`privacy_policy_version` أدناه، **فالكتابةُ به مفتاحٌ أجنبيٌّ واحدٌ لا أربعةُ
أعمدةٍ منسوخة** — وأربعةٌ منسوخةٌ تفترق عن أصلها أوّلَ تحرير.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

DOC_TYPE = postgresql.ENUM(
    "privacy_policy", "terms_of_use", name="policy_doc_type", create_type=False
)
POLICY_APP = postgresql.ENUM("rider", "driver", name="policy_app", create_type=False)


def _refuse_if_anything_was_written() -> None:
    """**تعدّ الصفوفَ ساعةَ التشغيل وتقف بصياحٍ مسمّى** (قرارُ المالك 2026-09-02).

    **العلّةُ بنصِّه**: «لا تفترض ذلك في الترحيلة نفسها — فتقيس على الإنتاج
    ساعةَ الترقية بدل أن نقيس اليوم بمفتاحٍ لا يعمل».

    **وهي ليست احتياطاً زائداً**: العمودان يُضافان `NOT NULL` **بلا افتراض**،
    فصفٌّ قائمٌ إمّا يُسقط الترحيلةَ برسالةِ Postgres («column contains null
    values») **وهي رسالةٌ لا تقول ما العمل**، وإمّا — لو أُعطي افتراضاً —
    **يُوسَم صامتاً** بأنه «سياسةُ خصوصيةٍ للراكب» وهو قد لا يكون كذلك.
    **ووسمٌ صامتٌ على نصٍّ قانونيٍّ أسوأُ من وقوف.**

    **والوقوفُ هنا يوقف الترقيةَ كلَّها** — وهو المقصود: البوّابةُ الرابعة
    تقول «يُوقَف عندها ولا يُكمَل ولا يُصلَح على الإنتاج».
    """
    bind = op.get_bind()
    policies = bind.execute(
        sa.text("SELECT count(*) FROM privacy_policies")
    ).scalar_one()
    consents = bind.execute(
        sa.text("SELECT count(*) FROM user_policy_consents")
    ).scalar_one()
    if policies or consents:
        raise RuntimeError(
            "0068 توقّفت: الجداولُ ليست فارغة "
            f"(privacy_policies={policies} · user_policy_consents={consents}). "
            "وهذه الترحيلةُ تُصلح شكلاً لم يُكتب فيه شيءٌ قطّ — "
            "فصفٌّ قائمٌ يعني أن أحداً كتب نصّاً قانونياً بيده، "
            "و«نوعُه» و«تطبيقُه» لا يُخمَّنان له. "
            "يُعرض ما فيها على المالك ويُقرَّر وسمُ كلِّ صفّ، ثمّ تُكتب ترحيلةٌ "
            "تحمل ذلك القرار — ولا تُوسَم صفوفٌ بافتراضٍ في هذه."
        )


def upgrade() -> None:
    _refuse_if_anything_was_written()

    DOC_TYPE.create(op.get_bind(), checkfirst=True)
    POLICY_APP.create(op.get_bind(), checkfirst=True)

    # **بلا `server_default`، والجدولُ فارغٌ مقيسٌ أعلاه**: افتراضٌ هنا يعني
    # أن أوّلَ صفٍّ يُكتب بعد اليوم بلا نوعٍ **يصير «سياسةَ خصوصيةٍ للراكب»
    # بلا أن يقول أحدٌ ذلك** — والبابُ يجب أن يُصرِّح بالاثنين.
    op.add_column("privacy_policies", sa.Column("doc_type", DOC_TYPE, nullable=False))
    op.add_column("privacy_policies", sa.Column("app", POLICY_APP, nullable=False))
    # **أدنى نسخةٍ تُبرئ** — يكتبها بابُ النشر وحدَه (§34)
    op.add_column(
        "privacy_policies",
        sa.Column("min_accepted_version", sa.Integer(), nullable=False),
    )

    # **الرقمُ يتصاعد داخل الثلاثيّة لا داخل السوق**: بلا هذا تتصادم
    # «خصوصيةُ الراكب v1» مع «شروطُ الكبتن v1» في السوق نفسِه
    op.drop_constraint(
        "privacy_policy_version", "privacy_policies", type_="unique"
    )
    op.create_unique_constraint(
        "privacy_policy_version",
        "privacy_policies",
        ["country_code", "doc_type", "app", "version"],
    )

    # **والفهرسُ الجزئيُّ هو جوابُ «أيُّ نسخةٍ واجبةٌ الآن»**: منشورةٌ واحدةٌ
    # لكلِّ (سوق + نوع + تطبيق). وكان على السوق وحدَه — **فنشرُ الشروط كان
    # يمنع نشرَ الخصوصية** في السوق نفسِه.
    op.drop_index("privacy_policy_one_published", table_name="privacy_policies")
    op.create_index(
        "privacy_policy_one_published",
        "privacy_policies",
        ["country_code", "doc_type", "app"],
        unique=True,
        postgresql_where=sa.text("is_published"),
    )


def downgrade() -> None:
    op.drop_index("privacy_policy_one_published", table_name="privacy_policies")
    op.create_index(
        "privacy_policy_one_published",
        "privacy_policies",
        ["country_code"],
        unique=True,
        postgresql_where=sa.text("is_published"),
    )
    op.drop_constraint(
        "privacy_policy_version", "privacy_policies", type_="unique"
    )
    op.create_unique_constraint(
        "privacy_policy_version", "privacy_policies", ["country_code", "version"]
    )
    op.drop_column("privacy_policies", "min_accepted_version")
    op.drop_column("privacy_policies", "app")
    op.drop_column("privacy_policies", "doc_type")
    # **والنوعُ يُحذف مع من أنشأه** — وإلا فشلت إعادةُ الترقية بـ«type already
    # exists»، وهي القاعدةُ المكتوبة في `COMMANDS.md`
    POLICY_APP.drop(op.get_bind(), checkfirst=True)
    DOC_TYPE.drop(op.get_bind(), checkfirst=True)
