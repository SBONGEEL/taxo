"""الشارات — **بيد المشرف، وبأثرها في الشاشة لا في التوزيع** (البند ٥٣، §٤).

**ولا تدخل الشاراتُ ترتيبَ التوزيع بحال.** المستوى مقيسٌ من عملٍ منجز، والشارةُ
تقديرٌ إنسانيٌّ — وجعلُ التقدير يزيد الطلباتِ يجعل المشرفَ **يوزّع المال بيده**.
وهذا هو الفرقُ الذي وُجد الجدولان لأجله؛ ولذلك لا عمودَ هنا يُقرأ في `dispatch`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Badge(UUIDMixin, TimestampMixin, Base):
    """كتالوجُ الشارات — تديره اللوحة، ولا يُشتق منه عدّاد."""

    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("key", name="uq_badges_key"),)

    key: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # اسمُ أيقونةٍ تعرفها الواجهة — **لا ملفَّ صورة**: كتالوجٌ من ستِّ شاراتٍ لا
    # يستحق مساراً للتخزين ولا منفذاً يخدم بايتات
    icon: Mapped[str | None] = mapped_column(String(48), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class DriverBadge(UUIDMixin, TimestampMixin, Base):
    """شارةٌ مُنحت لكبتن — **بسببٍ مكتوب**.

    و`note` هو استثناءُ «السببِ المكتوب» نفسُه الذي في تعليق الكبتن: قيدُ التدقيق
    لا يحمل القيمَ عادةً، وهذه قيمتُها **هي** الغرضُ من القيد.
    """

    __tablename__ = "driver_badges"
    __table_args__ = (
        UniqueConstraint("driver_id", "badge_id", name="uq_driver_badges"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("badges.id", ondelete="CASCADE"), nullable=False
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
