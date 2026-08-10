from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DevicePlatform


class DeviceRegisterRequest(BaseModel):
    """تسجيل جهازٍ لإشعارات Push — يُستدعى بعد الدخول وعند تجدّد الرمز."""

    device_id: str = Field(min_length=4, max_length=64)
    token: str = Field(min_length=8, max_length=512)
    platform: DevicePlatform


class DeviceOut(BaseModel):
    """بيانُ جهازٍ لصاحبه — **بلا الرمز**.

    الرمز يسمح بإرسال إشعارٍ باسم المنصة إلى هذا الجهاز، فلا يخرج من الخلفية
    كما لا يخرج `saved_cards.provider_token` (SPEC القسم 4).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: str
    platform: DevicePlatform
    is_active: bool
    last_seen_at: datetime


class NotificationPreferencesOut(BaseModel):
    """تفضيلات الإشعارات — مفتاحٌ واحد اليوم.

    المعاملاتي غير مذكور هنا عمداً: ليس تفضيلاً بل جزءٌ من الخدمة.
    """

    marketing_push_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    marketing_push_enabled: bool
