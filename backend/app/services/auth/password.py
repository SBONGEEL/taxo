from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountBlocked, InvalidCredentials, InvalidInput
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services.auth.base import AuthStrategy, create_account
from app.services.otp import Challenge

# هاش وهمي لكلمة مرور عشوائية — يُستخدم لتثبيت زمن الاستجابة عند عدم وجود
# المستخدم، فلا يكشف الفرق الزمني أي الأرقام مسجّلة (user enumeration).
_DUMMY_HASH = hash_password("taxo-timing-equalizer")

# الحد الأدنى لكلمة المرور. **سياسةٌ هنا لا في المخطط**: حقل `credential` في
# `RegisterRequest` يحمل كلمة مرور أو رمز OTP من ستة أرقام حسب المزود المفعّل،
# فسقفٌ في طبقة النقل يمنع أحدهما ليس سقفَ أمان بل عطلٌ في الطريق الآخر.
MIN_PASSWORD_LENGTH = 8


class PasswordAuthStrategy(AuthStrategy):
    """الدخول برقم الهاتف + كلمة المرور (الوضع الافتراضي قبل مزود SMS)."""

    method = "password"

    def describe(self) -> AuthMethodResponse:
        return AuthMethodResponse(method="password")

    async def register(
        self, session: AsyncSession, redis: Redis, data: RegisterRequest
    ) -> User:
        from app.core.phone import normalize_phone  # تفادي دورة استيراد

        if len(data.password) < MIN_PASSWORD_LENGTH:
            raise InvalidInput(
                f"كلمة المرور يجب ألا تقل عن {MIN_PASSWORD_LENGTH} خانات"
            )

        return await create_account(
            session,
            phone=normalize_phone(data.phone, data.country_code),
            data=data,
            password_hash=hash_password(data.password),
        )

    async def start_challenge(
        self, session: AsyncSession, redis: Redis, phone: str
    ) -> Challenge:
        return Challenge(sent=False)  # لا تحدي في وضع كلمة المرور

    async def authenticate(
        self, session: AsyncSession, redis: Redis, phone: str, credential: str
    ) -> User:
        user = await session.scalar(select(User).where(User.phone == phone))

        if user is None or user.password_hash is None:
            # حسابٌ بلا كلمة مرور (أُنشئ بـ OTP) يُعامل كغير الموجود: نفس
            # الجواب ونفس الزمن، فلا يُستدل على طريقة إنشاء الحساب
            verify_password(credential, _DUMMY_HASH)
            raise InvalidCredentials()

        if not verify_password(credential, user.password_hash):
            raise InvalidCredentials()

        if user.is_blocked:
            raise AccountBlocked()

        return user
