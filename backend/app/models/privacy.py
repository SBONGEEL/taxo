"""سياسةُ الخصوصية وموافقاتُها وبيانُ الجهة — الترحيلة `0060`.

**النصُّ في القاعدة لا في الشيفرة** (قرارُ المالك 2026-08-29): **تعديلُ سياسةٍ
لا يكون نشراً**. ومن خبزها في حزمةٍ جعل تصحيحَ سطرٍ ينتظر بناءً ورفعاً — **وهي
نصٌّ قانونيٌّ يُقرأ من متجرٍ ومن مستخدم**.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, PolicyApp, PolicyDocType


class PrivacyPolicy(UUIDMixin, TimestampMixin, Base):
    """نسخةٌ من **وثيقةٍ قانونية** لسوقٍ وتطبيقٍ بعينهما (§34، الترحيلة `0068`).

    **والنسخةُ صفٌّ جديدٌ لا تحريرٌ فوق القديم**: من وافق على نسخةِ أمس **لم
    يوافق على نسخة اليوم**، فلا يجوز أن يُمحى النصُّ الذي وافق عليه —
    و`user_policy_consents.policy_id` مقيَّدٌ بـ`RESTRICT` يمنع ذلك في القاعدة
    لا في التطبيق.

    **والاسمُ `privacy_policies` أضيقُ ممّا صار يحمل** (`0068`): فيه الشروطُ
    أيضاً. **والمعنى يحمله `doc_type` لا الاسم** — وتغييرُ الاسم يُعيد كتابةَ
    §34 ونماذجَه ومفتاحَه الأجنبيَّ لِقارئٍ لا وجودَ له بعد، **ويبقى رخيصاً
    ما دامت الجداولُ فارغة**.
    """

    __tablename__ = "privacy_policies"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    #: **أيُّ وثيقة** — والمستخدمُ يوافق على زرّين لا زرٍّ واحد (§34)
    doc_type: Mapped[PolicyDocType] = mapped_column(
        pg_enum(PolicyDocType, "policy_doc_type"), nullable=False
    )
    #: **أيُّ تطبيق** — فما يخصّ الوثائقَ والمركبةَ لا يُعرض على راكب.
    #: **ولا قيمةَ للمشرف** بقرارٍ مكتوبٍ في `0068`.
    app: Mapped[PolicyApp] = mapped_column(
        pg_enum(PolicyApp, "policy_app"), nullable=False
    )
    #: رقمٌ متصاعدٌ **داخل (سوق + نوع + تطبيق)** — يُعرض مع تاريخ النشر
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: **أدنى نسخةٍ تُبرئ** — من وافق عليها أو على ما بعدها فقد وافق على ما
    #: يكفي، **فلا يُمشى رجوعاً في النسخ** ليُعرف ذلك (§34، وقاعدةُ §5-ج في
    #: العمود المحضَّر). **وكاتبُه واحدٌ مسمّى**: بابُ النشر عند كلِّ حفظ —
    #: `requires_reconsent` ? نسخةُ الصفِّ نفسِه : قيمةُ المنشورةِ التي قبله.
    min_accepted_version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_ar: Mapped[str] = mapped_column(Text, nullable=False)
    #: **ولا تُترجم بحدس**: تبقى فارغةً حتى يُكتب نصٌّ إنجليزيّ بيد
    body_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: **يقرّره الناشرُ عند الحفظ** — تصحيحُ فاصلةٍ لا يُعيد سؤالَ الناس،
    #: وتغييرٌ جوهريٌّ بلا إعادةِ سؤالٍ يجعل الموافقةَ القديمةَ دعوى.
    requires_reconsent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    #: **المنشورةُ واحدةٌ لكلِّ سوق** — يحرسه فهرسٌ جزئيٌّ فريد
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # **كانت في الترحيلة `0060` ولم تكن هنا** (صُحِّح 2026-08-30) — والفرقُ
    # يُقرأ انحرافاً في `test_migrations_match_models`.
    __table_args__ = (
        # **الرقمُ يتصاعد داخل الثلاثيّة لا داخل السوق** (`0068`): بلا هذا
        # تتصادم «خصوصيةُ الراكب v1» مع «شروطُ الكبتن v1» في السوق نفسِه
        UniqueConstraint(
            "country_code", "doc_type", "app", "version",
            name="privacy_policy_version",
        ),
        # **منشورةٌ واحدةٌ لكلِّ (سوق + نوع + تطبيق)** — وهذا الفهرسُ **هو
        # جوابُ «أيُّ نسخةٍ واجبةٌ الآن»** لا وسيلةٌ إليه: فلا يُحسب
        # `MAX(version)` ولا يُفترض أن أحدثَ رقمٍ هو المنشور. وكان على السوق
        # وحدَه، **فنشرُ الشروط كان يُطفئ الخصوصيةَ في السوق نفسِه صامتاً**.
        Index(
            "privacy_policy_one_published",
            "country_code",
            "doc_type",
            "app",
            unique=True,
            postgresql_where=text("is_published"),
        ),
    )


class UserPolicyConsent(UUIDMixin, TimestampMixin, Base):
    """**أيَّ نسخةٍ قبِل هذا المستخدم ومتى** — فلا يُسأل بلا جواب."""

    __tablename__ = "user_policy_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("privacy_policies.id", ondelete="RESTRICT"), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # **وهو مفتاحُ «مستخدم + نوع + تطبيق + نسخة» نفسُه** (قرارُ المالك
    # 2026-09-02): `policy_id` يحلّ إلى (سوق + نوع + تطبيق + نسخة) بقيد
    # `privacy_policy_version` — **فمفتاحٌ أجنبيٌّ واحدٌ لا أربعةُ أعمدةٍ
    # منسوخة**، وأربعةٌ منسوخةٌ تفترق عن أصلها أوّلَ تحرير.
    __table_args__ = (
        UniqueConstraint("user_id", "policy_id", name="user_policy_consent_once"),
    )


class OrgProfile(UUIDMixin, TimestampMixin, Base):
    """بيانُ الجهة — **حقولٌ تُضبط من اللوحة ولا تُخبز**.

    **وصفٌّ واحدٌ لا صفٌّ لكلِّ سوق**: الجهةُ واحدةٌ وإن تعدّدت أسواقُها.
    **وتُترك فارغةً بلا سقوط** — الصفحةُ تعمل وتقول «لم تُضبط بعد».
    """

    __tablename__ = "org_profile"

    legal_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    privacy_email: Mapped[str | None] = mapped_column(String(160), nullable=True)
