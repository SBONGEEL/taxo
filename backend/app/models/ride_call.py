"""مكالمةُ الرحلة (SPEC §٦٦-ج، §٦٦-د/٣) — **سجلٌّ لا صوت**.

**يُحفظ**: الرحلة · من اتصل بمن · بدأت · رُدّ عليها · انتهت · المدّة · سببُ الانتهاء · **وهل سُجّلت**. **ولا صوت**: `recording_path`
فارغٌ ما دام التسجيلُ مطفأً في السوق — **وهو مطفأٌ افتراضاً، ولا يُشعله إلا المالكُ من اللوحة بعد نشر سطر خصوصيّته**.

**والسجلُّ يتبع مدّةَ المحادثة** (`service_settings.chat_retention_days`): من اتصل بمن ومتى أثرٌ من الرحلة نفسِها كرسائلها، **ومدّتان
لأثرٍ واحدٍ تفترقان بلا سبب** — والتسجيلُ وحدَه له مدّتُه (`call_recording_retention_days`) لأنه صوتُ إنسان لا سطرُ سجلّ.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import RatingRaterType, RideCallEndReason, RideCallStatus

#: **الحالاتُ الحيّة** — ومكالمةٌ حيّةٌ واحدةٌ لكلِّ رحلة يحرسها فهرسٌ فريدٌ جزئيٌّ من هذه القائمة نفسِها
LIVE_STATUSES: tuple[RideCallStatus, ...] = (RideCallStatus.RINGING, RideCallStatus.ACTIVE)


class RideCall(UUIDMixin, TimestampMixin, Base):
    """**مكالمةٌ واحدةٌ بين طرفَي رحلة** — حالُها `ringing ← active ← ended`، أو `ringing ← ended`.

    **وقيودُ القاعدة تقول ما لا يُكتب**: منتهيةٌ بلا وقتِ انتهاءٍ أو بلا سبب، وحيّةٌ بلا وقتِ ردّ، وتسجيلٌ لمكالمةٍ لم تُعلَن
    مسجَّلة. **و`caller_notice_at`/`callee_notice_at` هما «التنبيهُ يسبق دائماً» مكتوباً**: لا يُمرَّر عرضُ المتصل حتى يُقِرّ،
    ولا يُردّ على مكالمةٍ مسجَّلةٍ بلا إقرارِ المتصَل به — والخادمُ هو من يرفض لا الشاشة.
    """

    __tablename__ = "ride_calls"
    __table_args__ = (
        CheckConstraint(
            "(status = 'ended') = (ended_at IS NOT NULL AND end_reason IS NOT NULL)", name="ride_call_ended_complete"
        ),
        CheckConstraint(
            "status = 'ringing' OR answered_at IS NOT NULL OR status = 'ended'", name="ride_call_active_answered"
        ),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ride_call_duration_valid"),
        CheckConstraint("recording_path IS NULL OR recorded", name="ride_call_recording_only_when_recorded"),
        CheckConstraint(
            "caller_id IS NULL OR callee_id IS NULL OR caller_id <> callee_id", name="ride_call_two_parties"
        ),
        Index("ix_ride_calls_ride_id_started_at", "ride_id", "started_at"),
        # **مكالمةٌ حيّةٌ واحدةٌ لكلِّ رحلة** — والقفلُ على صفِّ الرحلة هو الحارسُ الأول، وهذا خلفه في القاعدة
        Index(
            "uq_ride_calls_live_ride",
            "ride_id",
            unique=True,
            postgresql_where=text("status IN ('ringing', 'active')"),
        ),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"), nullable=False)
    caller_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    callee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    #: **جانبُ المتصل في الرحلة** — والمتصَلُ به هو الجانبُ الآخر بالتعريف
    caller_role: Mapped[RatingRaterType] = mapped_column(pg_enum(RatingRaterType, "rating_rater_type"), nullable=False)
    status: Mapped[RideCallStatus] = mapped_column(
        pg_enum(RideCallStatus, "ride_call_status"),
        nullable=False,
        default=RideCallStatus.RINGING,
        server_default=text("'ringing'"),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: **من الردّ إلى الانتهاء** — وفارغةٌ لمكالمةٍ لم يُردّ عليها: «صفرُ ثانية» يُقرأ مكالمةً تمّت
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_reason: Mapped[RideCallEndReason | None] = mapped_column(
        pg_enum(RideCallEndReason, "ride_call_end_reason"), nullable=True
    )
    #: **مجمَّدٌ لحظةَ البدء** من إعداد السوق — إطفاؤه بعدها لا يجعل مكالمةً أُعلنت مسجَّلةً غيرَ مسجَّلة
    recorded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    caller_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    callee_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recording_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideCall {self.ride_id} {self.status}>"
