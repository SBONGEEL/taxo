from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FeatureNotAvailable
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services.auth.base import AuthStrategy

OTP_LENGTH = 6


class OtpAuthStrategy(AuthStrategy):
    """الدخول برمز OTP عبر SMS.

    مكان التنفيذ: المرحلة 8 (طبقة المزودين). موجودة هنا كي يكون التبديل
    تغيير إعداد لا تغيير كود: ما إن يُفعَّل مزود SMS من صفحة العقود حتى
    تُختار هذه الاستراتيجية تلقائياً بدل كلمة المرور.
    """

    method = "otp"

    def describe(self) -> AuthMethodResponse:
        return AuthMethodResponse(method="otp", otp_length=OTP_LENGTH)

    async def register(self, session: AsyncSession, data: RegisterRequest) -> User:
        raise FeatureNotAvailable("التسجيل عبر OTP يُنفَّذ في المرحلة 8")

    async def start_challenge(self, session: AsyncSession, phone: str) -> None:
        raise FeatureNotAvailable("إرسال OTP يُنفَّذ في المرحلة 8")

    async def authenticate(
        self, session: AsyncSession, phone: str, credential: str
    ) -> User:
        raise FeatureNotAvailable("التحقق من OTP يُنفَّذ في المرحلة 8")
