"""ساعاتُ العمل (SPEC §٦٢-ج/٣٧، §٦٤-ج) — **رقمٌ لا موقع**: دقائقُ يومٍ لكلِّ كبتن، ثمّ مجموعُ شهرٍ بعد ثلاثةَ عشرَ شهراً.

**مفتاحٌ مركّبٌ لا مُعرِّف**: صفٌّ واحدٌ لكلِّ (كبتن، يوم) تُرقّى دقائقُه ذرّياً (`ON CONFLICT`) — فلا صفّان ليومٍ واحدٍ يفترقان.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DriverActivityDay(Base):
    __tablename__ = "driver_activity_days"
    __table_args__ = (CheckConstraint("online_minutes BETWEEN 0 AND 1440", name="activity_day_minutes"),)

    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True)
    #: **يومُ السوق** لا يومُ الخادم — بمِنطقة `notification_settings` كأرقام «اليوم» كلِّها
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    online_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DriverActivityMonth(Base):
    __tablename__ = "driver_activity_months"
    __table_args__ = (CheckConstraint("online_minutes >= 0", name="activity_month_minutes"),)

    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True)
    #: أوّلُ الشهر
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    online_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
