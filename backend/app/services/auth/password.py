from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountBlocked, InvalidCredentials, PhoneAlreadyRegistered
from app.core.security import hash_password, verify_password
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services.auth.base import AuthStrategy

# هاش وهمي لكلمة مرور عشوائية — يُستخدم لتثبيت زمن الاستجابة عند عدم وجود
# المستخدم، فلا يكشف الفرق الزمني أي الأرقام مسجّلة (user enumeration).
_DUMMY_HASH = hash_password("taxo-timing-equalizer")


class PasswordAuthStrategy(AuthStrategy):
    """الدخول برقم الهاتف + كلمة المرور (الوضع الافتراضي قبل مزود SMS)."""

    method = "password"

    def describe(self) -> AuthMethodResponse:
        return AuthMethodResponse(method="password")

    async def register(self, session: AsyncSession, data: RegisterRequest) -> User:
        from app.core.phone import normalize_phone  # تفادي دورة استيراد

        phone = normalize_phone(data.phone, data.country_code)

        existing = await session.scalar(select(User.id).where(User.phone == phone))
        if existing is not None:
            raise PhoneAlreadyRegistered()

        user = User(
            phone=phone,
            name=data.name.strip(),
            role=UserRole(data.role),
            country_code=data.country_code,
            password_hash=hash_password(data.password),
        )
        session.add(user)
        await session.flush()

        if user.role is UserRole.DRIVER:
            # ملف الكبتن يُنشأ فوراً بحالة pending بانتظار مراجعة المستندات
            session.add(Driver(user_id=user.id))
            await session.flush()

        return user

    async def start_challenge(self, session: AsyncSession, phone: str) -> None:
        return None  # لا تحدي في وضع كلمة المرور

    async def authenticate(
        self, session: AsyncSession, phone: str, credential: str
    ) -> User:
        user = await session.scalar(select(User).where(User.phone == phone))

        if user is None:
            verify_password(credential, _DUMMY_HASH)
            raise InvalidCredentials()

        if not verify_password(credential, user.password_hash):
            raise InvalidCredentials()

        if user.is_blocked:
            raise AccountBlocked()

        return user
