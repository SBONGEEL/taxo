"""إشعاراتُ المالك كما تقرؤها اللوحة (SPEC §٨١) — **قيمٌ خامٌ وحدَها**: العنوانُ يُركَّب في اللوحة من الفهرس، والمبلغُ نصٌّ عشريٌّ كما في
كلِّ مالٍ يخرج من الخلفية. **وسطرُ الدرج** (`title`/`body`) معها لأنه ما رآه المالكُ على شاشة القفل، فتُطابقه القائمةُ حرفاً."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CountryCode, Currency


class AlertOut(BaseModel):
    id: uuid.UUID
    kind: str
    category: str
    tone: str
    country_code: CountryCode | None = None
    count: int
    amount: Decimal | None = None
    currency: Currency | None = None
    record_type: str | None = None
    record_id: str | None = None
    data: dict[str, Any]
    title: str
    body: str
    created_at: datetime
    last_event_at: datetime
    read: bool


class AlertPage(BaseModel):
    items: list[AlertOut]
    unread: int


class AlertSummary(BaseModel):
    unread: int
    latest: list[AlertOut]


class AlertReadIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    all: bool = False


class AlertReadOut(BaseModel):
    marked: int
    unread: int


class AlertTokenReadIn(BaseModel):
    user_id: uuid.UUID
    token: str = Field(min_length=8, max_length=80)


class AlertKindOut(BaseModel):
    kind: str
    category: str
    tone: str
    label: str
    plural: str


class AlertNamedOut(BaseModel):
    key: str
    label: str


class AlertCatalogOut(BaseModel):
    kinds: list[AlertKindOut]
    categories: list[AlertNamedOut]
    tones: list[AlertNamedOut]
    channels: list[str]


class AlertSettingsBody(BaseModel):
    #: `{kind: {"panel": bool, "web": bool, "phone": bool}}`
    kinds: dict[str, dict[str, bool]]
    #: `{tone: bool}`
    sounds: dict[str, bool]


class AlertTestIn(BaseModel):
    kind: str = Field(min_length=1, max_length=48)
    country_code: CountryCode = CountryCode.JO
    #: **عددٌ فوق الواحد يعاين الجمع** — «٣ طلبات رحلة»
    count: int = Field(default=1, ge=1, le=50)


class AlertSampleOut(BaseModel):
    kind: str
    category: str
    tone: str
    count: int
    title: str
    body: str


class AlertTestOut(BaseModel):
    title: str
    body: str
    web: int
    phone: int
    failed: int
