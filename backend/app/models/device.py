"""رموز أجهزة الإشعارات (SPEC القسم 4/10 — المرحلة 8).

جدولٌ **أضافته المرحلة 8** ولم يكن في القسم 4: إشعارُ Push لا يُرسل إلى
مستخدم بل إلى **جهاز**، ورمزُ الجهاز يصدره FCM على الجهاز نفسه فلا سبيل
لمعرفته إلا أن يرسله التطبيق ويُحفظ. ولا مكان له في الجداول القائمة: عمودٌ
على `users` يفترض جهازاً واحداً لحسابٍ قد يكون على هاتفٍ ولوحٍ ومتصفح معاً.

ثلاث قواعد يحملها المخطط نفسه:

- **`token` فريد على مستوى الجدول كله.** رمز FCM يعرّف تثبيتَ تطبيقٍ واحد؛
  فإن سجّل الدخول عليه حسابٌ آخر انتقل الصفُّ إليه ولا يبقى للأول — وإلا وصل
  إشعارُ الحساب السابق إلى من يحمل الهاتف الآن.
- **`(user_id, device_id)` فريد.** الرمز يدور من تلقاء FCM، فالجهاز الواحد
  صفٌّ واحد يُحدَّث لا صفوفٌ تتراكم لرموزٍ ماتت.
- **`ON DELETE CASCADE` بخلاف الجداول المالية.** الرمز بيانُ توصيلٍ لا سجلٌّ
  محاسبي — نفس منطق `saved_cards`، ولا معنى له بعد ذهاب صاحبه.

و`device_id` هو نفسه ما يرسله المقبس في `?device_id=`، فتُعرف أيُّ الأجهزة
مفتوحٌ الآن ولا يُرسل إليه Push مكرِّراً لما وصله عبر WebSocket (القسم 10).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import DevicePlatform


class DeviceToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_tokens_token"),
        UniqueConstraint("user_id", "device_id", name="uq_device_tokens_user_device"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # مُعرّف ثابت يولّده التطبيق ويبقى مع تثبيته — به تُطابق الأجهزة المفتوحة
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # رمز التسجيل لدى FCM. طويل ويدور، ولا يُعرض لأحد: ليس سرّاً يُدفع به لكنه
    # يسمح بإرسال إشعارٍ باسمنا إلى جهاز مستخدم
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[DevicePlatform] = mapped_column(
        pg_enum(DevicePlatform, "device_platform"), nullable=False
    )
    # آخر تسجيلٍ للرمز — عليه يُبنى تنظيف الأجهزة المهجورة لاحقاً
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # يُطفأ حين يردّ FCM «هذا الرمز لم يعد مسجَّلاً» — **تعطيلٌ لا حذف**:
    # الصفُّ يبقى فيعرف نفس الجهاز عند إعادة التسجيل، ولا يُعاد الإرسال إليه
    # في كل حملة ليفشل في كل مرة
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DeviceToken {self.platform} {self.device_id}>"
