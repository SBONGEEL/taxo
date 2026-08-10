"""أجهزة المستخدم وتفضيلات إشعاراته (SPEC القسم 4/10 — المرحلة 8).

مساران للجهاز — تسجيلٌ عند الدخول وحذفٌ عند الخروج — ومسارٌ لتفضيلٍ واحد:
إشعارات الحملات. **المعاملاتي ليس تفضيلاً** فلا مفتاح له هنا: من يطفئ
«وصل الكبتن» ينتظر كبتناً لا يعرف أنه وصل.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.device import (
    DeviceOut,
    DeviceRegisterRequest,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
)
from app.services import devices as devices_service

router = APIRouter(prefix="/me", tags=["devices"])


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(user: CurrentUser, session: DbSession) -> list[DeviceOut]:
    return [
        DeviceOut.model_validate(device)
        for device in await devices_service.list_for_user(session, user.id)
    ]


@router.put("/devices", response_model=DeviceOut)
async def register_device(
    payload: DeviceRegisterRequest, user: CurrentUser, session: DbSession
) -> DeviceOut:
    """تسجيل الجهاز أو تحديث رمزه — يُستدعى بعد الدخول وكلما دار الرمز."""
    device = await devices_service.register(
        session,
        user=user,
        device_id=payload.device_id,
        token=payload.token,
        platform=payload.platform,
    )
    await session.commit()
    await session.refresh(device)
    return DeviceOut.model_validate(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    device_id: str, user: CurrentUser, session: DbSession
) -> None:
    """حذف الجهاز عند الخروج — لا يبقى رمزٌ يوصل إشعارات حسابٍ غادر الهاتف."""
    await devices_service.unregister(session, user=user, device_id=device_id)
    await session.commit()


@router.get("/notification-preferences", response_model=NotificationPreferencesOut)
async def read_preferences(user: CurrentUser) -> NotificationPreferencesOut:
    return NotificationPreferencesOut(
        marketing_push_enabled=user.marketing_push_enabled
    )


@router.put("/notification-preferences", response_model=NotificationPreferencesOut)
async def update_preferences(
    payload: NotificationPreferencesUpdate, user: CurrentUser, session: DbSession
) -> NotificationPreferencesOut:
    user.marketing_push_enabled = payload.marketing_push_enabled
    await session.commit()
    return NotificationPreferencesOut(
        marketing_push_enabled=user.marketing_push_enabled
    )
