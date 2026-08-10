from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PhoneAlreadyRegistered
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import AuthMethodResponse, RegisterRequest
from app.services.otp import Challenge

AuthMethod = Literal["password", "otp"]


class AuthStrategy(ABC):
    """واجهة موحّدة للمصادقة.

    الاستراتيجية الفعّالة تُختار وقت التشغيل (`get_auth_strategy`):
    - `PasswordAuthStrategy` ما دام لا يوجد مزود SMS مفعّل.
    - `OtpAuthStrategy` تلقائياً بمجرد تفعيل مزود SMS من صفحة العقود.

    الراوترات والواجهات تتعامل مع هذه الواجهة فقط، فلا يتغير أي endpoint
    عند التبديل — يتغير معنى الحقل `credential` من كلمة مرور إلى رمز OTP.

    كل عملية تأخذ `redis` وإن لم تحتجه استراتيجيةُ كلمة المرور: التوقيع واحد
    كي يبقى الراوتر جاهلاً بأيّهما يخدمه.
    """

    method: AuthMethod

    @abstractmethod
    def describe(self) -> AuthMethodResponse:
        """وصف طريقة الدخول الحالية للواجهات."""

    @abstractmethod
    async def register(
        self, session: AsyncSession, redis: Redis, data: RegisterRequest
    ) -> User:
        """إنشاء حساب جديد."""

    @abstractmethod
    async def start_challenge(
        self, session: AsyncSession, redis: Redis, phone: str
    ) -> Challenge:
        """بدء التحدي (إرسال OTP). في وضع كلمة المرور لا شيء يُرسل."""

    @abstractmethod
    async def authenticate(
        self, session: AsyncSession, redis: Redis, phone: str, credential: str
    ) -> User:
        """التحقق من الهوية وإرجاع المستخدم، أو رفع خطأ مصادقة."""


async def create_account(
    session: AsyncSession,
    *,
    phone: str,
    data: RegisterRequest,
    password_hash: str | None,
) -> User:
    """إنشاء الحساب — مشتركٌ بين الاستراتيجيتين.

    الفرق بينهما حقلٌ واحد: حساب OTP بلا `password_hash` (العمود nullable
    لهذا السبب بالضبط). وما عداه — فحص التكرار وملف الكبتن المعلّق — واحد،
    فلا يُكتب مرتين ليفترق مرتين.
    """
    existing = await session.scalar(select(User.id).where(User.phone == phone))
    if existing is not None:
        raise PhoneAlreadyRegistered()

    user = User(
        phone=phone,
        name=data.name.strip(),
        role=UserRole(data.role),
        country_code=data.country_code,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()

    if user.role is UserRole.DRIVER:
        # ملف الكبتن يُنشأ فوراً بحالة pending بانتظار مراجعة المستندات
        session.add(Driver(user_id=user.id))
        await session.flush()

    return user
