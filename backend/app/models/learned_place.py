"""**أماكنُ تعلّمتها الرحلات** (قرارُ المالك ٢٠٢٦-١١-١٥) — ما كتبه الركّابُ في البحث، وأين انتهت رحلاتُهم فعلاً.

**الاسمُ نصُّ الراكب لا نصُّ Google** (لا يُحفظ من Places نصٌّ دائماً)، **والموقعُ نهايةُ رحلةٍ مكتملة** — بياناتُنا. ولا يظهر في البحث
إلا ما أكّدته **رحلتان على الأقلّ** في **آخر ٣٠ يوماً** — فخطأُ راكبٍ واحدٍ لا يصير مكاناً للجميع. **ولا جدولَ مالٍ هنا ولا صلةَ بمال.**
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class LearnedPlace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learned_places"
    __table_args__ = (
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="learned_place_point_valid"),
        CheckConstraint("char_length(btrim(label)) >= 2", name="learned_place_label_present"),
        #: **خليّةٌ بثلاث منازل** (~١١٠ م) — الاسمُ نفسُه في الخليّة نفسِها صفٌّ واحدٌ يُعدّ
        UniqueConstraint("country_code", "label_norm", "cell", name="uq_learned_places_label_cell"),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    label_norm: Mapped[str] = mapped_column(String(80), nullable=False)
    cell: Mapped[str] = mapped_column(String(24), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    trips: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
