"""الأماكن المحفوظة للراكب (`FUTURE-FEATURES` بند 1).

«المنزل» و«العمل» وما يضيفه صاحب الحساب. ثلاثةُ قراراتٍ في هذا الجدول:

- **`label` فريدٌ لكل مستخدم**: «المنزل» مكانٌ واحد. ومنزلان بنفس الاسم يجعلان
  الاختصار على الرئيسية سؤالاً بدل أن يكون طريقاً.
- **`icon` نصٌّ محروسٌ في طبقة Pydantic لا `ENUM` في القاعدة** — نفس استثناء
  `feature_flags.feature_key` و`rides.cancel_reason_code`: أيقونةٌ جديدة
  تغييرُ كودٍ لا ترحيلة.
- **`ON DELETE CASCADE`** بخلاف الجداول المالية: هذا بيانُ راحةٍ لا سجلٌّ
  محاسبي، يذهب مع صاحبه كـ`device_tokens` و`saved_cards`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.ride import _latitude, _longitude, _point_column

# سقفُ ما يحفظه مستخدمٌ واحد. ثابتُ كودٍ لا إعداد: ليس رقماً تديره الإدارة
# ولا يختلف بين سوقين، وغرضُه منعُ قائمةٍ لا تُقرأ لا تحصيلُ مقابل
MAX_SAVED_PLACES = 12


class SavedPlace(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "saved_places"
    __table_args__ = (
        UniqueConstraint("user_id", "label", name="uq_saved_places_user_label"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    point: Mapped[str] = mapped_column(_point_column(), nullable=False)
    icon: Mapped[str] = mapped_column(String(24), nullable=False, server_default="star")

    lat: Mapped[float] = column_property(_latitude(point))
    lng: Mapped[float] = column_property(_longitude(point))

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SavedPlace {self.label}>"
