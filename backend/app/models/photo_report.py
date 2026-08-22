"""بلاغُ كبتنٍ عن صورةِ راكب — **يحجب فوراً ويعرض على المشرف**.

**قرارُ المالك 2026-08-22**: صورةُ الراكب **بلا مراجعةٍ مسبقة** — الكبتنُ
يبحث عن راكبه في مكانٍ مزدحم، والانتظارُ يُفرغ الميزةَ من غرضها. **والثمنُ
المقبول** أن تُنشر صورةٌ مسيئةٌ أحياناً، **وعلاجُه بلاغٌ يحجب في الحال**.

**والحجبُ قبل القرار لا بعده**: من رأى صورةً مسيئةً لا يُطلب منه أن ينتظر
مشرفاً — **والضررُ يقع في الدقائق لا في الأيام**. والقرارُ اللاحقُ إمّا
إعادةٌ (بلاغٌ كاذب) أو حذفٌ.

**وبلاغٌ واحدٌ يكفي للحجب**: عتبةٌ عدديةٌ («ثلاثةُ بلاغات») تعني أن أوّلَ
مُبلِّغَين رأياها ولم يقع شيء — **وهي صورةٌ لا تصويت**.

**والصفُّ يبقى بعد القرار**: مُبلِّغٌ يبلّغ كذباً مراراً يُقرأ من صفوفه، ومن
حُذفت صورتُه ثم رفع مثلَها كذلك. **فالحذفُ يمسح الملفَّ لا الأثر.**
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserPhotoReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_photo_reports"
    __table_args__ = (
        # **بلاغٌ واحدٌ لكلِّ مُبلِّغٍ على كلِّ صورةٍ مفتوحة**: تكرارُ الضغط
        # لا يصير ثلاثةَ بلاغات، ولا يُقرأ إلحاحُ واحدٍ إجماعاً
        UniqueConstraint(
            "subject_id", "reported_by", "resolved_at", name="uq_photo_report_open"
        ),
    )

    #: صاحبُ الصورة
    subject_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: من بلّغ — **كبتنُ رحلةٍ لصاحبها**، لا أيُّ مستخدم
    reported_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    #: الرحلةُ التي رآها فيها — **المفتاحُ الذي أعطاه الحقَّ في رؤيتها**
    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    #: قرارُ المشرف: `removed` أو `restored` — و`NULL` معلَّق
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
