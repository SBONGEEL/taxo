"""مخططات الأماكن المحفوظة (`FUTURE-FEATURES` بند 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# أيقوناتُ التصميم الثلاث. **محروسةٌ هنا لا في القاعدة** (`String(24)`) — نفس
# استثناء `feature_flags.feature_key`: أيقونةٌ رابعة تغييرُ كودٍ لا ترحيلة
PlaceIcon = Literal["home", "work", "star"]


class PlaceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=255)
    icon: PlaceIcon = "star"


class PlaceUpdate(BaseModel):
    """تعديلٌ جزئي — و`exclude_unset` في الراوتر هو ما يفرّق الغائب عن الفارغ."""

    label: str | None = Field(default=None, min_length=1, max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=255)
    icon: PlaceIcon | None = None


class PlaceOut(BaseModel):
    id: uuid.UUID
    label: str
    address: str | None
    lat: float
    lng: float
    icon: str
    created_at: datetime
