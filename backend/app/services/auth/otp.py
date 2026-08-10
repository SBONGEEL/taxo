"""الدخول برمز OTP عبر SMS (SPEC القسم 15/أ — المرحلة 8).

تُختار تلقائياً ما إن يُفعَّل عقد مزود SMS من صفحة العقود، بلا تعديل أي
endpoint: الحقل `password` في `/auth/login` و`/auth/register` يصير معناه
«رمز التحقق»، والواجهة تعرف ذلك من `GET /auth/method` (`otp_length`).

**الحساب المُنشأ هنا بلا كلمة مرور** — العمود nullable لهذا بالضبط (القسم 4).
فلو أُطفئ عقد الرسائل لاحقاً لم يستطع صاحبه الدخول بكلمة مرور لا يملكها؛
وهذا هو الصواب: طريقة الدخول قرارٌ إداري على مستوى النظام، وإعادةُ تعيينٍ
لكلمة مرورٍ لم تُوضع أبداً بابٌ لا يُفتح بغير تحقق.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountBlocked, AccountNotRegistered
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services import otp
from app.services.auth.base import AuthStrategy, create_account
from app.services.otp import Challenge

OTP_LENGTH = otp.CODE_LENGTH


class OtpAuthStrategy(AuthStrategy):
    method = "otp"

    def describe(self) -> AuthMethodResponse:
        return AuthMethodResponse(method="otp", otp_length=OTP_LENGTH)

    async def start_challenge(
        self, session: AsyncSession, redis: Redis, phone: str
    ) -> Challenge:
        return await otp.issue(session, redis, phone)

    async def register(
        self, session: AsyncSession, redis: Redis, data: RegisterRequest
    ) -> User:
        """التسجيل = إثبات ملكية الرقم ثم إنشاء الحساب.

        الرمز يُستهلك **قبل** الإنشاء: لو فشل الإنشاء (رقم مسجّل مسبقاً) فقد
        احترق الرمز — وهو الصواب، فمن أثبت ملكية الرقم لا يحتاج نفس الرمز
        لمحاولةٍ ثانية بنيّةٍ أخرى.
        """
        from app.core.phone import normalize_phone  # تفادي دورة استيراد

        phone = normalize_phone(data.phone, data.country_code)
        await otp.verify(redis, phone, data.password)

        return await create_account(
            session, phone=phone, data=data, password_hash=None
        )

    async def authenticate(
        self, session: AsyncSession, redis: Redis, phone: str, credential: str
    ) -> User:
        """يتحقق من الرمز أولاً ثم يبحث عن الحساب.

        الترتيب مقصود: بغيره يصير المسار عدّاداً للحسابات — من يجرّب أرقاماً
        عشوائية يعرف أيُّها مسجّل من اختلاف الجواب قبل أن يملك رمزاً أصلاً.
        """
        await otp.verify(redis, phone, credential)

        user = await session.scalar(select(User).where(User.phone == phone))
        if user is None:
            raise AccountNotRegistered()
        if user.is_blocked:
            raise AccountBlocked()
        return user
