"""بلاغاتُ صور الركاب في اللوحة — **حجبٌ وقع، وقرارٌ ينتظر**.

**والشاشةُ تقرّر ولا تُنشئ**: البلاغُ يكتبه كبتنٌ رأى الصورة، والمشرفُ يفصل —
إمّا **إعادة** (بلاغٌ كاذب) أو **حذف**. ولا بابَ هنا يُنشئ بلاغاً: من لم يرَ
الصورةَ في رحلته لا يبلّغ عنها.

**والصفُّ يبقى بعد القرار** — لا يُحذف: مُبلِّغٌ يبلّغ كذباً مراراً يُقرأ من
صفوفه، ومن حُذفت صورتُه ثم رفع مثلَها كذلك. **فالحذفُ يمسح الملفَّ لا الأثر.**
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import AdminUser, DbSession
from app.schemas.photo_report import PhotoReportOut
from app.services import audit, rider_photo
from app.models.enums import AuditAction

router = APIRouter(prefix="/admin/photo-reports", tags=["admin"])


@router.get("", response_model=list[PhotoReportOut])
async def list_reports(_admin: AdminUser, session: DbSession) -> list[PhotoReportOut]:
    """المعلَّقةُ وحدَها — **وصورةُ كلٍّ محجوبةٌ الآن** بانتظار هذا القرار."""
    rows = await rider_photo.open_reports(session)
    return [PhotoReportOut.model_validate(row) for row in rows]


@router.post("/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_report(
    report_id: uuid.UUID,
    remove: bool,
    admin: AdminUser,
    session: DbSession,
) -> None:
    """قرارُ المشرف — **ويُقيَّد في التدقيق كغيره**: هذا حذفُ محتوى شخصٍ آخر."""
    row = await rider_photo.resolve(
        session, report_id=report_id, admin_id=admin.id, remove=remove
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="user_photo_report",
        entity_id=row.id,
        details={"resolution": row.resolution},
    )
    await session.commit()
