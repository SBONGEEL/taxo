"""الدخول بكلمة المرور — الطريقة الوحيدة (المرحلة 8-ب).

ومعها **تعيين كلمة المرور**: عند التسجيل، وعند استعادتها بعد إثبات ملكية
الرقم. والتعيينُ يُبطل كل الجلسات القائمة — كلمةٌ تُغيَّر لأن القديمة تسرّبت
لا تُغيَّر شيئاً إن بقيت جلسةُ من سرّبها مفتوحة.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountBlocked, InvalidCredentials, InvalidInput
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services import token_service
from app.services.auth.base import create_account

# هاش وهمي لكلمة مرور عشوائية — يُستخدم لتثبيت زمن الاستجابة عند عدم وجود
# المستخدم، فلا يكشف الفرق الزمني أي الأرقام مسجّلة (user enumeration).
_DUMMY_HASH = hash_password("taxo-timing-equalizer")

MIN_PASSWORD_LENGTH = 8
# سقفٌ من الاستراتيجية لا من المخطط: المخطط يتسع لرمز هوية Firebase في حقلٍ
# آخر، وكلمةُ مرورٍ بألف حرف ليست كلمة مرور. والتجزئة المسبقة (sha256) تعني
# أن الطول لا يكسر bcrypt أصلاً — فالسقف نظافةٌ لا حماية
MAX_PASSWORD_LENGTH = 128


def validate_password(password: str) -> str:
    """سياسة كلمة المرور في مكان واحد — يستدعيها التسجيل والاستعادة معاً."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidInput(f"كلمة المرور يجب ألا تقل عن {MIN_PASSWORD_LENGTH} خانات")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise InvalidInput(f"كلمة المرور يجب ألا تزيد عن {MAX_PASSWORD_LENGTH} خانة")
    return password


class PasswordAuthStrategy:
    """الدخول برقم الهاتف + كلمة المرور."""

    method = "password"

    def describe(self) -> AuthMethodResponse:
        return AuthMethodResponse(login="password", verification="none")

    async def register(
        self,
        session: AsyncSession,
        data: RegisterRequest,
        *,
        phone: str,
        verified_at=None,
    ) -> User:
        return await create_account(
            session,
            phone=phone,
            data=data,
            password_hash=hash_password(validate_password(data.password)),
            phone_verified_at=verified_at,
        )

    async def authenticate(
        self, session: AsyncSession, phone: str, password: str
    ) -> User:
        user = await session.scalar(select(User).where(User.phone == phone))

        if user is None or user.password_hash is None:
            # حسابٌ بلا كلمة مرور (أُنشئ قبل المرحلة 8-ب بـ OTP وحده) يُعامل
            # كغير الموجود: نفس الجواب ونفس الزمن، ومخرجُه استعادةُ كلمة
            # المرور — لا كلمةٌ يخترعها من يجرّب
            verify_password(password, _DUMMY_HASH)
            raise InvalidCredentials()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentials()

        if user.is_blocked:
            raise AccountBlocked()

        return user


async def set_password(
    session: AsyncSession, redis: Redis, *, user: User, new_password: str
) -> User:
    """يعيّن كلمة مرورٍ جديدة **ويُبطل كل جلسات صاحبها**.

    الإبطال جزءٌ من العملية لا خطوةٌ تالية: من غيّر كلمته لأنها تسرّبت لم
    يُغيّر شيئاً إن بقيت جلسةُ من سرّبها مفتوحة. و`revoke_all_for_user` يمحو
    مفاتيح التحديث؛ أما توكن الوصول القصير فينتهي بنفسه (SPEC القسم 14).

    الـ commit مسؤولية الراوتر.
    """
    user.password_hash = hash_password(validate_password(new_password))
    await token_service.revoke_all_for_user(redis, user.id)
    return user
