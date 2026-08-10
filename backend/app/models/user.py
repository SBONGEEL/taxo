from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, UserRole

if TYPE_CHECKING:
    from app.models.driver import Driver


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # الهاتف هو مُعرّف الدخول — مخزّن بصيغة E.164
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.RIDER
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # تجميد المحفظة وحدها دون حظر الحساب (SPEC القسم 7/13.3): محفظة مشبوهة
    # تُوقَف حركتها بينما يبقى صاحبها قادراً على الركوب والدفع نقداً
    wallet_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # كلمة المرور هي طريقة الدخول **دائماً** (المرحلة 8-ب). تبقى nullable
    # لحساباتٍ أُنشئت قبل ذلك بـ OTP وحده، ولحسابٍ يُنشئه مسارٌ إداري ثم يضع
    # صاحبه كلمته — ولا يُفتح حسابٌ بلا كلمة مرور بكلمةٍ يخترعها أحد
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # لحظةُ إثبات ملكية الرقم (Firebase أو رمز SMS). **فارغة تعني رقماً غير
    # محقق**: يُنشأ الحساب هكذا فقط حين يُطفئ المشرف مفتاح
    # `otp_verification_enabled` للطوارئ، ويبقى موسوماً في اللوحة ويُطالَب
    # بالتحقق. ولا تُعتمد وثائق كبتنٍ قبل ملئها مهما كان المفتاح: رقمُ الكبتن
    # هو ما يستلم عليه حوالات كليك (SPEC القسم 6/9)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    # إشعارات الحملات التسويقية وحدها (المرحلة 8). **لا أثر له على
    # المعاملاتي**: أحداث الرحلة وعرض الطلب وتنبيه الاشتراك جزءٌ من الخدمة
    # لا إعلان، فمن أطفأ الإعلانات لم يطفئ «وصل الكبتن». مفتوحٌ افتراضياً
    # وإطفاؤه بيد صاحبه من التطبيق
    marketing_push_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    driver: Mapped["Driver | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<User {self.phone} ({self.role})>"
