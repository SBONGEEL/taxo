"""ملاحظاتُ المختبرين والمستخدمين في اللوحة (SPEC §٧٦/٤) — **مَن أرسل · أيُّ تطبيق · أيُّ إصدار · متى**.

**والقراءةُ للموظّفين** (`StaffUser`): الدعمُ يقرأ ما يكتبه الناسُ كما يقرأ الأعطال. **والصورةُ تُخدَم بترويسات الوثائق** — ملفٌّ رفعه
مستخدم: `nosniff` و`no-store`.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core import storage
from app.core.deps import DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.feedback import AdminFeedbackOut, AdminFeedbackPage, FeedbackHandledIn
from app.services import audit
from app.services import feedback as feedback_service

router = APIRouter(prefix="/admin/feedback", tags=["admin"])


def _out(row: feedback_service.FeedbackRow) -> AdminFeedbackOut:
    item = row.feedback
    return AdminFeedbackOut(
        id=item.id,
        user_id=item.user_id,
        user_name=row.user_name,
        user_phone=row.user_phone,
        app=item.app,
        message=item.message,
        app_version=item.app_version,
        web_build=item.web_build,
        platform=item.platform,
        route=item.route,
        has_screenshot=item.screenshot_path is not None,
        created_at=item.created_at,
        handled_at=item.handled_at,
    )


@router.get("", response_model=AdminFeedbackPage)
async def list_feedback(
    _staff: StaffUser,
    session: DbSession,
    status: Literal["all", "new", "handled"] = "all",
    app: Literal["rider", "driver"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminFeedbackPage:
    rows, total, new_count = await feedback_service.page(
        session, status=status, app=app, limit=limit, offset=offset
    )
    return AdminFeedbackPage(items=[_out(row) for row in rows], total=total, new_count=new_count)


@router.get("/{feedback_id}/screenshot")
async def feedback_screenshot(feedback_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> FileResponse:
    row = await feedback_service.get(session, feedback_id)
    if not row.screenshot_path:
        raise NotFound("لا صورةَ مع هذه الملاحظة")
    path = storage.resolve(row.screenshot_path)
    return FileResponse(
        path,
        media_type=row.screenshot_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="feedback{path.suffix}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{feedback_id}", response_model=AdminFeedbackOut)
async def mark_feedback(
    feedback_id: uuid.UUID, payload: FeedbackHandledIn, staff: StaffUser, session: DbSession
) -> AdminFeedbackOut:
    """«عولجت» أو إعادتُها جديدة — **ويُسجَّل في التدقيق** كأيِّ قرارِ موظّف."""
    row = await feedback_service.set_handled(session, feedback_id, admin=staff, handled=payload.handled)
    await audit.record(
        session,
        actor=staff,
        action=AuditAction.UPDATE,
        entity_type="app_feedback",
        entity_id=row.id,
        changes={"handled": {"after": payload.handled}},
    )
    sender = await session.get(User, row.user_id)
    await session.commit()
    return _out(feedback_service.FeedbackRow(row, sender.name if sender else None, sender.phone if sender else None))
