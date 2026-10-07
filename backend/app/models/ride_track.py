"""رابطُ تتبّع رحلةٍ لشخصٍ آخر (§٦٣-ج/١، قرارُ المالك ٢٠٢٦-١٠-٠٧).

**الطالبُ يرسله بنفسه** بزرّ «شارك رابط التتبّع» — لا رسالةَ منّا: لا قناةَ واتساب معتمدة. **ومن يفتحه بلا دخولٍ يرى اسمَ
الكبتن وسيارتَه ولوحتَها وموقعَه** حتى تنتهي الرحلة، **ولا يرى رقمَ الطالب ولا محفظتَه**.

**والرمزُ هو الإذنُ كلُّه** — فهو عشوائيٌّ بـ١٢٨ بتاً (`secrets.token_urlsafe(16)`) لا معرّفُ الرحلة: معرّفٌ يُخمَّن أو يُرى في
سجلٍّ لا يصير رابطاً عامّاً. **ولا عمودَ انتهاءٍ** — حياتُه حياةُ الرحلة: يُقرأ حالُها لحظةَ الفتح، **ورحلةٌ انتهت = «انتهت
الرحلة» بلا كبتنٍ ولا موقع**. وعمودُ انتهاءٍ ثانٍ حقيقةٌ ثانيةٌ تفترق عن الأولى أوّلَ رحلةٍ تُلغى.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class RideTrackToken(UUIDMixin, TimestampMixin, Base):
    """رمزٌ واحدٌ لكلِّ رحلة — **فريدٌ في القاعدة**، فضغطتان معاً تعطيان الرابطَ نفسَه."""

    __tablename__ = "ride_track_tokens"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    token: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
