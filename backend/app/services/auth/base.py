from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PhoneAlreadyRegistered
from app.models.driver import Driver
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import RegisterRequest

async def create_account(
    session: AsyncSession,
    *,
    phone: str,
    data: RegisterRequest,
    password_hash: str | None,
    phone_verified_at: datetime | None = None,
) -> User:
    """إنشاء الحساب — البابُ الوحيد، فلا يُكتب المنطق مرتين ليفترق مرتين.

    `phone_verified_at` فارغة تعني رقماً لم يُثبَت: لا تقع إلا حين يُطفئ
    المشرف مفتاح `otp_verification_enabled` للطوارئ (SPEC القسم 4)، ويبقى
    الحساب موسوماً في اللوحة حتى يُثبِت صاحبُه رقمه.
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
        phone_verified_at=phone_verified_at,
    )
    session.add(user)
    await session.flush()

    if user.role is UserRole.DRIVER:
        # ملف الكبتن يُنشأ فوراً بحالة pending بانتظار مراجعة المستندات
        session.add(Driver(user_id=user.id))
        await session.flush()

    return user
