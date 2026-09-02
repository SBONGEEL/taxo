"""بلاغاتُ صور الركاب في اللوحة — **حجبٌ وقع، وقرارٌ ينتظر**.

**والشاشةُ تقرّر ولا تُنشئ**: البلاغُ يكتبه كبتنٌ رأى الصورة، والمشرفُ يفصل —
إمّا **إعادة** (بلاغٌ كاذب) أو **حذف**. ولا بابَ هنا يُنشئ بلاغاً: من لم يرَ
الصورةَ في رحلته لا يبلّغ عنها.

**والصفُّ يبقى بعد القرار** — لا يُحذف: مُبلِّغٌ يبلّغ كذباً مراراً يُقرأ من
صفوفه، ومن حُذفت صورتُه ثم رفع مثلَها كذلك. **فالحذفُ يمسح الملفَّ لا الأثر.**
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.core.deps import FleetManager, DbSession
from app.schemas.photo_report import PhotoReportOut
from app.core import storage
from app.models.user import User
from app.services import audit, avatar, rider_photo
from app.models.enums import AuditAction

router = APIRouter(prefix="/admin/photo-reports", tags=["admin"])


@router.get("", response_model=list[PhotoReportOut])
async def list_reports(_admin: FleetManager, session: DbSession) -> list[PhotoReportOut]:
    """المعلَّقةُ وحدَها — **وصورةُ كلٍّ محجوبةٌ الآن** بانتظار هذا القرار."""
    rows = await rider_photo.open_reports(session)
    out: list[PhotoReportOut] = []
    for row in rows:
        subject = await session.get(User, row.subject_id)
        reporter = await session.get(User, row.reported_by)
        out.append(
            PhotoReportOut(
                id=row.id,
                subject_id=row.subject_id,
                subject_name=subject.name if subject else None,
                subject_phone=subject.phone if subject else None,
                reported_by=row.reported_by,
                reporter_name=reporter.name if reporter else None,
                ride_id=row.ride_id,
                created_at=row.created_at,
                resolution=row.resolution,
            )
        )
    return out


@router.get("/{report_id}/photo")
async def reported_photo(
    report_id: uuid.UUID, _admin: FleetManager, session: DbSession
) -> Response:
    """الصورةُ المبلَّغُ عنها — **البابُ الوحيدُ الذي يراها وهي محجوبة**.

    **وقرارٌ بلا رؤيةٍ ليس قراراً**: من يُطلب منه أن يحذف أو يُعيد ولا يرى ما
    يحكم عليه يضغط أحدَ الزرّين بالتخمين. فهي تُقرأ من `photo_path` مباشرةً
    **متجاوزةً `visible_path`** — الحجبُ عن الكبتن والراكب، لا عن الفاصل.

    **ولا `no-store` وحدَها بل `no-store` وللمشرف فقط**: صورةٌ شخصيةٌ لشخصٍ
    لم يُدَن بعد.
    """
    row = await rider_photo.get_report(session, report_id)
    subject = await session.get(User, row.subject_id)
    raw: bytes | None = None
    if subject is not None and subject.photo_path:
        try:
            raw = storage.resolve(subject.photo_path).read_bytes()
        except OSError:
            raw = None
    return Response(
        content=avatar.render(raw, name=(subject.name if subject else "")),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": 'inline; filename="reported.jpg"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{report_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_report(
    report_id: uuid.UUID,
    remove: bool,
    admin: FleetManager,
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
