"""سياسةُ الخصوصية وموافقاتُها وبيانُ الجهة — الترحيلة `0060`.

**النصُّ في القاعدة لا في الشيفرة** (قرارُ المالك 2026-08-29): **تعديلُ سياسةٍ
لا يكون نشراً**. ومن خبزها في حزمةٍ جعل تصحيحَ سطرٍ ينتظر بناءً ورفعاً — **وهي
نصٌّ قانونيٌّ يُقرأ من متجرٍ ومن مستخدم**.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class PrivacyPolicy(UUIDMixin, TimestampMixin, Base):
    """نسخةٌ من السياسة لسوقٍ بعينه.

    **والنسخةُ صفٌّ جديدٌ لا تحريرٌ فوق القديم**: من وافق على نسخةِ أمس **لم
    يوافق على نسخة اليوم**، فلا يجوز أن يُمحى النصُّ الذي وافق عليه —
    و`user_policy_consents.policy_id` مقيَّدٌ بـ`RESTRICT` يمنع ذلك في القاعدة
    لا في التطبيق.
    """

    __tablename__ = "privacy_policies"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    #: رقمٌ متصاعدٌ **لكلِّ سوقٍ على حدة** — يُعرض مع تاريخ النشر
    version: Mapped[int] = mapped_column(Integer, nullable=False)
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


class OrgProfile(UUIDMixin, TimestampMixin, Base):
    """بيانُ الجهة — **حقولٌ تُضبط من اللوحة ولا تُخبز**.

    **وصفٌّ واحدٌ لا صفٌّ لكلِّ سوق**: الجهةُ واحدةٌ وإن تعدّدت أسواقُها.
    **وتُترك فارغةً بلا سقوط** — الصفحةُ تعمل وتقول «لم تُضبط بعد».
    """

    __tablename__ = "org_profile"

    legal_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    privacy_email: Mapped[str | None] = mapped_column(String(160), nullable=True)
