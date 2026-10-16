"""مخططاتُ وضع الضيف (SPEC §٧٦-ن/أ)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GuestStartIn(BaseModel):
    app: Literal["rider", "driver"]
    #: معرّفُ التثبيت الذي يحمله التطبيقُ أصلاً (`lib/device.ts`) — **للحدِّ وحدَه، ويُجزَّأ قبل أن يُكتب**
    device_id: str = Field(min_length=8, max_length=128)


class GuestStartOut(BaseModel):
    guest_id: str
    #: رمزٌ من نوع `guest` — **لا يفتح إلا «أرسل ملاحظة»**
    token: str
    #: كم يبقى — ثلاثون يوماً ثمّ يُمحى كلُّ شيء
    retention_days: int


class GuestModeOut(BaseModel):
    rider: bool = False
    driver: bool = False


class GuestModeIn(BaseModel):
    rider: bool | None = None
    driver: bool | None = None
