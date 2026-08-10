"""تقييم متبادل بعد الرحلة (SPEC القسم 4/5.9).

كل طرف يقيّم الآخر مرة واحدة لا أكثر — يفرضه القيد الفريد
`(ride_id, rater_type)` في القاعدة لا الخدمةُ وحدها، فسباقُ ضغطتين لا ينتج
تقييمين. والتقييم اختياري: رحلةٌ بلا تقييم رحلةٌ مكتملة.

`drivers.rating_avg` مشتق من هذا الجدول ويُعاد حسابه بعد كل تقييمٍ يكتبه راكب
(`services/ratings.py`) — عمودٌ محسوب لا مصدرٌ يُكتب فيه رقمٌ من عند نفسه.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import RatingRaterType

if TYPE_CHECKING:
    from app.models.ride import Ride
    from app.models.user import User


class Rating(UUIDMixin, TimestampMixin, Base):
    """تقييم طرفٍ لرحلة."""

    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("stars BETWEEN 1 AND 5", name="rating_stars_range"),
        UniqueConstraint("ride_id", "rater_type"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rater_type: Mapped[RatingRaterType] = mapped_column(
        pg_enum(RatingRaterType, "rating_rater_type"), nullable=False
    )
    # صاحب التقييم بعينه: `rater_type` يقول أيّ الطرفين، وهذا يقول أيّ حساب —
    # فيبقى السجل مقروءاً بعد أن يتغيّر إسناد الرحلة أو يُحذف ملف الكبتن
    rater_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    stars: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ride: Mapped["Ride"] = relationship("Ride", foreign_keys=[ride_id])
    rater: Mapped["User"] = relationship("User", foreign_keys=[rater_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Rating {self.rater_type} {self.stars}★>"
