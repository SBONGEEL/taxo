from __future__ import annotations

import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CampaignAudience,
    CampaignStatus,
    CountryCode,
    DeliveryStatus,
)


class CampaignCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(min_length=2, max_length=500)
    audience: CampaignAudience
    country_code: CountryCode | None = None
    # بلا موعد تبقى مسودّة؛ بموعدٍ تصير مجدولة
    scheduled_at: datetime | None = None


class CampaignUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    body: str | None = Field(default=None, min_length=2, max_length=500)
    audience: CampaignAudience | None = None
    country_code: CountryCode | None = None
    scheduled_at: datetime | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    audience: CampaignAudience
    country_code: CountryCode | None
    status: CampaignStatus
    scheduled_at: datetime | None
    sent_at: datetime | None
    sent_count: int
    created_at: datetime


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: DeliveryStatus
    sent_at: datetime | None


class NotificationSettingOut(BaseModel):
    """ساعات الهدوء per-country — بتوقيت الدولة لا بـ UTC."""

    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    quiet_hours_start: time
    quiet_hours_end: time
    timezone: str


class NotificationSettingUpdate(BaseModel):
    # "HH:MM" — نصٌّ لا datetime: الساعة هنا وقتٌ في اليوم لا لحظةٌ في التقويم
    quiet_hours_start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
