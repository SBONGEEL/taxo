"""الحسابات في اللوحة: القائمة والفلترة واعتماد الكباتن (SPEC القسم 13.2/13.3).

شريحةٌ صغيرة من صفحتي «الكباتن» و«الركاب» تسبق واجهتَهما في المرحلة 11،
لأن قاعدتين من المرحلة 8-ب لا مكان لهما بغيرها:

- **الحسابات غير المحققة تُعلَّم وتُفلتر**: الرقم غير المُثبَت حالةٌ استثنائية
  لا تقع إلا بإطفاء مفتاح الطوارئ، ولا تُعالَج إن لم تُرَ.
- **لا يُعتمد كبتنٌ غير محقق الرقم مهما كان المفتاح**: رقمُ الكبتن هو ما
  يستلم عليه حوالات كليك (SPEC القسم 6/9)، فاعتمادُ من لا نعرف أنه يملكه
  إرسالُ مالٍ إلى رقمٍ مجهول.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import AdminUser, DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, UserRole
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.driver import DriverOut
from app.services import drivers as drivers_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _staff: StaffUser,
    session: DbSession,
    role: UserRole | None = None,
    country_code: CountryCode | None = None,
    phone_verified: bool | None = Query(
        default=None,
        description="فلترة الحسابات غير المحققة — تُعالَج أولاً بعد إعادة تفعيل المفتاح",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserOut]:
    """قائمة الحسابات بوسم التحقق — و`UserOut.phone_verified` هو الوسم."""
    stmt = select(User).order_by(User.created_at.desc())
    if role is not None:
        stmt = stmt.where(User.role == role)
    if country_code is not None:
        stmt = stmt.where(User.country_code == country_code)
    if phone_verified is True:
        stmt = stmt.where(User.phone_verified_at.is_not(None))
    elif phone_verified is False:
        stmt = stmt.where(User.phone_verified_at.is_(None))

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    return [UserOut.model_validate(row) for row in rows]


@router.post("/drivers/{driver_id}/approve", response_model=DriverOut)
async def approve_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    """اعتماد الكبتن بعد مراجعة مستنداته — ويشترط رقماً مُثبتاً."""
    driver = await _driver(session, driver_id)
    driver = await drivers_service.approve(session, driver=driver, actor=admin)
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


@router.post("/drivers/{driver_id}/reject", response_model=DriverOut)
async def reject_driver(
    driver_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> DriverOut:
    driver = await _driver(session, driver_id)
    driver = await drivers_service.set_status(
        session, driver=driver, status=DriverStatus.REJECTED, actor=admin
    )
    await session.commit()
    await session.refresh(driver)
    return DriverOut.model_validate(driver)


async def _driver(session, driver_id: uuid.UUID) -> Driver:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    return driver
