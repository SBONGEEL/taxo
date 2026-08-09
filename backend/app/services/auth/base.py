from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest

AuthMethod = Literal["password", "otp"]


class AuthStrategy(ABC):
    """واجهة موحّدة للمصادقة.

    الاستراتيجية الفعّالة تُختار وقت التشغيل (`get_auth_strategy`):
    - `PasswordAuthStrategy` ما دام لا يوجد مزود SMS مفعّل.
    - `OtpAuthStrategy` تلقائياً بمجرد تفعيل مزود SMS من صفحة العقود.

    الراوترات والواجهات تتعامل مع هذه الواجهة فقط، فلا يتغير أي endpoint
    عند التبديل — يتغير معنى الحقل `credential` من كلمة مرور إلى رمز OTP.
    """

    method: AuthMethod

    @abstractmethod
    def describe(self) -> AuthMethodResponse:
        """وصف طريقة الدخول الحالية للواجهات."""

    @abstractmethod
    async def register(self, session: AsyncSession, data: RegisterRequest) -> User:
        """إنشاء حساب جديد."""

    @abstractmethod
    async def start_challenge(self, session: AsyncSession, phone: str) -> None:
        """بدء التحدي (إرسال OTP). في وضع كلمة المرور لا شيء يُرسل."""

    @abstractmethod
    async def authenticate(
        self, session: AsyncSession, phone: str, credential: str
    ) -> User:
        """التحقق من الهوية وإرجاع المستخدم، أو رفع خطأ مصادقة."""
