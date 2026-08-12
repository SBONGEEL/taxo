"""سياسةُ دخول اللوحة — قراءةٌ وكتابةٌ لـ`admin` حصراً (القسم 14.1، 12-د).

**لا `StaffUser` هنا**: هذه سياسةُ من يدخل اللوحة، وتوسيعُ مهلة الخمول أو إطفاء
الإلزام قرارٌ على الطاقم كلّه لا إجراءُ دعمٍ فنيّ — كصفحة العقود بالضبط
(القسم 13/8).

وكلُّ كتابةٍ تدخل سجل التدقيق بأسماءِ ما تغيّر لا بقيمه، كبقية كتابات اللوحة.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession
from app.models.enums import AuditAction
from app.schemas.security import (
    SecuritySettingOut,
    SecuritySettingUpdate,
    TotpStatusOut,
)
from app.services import audit, security_settings, totp

router = APIRouter(prefix="/admin/security", tags=["admin"])


async def _my_factor(session, user) -> TotpStatusOut:
    record = await totp.get_record(session, user.id)
    return TotpStatusOut(
        enrolled=record is not None,
        confirmed=bool(record and record.is_confirmed),
        confirmed_at=record.confirmed_at if record else None,
        recovery_verified_at=record.recovery_codes_verified_at if record else None,
        recovery_codes_remaining=await totp.remaining_recovery_codes(session, user.id),
        required=await security_settings.totp_required_for(session, user),
    )


async def _read(session, user) -> SecuritySettingOut:
    row = await security_settings.get(session)
    return SecuritySettingOut(
        admin_totp_required=bool(row and row.admin_totp_required),
        admin_idle_timeout_minutes=await security_settings.idle_timeout_minutes(session),
        my_factor=await _my_factor(session, user),
    )


@router.get("", response_model=SecuritySettingOut)
async def read_security_settings(
    user: AdminUser, session: DbSession
) -> SecuritySettingOut:
    """السياسةُ ومعها حالةُ عاملِ من يقرأ — فالشاشةُ تعرف **لماذا** يُعطَّل الزر."""
    return await _read(session, user)


@router.put("", response_model=SecuritySettingOut)
async def update_security_settings(
    payload: SecuritySettingUpdate, user: AdminUser, session: DbSession
) -> SecuritySettingOut:
    """يكتب السياسة — وإشعالُ الإلزام مشروطٌ بإثبات استردادِ الطالب نفسِه."""
    row, changed = await security_settings.update(
        session,
        actor=user,
        admin_totp_required=payload.admin_totp_required,
        admin_idle_timeout_minutes=payload.admin_idle_timeout_minutes,
    )
    if changed:
        await audit.record(
            session,
            actor=user,
            action=AuditAction.UPDATE,
            entity_type="security_settings",
            entity_id=row.id,
            details={"fields": changed},
        )
    await session.commit()
    return await _read(session, user)
