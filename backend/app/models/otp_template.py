"""قوالبُ رسالة رمز التحقق — **عالميةٌ لأن الرقمَ عالمي** (قرارُ المالك 2026-08-19).

عقدُ واتساب عالميٌّ ورقمٌ واحدٌ يخدم السوقين (SPEC القسم 8)، فالقالبُ **صفةُ
الرقم لا صفةُ السوق**: هو ما يقوله هذا الرقمُ لمن يراسله، لا ما يقوله سوقٌ
لمشتركيه. ولذلك لا عمودَ دولةٍ هنا — كـ`security_settings` سواءً بسواء.

**وشرطُ ما يبطل هذا الاختيار مكتوبٌ كي لا يُظنّ سهواً**: إن صار لكل سوقٍ رقمُه
أو عقدُه، فالقالبُ يتبعهما وتُعاد قراءةُ عالميّته. وحتى ذلك اليوم، عمودُ دولةٍ
«احتياطاً» عمودٌ يُدار بيدٍ بلا حاجةٍ قائمة — وهو ما رُفض في أولوية العروض.

**وصفٌّ لكل غرض، لا عمودان في صفٍّ واحد**: الحفظُ مستقلٌّ بنصِّه ومدقِّقه
ووقتِه، وغرضٌ ثالثٌ يُضاف صفّاً لا هجرةً.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OtpTemplatePurpose:
    """غرضُ الرسالة — **نصٌّ لا تعدادُ بوستجرس**.

    نفسُ استثناء `feature_flags.feature_key`: غرضٌ ثالثٌ يوماً ما يكون شيفرةً
    بلا هجرة، ولا قيمةَ لتعدادٍ يحرس عمودَ إعداداتٍ يكتبه المشرفُ من قائمةٍ
    مغلقةٍ في اللوحة أصلاً.
    """

    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"

    ALL = (REGISTRATION, PASSWORD_RESET)


class OtpMessageTemplate(Base):
    __tablename__ = "otp_message_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    purpose: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
