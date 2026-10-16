"""ملاحظةُ التطبيق كما يقرؤها المرسلُ واللوحة (SPEC §٧٦/٤)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FeedbackSentOut(BaseModel):
    """ما يعود للتطبيق — **إقرارٌ بالوصول لا أكثر**: لا يحتاج المرسلُ شيئاً آخرَ ليقول «وصلت، شكراً»."""

    id: uuid.UUID
    created_at: datetime


class AdminFeedbackOut(BaseModel):
    id: uuid.UUID
    #: **مَن أرسل** — الاسمُ والرقمُ يخرجان للّوحة وحدَها، كبلاغات الصور
    user_id: uuid.UUID | None = None
    #: **ملاحظةُ ضيف** (SPEC §٧٦-ن/٣) — بلا حسابٍ ولا اسمٍ ولا رقم، وتُرسم موسومةً «ضيف»
    is_guest: bool = False
    user_name: str | None = None
    user_phone: str | None = None
    #: **أيُّ تطبيق** — `rider` أو `driver`
    app: str
    message: str
    #: **أيُّ إصدار** — الغلافُ المثبَّت وحزمةُ الشاشات
    app_version: str | None = None
    web_build: str | None = None
    platform: str | None = None
    route: str | None = None
    has_screenshot: bool
    #: **متى**
    created_at: datetime
    handled_at: datetime | None = None


class AdminFeedbackPage(BaseModel):
    items: list[AdminFeedbackOut]
    total: int
    #: ما لم يُعالَج بعد — شارةُ القائمة
    new_count: int


class FeedbackHandledIn(BaseModel):
    handled: bool
