"""مفتاحُ وضع الضيف لكلِّ تطبيق — من اللوحة (SPEC §٧٦-ن/٤).

القراءةُ للطاقم، **والكتابةُ لمن يملك `settings.write`** كبقيّة الإعدادات؛ وكلُّ تغييرٍ في سجلّ التدقيق بأسماء ما تغيّر.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction
from app.schemas.guest import GuestModeIn, GuestModeOut
from app.services import audit
from app.services import guest as guest_service

router = APIRouter(prefix="/admin/guest-mode", tags=["admin"])


@router.get("", response_model=GuestModeOut)
async def read_guest_mode(_staff: StaffUser, session: DbSession) -> GuestModeOut:
    return GuestModeOut(**await guest_service.enabled(session))


@router.put("", response_model=GuestModeOut)
async def update_guest_mode(payload: GuestModeIn, admin: SettingsWriter, session: DbSession) -> GuestModeOut:
    row, changed = await guest_service.update(session, rider=payload.rider, driver=payload.driver)
    if changed:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="guest_mode_settings",
            entity_id=row.id,
            details={"fields": changed, "rider": row.rider_enabled, "driver": row.driver_enabled},
        )
    await session.commit()
    return GuestModeOut(**await guest_service.enabled(session))
