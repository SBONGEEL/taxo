"""إعداداتُ بثّ الموقع في اللوحة (SPEC §٧٥-ج) — ما يُكتب، وما يُرى حيّاً، وسجلُّ التغييرات."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BroadcastStep(BaseModel):
    """درجةٌ في جدول الطور الآليّ: «حتى هذا العدد من المتّصلين ⇒ هذا الفاصل»، **والأخيرةُ بلا حدّ**."""

    max_online: int | None = Field(default=None, ge=1)
    #: **حدّا المالك الصلبان** — ولو كُتب غيرُهما في الجدول
    seconds: int = Field(ge=15, le=45)


class BroadcastSettingsUpdate(BaseModel):
    mode: Literal["manual", "automatic"] | None = None
    available_seconds: int | None = Field(default=None, ge=15, le=45)
    heading_seconds: int | None = Field(default=None, ge=3, le=60)
    trip_send_seconds: int | None = Field(default=None, ge=3, le=60)
    trip_record_seconds: int | None = Field(default=None, ge=1, le=10)
    move_meters: int | None = Field(default=None, ge=5, le=500)
    heartbeat_seconds: int | None = Field(default=None, ge=15, le=120)
    auto_steps: list[BroadcastStep] | None = Field(default=None, min_length=1, max_length=8)

    @model_validator(mode="after")
    def _steps_ordered(self) -> "BroadcastSettingsUpdate":
        steps = self.auto_steps
        if steps is None:
            return self
        if steps[-1].max_online is not None:
            raise ValueError("الدرجةُ الأخيرةُ بلا حدّ — «فوق ذلك»")
        limits = [step.max_online for step in steps[:-1]]
        if any(limit is None for limit in limits):
            raise ValueError("كلُّ درجةٍ قبل الأخيرة لها حدّ")
        if any(b <= a for a, b in zip(limits, limits[1:], strict=False)):
            raise ValueError("حدودُ الدرجات تصاعديّة")
        return self


class BroadcastChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    source: str
    online_count: int
    old_seconds: int | None
    new_seconds: int


class BroadcastLiveOut(BaseModel):
    """**ما يعمل الآن** — من Redis لا من الصفّ: الطورُ والفاصلُ الفعّالُ والمهلةُ وعددُ المتّصلين ومتى قِيس."""

    mode: str
    available_seconds: int
    presence_ttl: int
    online: int | None = None
    checked_at: datetime | None = None
    changed_at: datetime | None = None


class BroadcastSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mode: str
    available_seconds: int
    heading_seconds: int
    trip_send_seconds: int
    trip_record_seconds: int
    move_meters: int
    heartbeat_seconds: int
    auto_steps: list[BroadcastStep]
    updated_at: datetime | None = None
    live: BroadcastLiveOut
    changes: list[BroadcastChangeOut]
