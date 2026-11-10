"""**عيّناتُ دقّة وقت الوصول** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢) — الترحيلة `0149`.

صفٌّ لكلِّ رحلةٍ وصل كبتنُها إلى الراكب وكان لها وقتُ اقترابٍ متوقَّع: **ما قاله المزوّد** (`raw_seconds`)، **وما عُرض بعد
التصحيح** (`shown_seconds`)، **وما وقع** (`actual_seconds`)، وساعةُ الدولة ويومُها لحظةَ التوقّع. **لا مالَ هنا ولا موضعَ أحد.**
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class EtaSample(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "eta_samples"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    raw_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    shown_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ساعةُ الدولة (٠–٢٣) ويومُها (٠ الاثنين … ٦ الأحد) لحظةَ التوقّع
    local_hour: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    local_dow: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (UniqueConstraint("ride_id", name="eta_samples_ride"),)
