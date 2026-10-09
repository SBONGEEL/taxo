"""عقدُ مكالمة الرحلة (SPEC §٦٦-ج) — **معرّفاتٌ وجوانبُ وأوقات، ولا رقمَ ولا صوتَ في شيءٍ منه**."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import RatingRaterType, RideCallEndReason, RideCallStatus

if TYPE_CHECKING:
    from app.models.ride_call import RideCall


class IceServerOut(BaseModel):
    """**مُرحِّلُنا ببياناتٍ مؤقّتة** — `RTCIceServer` كما يقبله المتصفّح. وقائمةٌ فارغةٌ حين لا مُرحِّل (التطوير)."""

    urls: list[str]
    username: str
    credential: str


class CallStartOut(BaseModel):
    call_id: uuid.UUID
    ride_id: uuid.UUID
    ice_servers: list[IceServerOut]
    #: **مسجَّلة؟** — وإن كانت: لا يُمرَّر عرضُك حتى تُقِرّ (`POST /calls/{id}/recording-notice`)
    recording: bool
    ring_timeout_seconds: int


class CallAnswerIn(BaseModel):
    #: **إقرارُ المتصَل به بتنبيه التسجيل** — شرطٌ للردّ على مكالمةٍ مسجَّلة، ولا أثرَ له في غيرها
    recording_notice_ack: bool = False


class CallAnswerOut(BaseModel):
    call_id: uuid.UUID
    ride_id: uuid.UUID
    ice_servers: list[IceServerOut]
    recording: bool


class CallSignalIn(BaseModel):
    """**إشارةُ WebRTC** يمرّرها الخادمُ إلى الطرف الآخر ولا يقرؤها — عرضٌ أو جوابٌ (SDP) أو مرشّحُ ICE."""

    kind: Literal["offer", "answer", "ice"]
    payload: dict[str, Any] = Field(default_factory=dict)


class RideCallOut(BaseModel):
    """حالُ مكالمةٍ لأحد طرفَيها — **و`mine` تقول هل هو المتصل**."""

    id: uuid.UUID
    ride_id: uuid.UUID
    status: RideCallStatus
    caller_role: RatingRaterType
    mine: bool
    recording: bool
    started_at: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    end_reason: RideCallEndReason | None = None

    @classmethod
    def of(cls, call: "RideCall", viewer_id: uuid.UUID) -> "RideCallOut":
        """**البانِي الواحد** — يخدم أبوابَ المكالمة كلَّها وسطرَها في المحادثة، فلا يملأ بابٌ حقلاً ينساه آخر."""
        return cls(
            id=call.id,
            ride_id=call.ride_id,
            status=call.status,
            caller_role=call.caller_role,
            mine=call.caller_id == viewer_id,
            recording=call.recorded,
            started_at=call.started_at,
            answered_at=call.answered_at,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds,
            end_reason=call.end_reason,
        )


class AdminCallOut(BaseModel):
    """**سجلُّ المكالمة للّوحة — بياناتٌ وصفيّةٌ وحدَها**: من اتصل بمن، ومتى، وكم، وكيف انتهت، وهل سُجّلت."""

    id: uuid.UUID
    caller_role: RatingRaterType
    caller_name: str | None = None
    callee_name: str | None = None
    status: RideCallStatus
    started_at: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    end_reason: RideCallEndReason | None = None
    recorded: bool
    #: **أثمّة ملفٌّ يُستمع إليه الآن** — والاستماعُ بابٌ بصلاحيته وتدقيقه لا هذا الحقل
    has_recording: bool
    recording_expires_at: datetime | None = None


class RecordingEraseIn(BaseModel):
    """**حذفُ تسجيلٍ قبل موعده — بسببٍ مكتوب** يُحفظ في سطر التدقيق (§٧١-ب/٧)."""

    reason: str = Field(min_length=8, max_length=300)
