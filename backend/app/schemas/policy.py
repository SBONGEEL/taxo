"""حمولاتُ السياسات والشروط — **البند ١٠ (§39٫١٠، §34، §45)**.

**ولا حمولةَ تعديل**: كلُّ حفظٍ نسخةٌ جديدة، **ولا يُحرَّر صفٌّ فوق نفسه** —
والعقدُ يقول ذلك بغياب النموذج لا بتعليقٍ فيه.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, PolicyApp, PolicyDocType


class PolicyVersionIn(BaseModel):
    """نسخةٌ جديدة — **تولد مسوّدةً، والنشرُ فعلٌ ثانٍ**."""

    country_code: CountryCode
    doc_type: PolicyDocType
    app: PolicyApp
    body_ar: str = Field(min_length=1)
    #: **ولا تُترجم بحدس** — تبقى فارغةً حتى يُكتب نصٌّ إنجليزيٌّ بيد
    body_en: str | None = None
    #: **يقرّره الناشر**: تصحيحُ فاصلةٍ لا يُعيد سؤالَ الناس، **وتغييرٌ جوهريٌّ
    #: بلا إعادةِ سؤالٍ يجعل الموافقةَ القديمةَ دعوى**
    requires_reconsent: bool = False


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    doc_type: PolicyDocType
    app: PolicyApp
    version: int
    #: **أدنى نسخةٍ تُبرئ** — يكتبها بابُ الحفظ وحدَه (§34)
    min_accepted_version: int
    body_ar: str
    body_en: str | None
    requires_reconsent: bool
    is_published: bool
    published_at: datetime | None
    #: **عددُ من وافق على هذه النسخة** — يُحسب في الخلفية، **وهو ما يجعل
    #: زرَّ الحذف يُرسم معطَّلاً بعلّته** لا يُرسم ثمّ يرتدّ
    consents: int
    created_at: datetime


class OrgProfileIn(BaseModel):
    """بيانُ الجهة — **حقولٌ تُضبط ولا تُخبز**، وفراغُها حالٌ صحيحة."""

    legal_name: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=320)
    privacy_email: str | None = Field(default=None, max_length=160)


class OrgProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    legal_name: str | None
    address: str | None
    privacy_email: str | None
