"""ساعاتُ عمل الكبتن للإدارة (SPEC §٦٢-ج/٣٧، §٦٤-ج: «يراها الكبتنُ والإدارة») — ثلاثون يوماً وما جُمع شهرياً. **ولا موقع.**"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.deps import DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import FeatureKey
from app.models.user import User
from app.schemas.activity import ActivityDayOut, ActivityMonthOut, DriverActivityOut
from app.services import activity, settings_service
from app.services.stats import _zone

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/drivers/{driver_id}/activity", response_model=DriverActivityOut)
async def driver_activity(driver_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> DriverActivityOut:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    owner = await session.get(User, driver.user_id)
    assert owner is not None
    today = datetime.now(UTC).astimezone(await _zone(session, owner.country_code)).date()
    view = await activity.view_for_admin(session, driver_id, today)
    return DriverActivityOut(
        enabled=await settings_service.is_feature_enabled(session, owner.country_code, FeatureKey.WORK_HOURS_ENABLED),
        today_minutes=view.today,
        week_minutes=view.week,
        month_minutes=view.month,
        days=[ActivityDayOut(day=day, minutes=minutes) for day, minutes in view.days],
        months=[ActivityMonthOut(month=month, minutes=minutes) for month, minutes in view.months],
    )
