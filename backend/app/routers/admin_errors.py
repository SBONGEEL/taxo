"""شاشةُ الأعطال في اللوحة — **تقرأ المجموعاتِ وتحسمها** (2026-09-20).

**ولا بابَ هنا يكتب حدثاً**: الأحداثُ تأتي من الأجهزة عبر `telemetry` وحدَه.
وما يُكتب من هنا **حالُ المجموعة** لا محتواها — إقرارٌ من إنسانٍ بأنه رآها.

## والحسمُ ثلاثيُّ الاتجاه لا اتجاهان

«حُسم» و«كُتم» **وعودةٌ إلى المفتوح**. والثالثُ ليس ترفاً: **بابٌ يُغلق ولا
يُفتح** هو «مفتاحٌ بُني ليوقف الأذى ولا يُطفأ» بعينه — مشرفٌ يحسم مجموعةً
بالخطأ يبقى العطبُ مخفيّاً بلا سبيل. **وثلاثتُها تدخل سجلَّ التدقيق**.

## وقراءةُ القائمة لا تُسجَّل

**وهذا قرارٌ لا سهو**: القراءتان المسجَّلتان في المشروع كلِّه (`live_map`
و`driver_live`) **تقرنان هويةً بموقع**، وهذه لا تحمل هويةً أصلاً — لا رقمَ
ولا حساباً ولا إحداثيّة (`core/scrub.py`). **وقيدٌ لكلِّ فتحةِ شاشةٍ تقنيّة
يُغرق السجلَّ الذي بُني ليُقرأ**، فيصير التدقيقُ ضجيجاً.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from app.core.deps import DbSession, ErrorsReader
from app.models.enums import AuditAction, ClientApp, ErrorSort, ErrorStatus
from app.models.error_report import ErrorEvent, ErrorGroup
from app.schemas.error_report import (
    ErrorEventOut,
    ErrorGroupDetailOut,
    ErrorGroupOut,
)
from app.services import audit

router = APIRouter(prefix="/admin/errors", tags=["admin:errors"])


async def _locked_group(session: DbSession, group_id: uuid.UUID) -> ErrorGroup:
    """يُقفل الصفَّ **قبل** أن تُقرأ حالُه — كبقيةِ مغيّراتِ الحال.

    **والقفلُ ليس احتياطاً هنا أيضاً**: مشرفان يضغطان «حُسم» و«كُتم» معاً
    يقرآن `open` كلاهما ويكتب أحدُهما فوق الآخر، **فيُقرأ السجلُّ إقرارين
    وأحدُهما لم يقع**.
    """
    row = await session.execute(
        select(ErrorGroup).where(ErrorGroup.id == group_id).with_for_update()
    )
    group = row.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return group


@router.get("", response_model=list[ErrorGroupOut])
async def list_error_groups(
    _reader: ErrorsReader,
    session: DbSession,
    app: ClientApp | None = None,
    group_status: ErrorStatus | None = Query(default=None, alias="status"),
    release: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
    sort: ErrorSort = ErrorSort.USERS,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ErrorGroupOut]:
    """قائمةُ المجموعات — **والافتراضُ ترتيبٌ بالمتأثّرين**.

    **والفلاترُ هي أسئلةُ القراءة الحقيقية**: أيُّ تطبيقٍ · أفي النسخة الجديدة
    وحدَها · وما لم يُحسم بعد.
    """
    stmt = select(ErrorGroup)

    if app is not None:
        stmt = stmt.where(ErrorGroup.app == app)
    if group_status is not None:
        stmt = stmt.where(ErrorGroup.status == group_status)
    if release:
        # **آخرُ إصدارٍ رُئيت فيه** — «أما زالت تقع في الجديدة؟»
        stmt = stmt.where(ErrorGroup.last_seen_release == release)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            ErrorGroup.title.ilike(needle) | ErrorGroup.name.ilike(needle)
        )

    order = {
        ErrorSort.USERS: (desc(ErrorGroup.user_count), desc(ErrorGroup.last_seen_at)),
        ErrorSort.EVENTS: (desc(ErrorGroup.event_count), desc(ErrorGroup.last_seen_at)),
        ErrorSort.LAST_SEEN: (desc(ErrorGroup.last_seen_at),),
    }[sort]

    rows = await session.execute(stmt.order_by(*order).limit(limit).offset(offset))
    return [ErrorGroupOut.model_validate(row) for row in rows.scalars()]


@router.get("/{group_id}", response_model=ErrorGroupDetailOut)
async def get_error_group(
    group_id: uuid.UUID, _reader: ErrorsReader, session: DbSession
) -> ErrorGroupDetailOut:
    """المجموعةُ ومعها **آخرُ** حدث — وهو ما يُقرأ عند التشخيص."""
    group = await session.get(ErrorGroup, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    latest = await session.execute(
        select(ErrorEvent)
        .where(ErrorEvent.group_id == group_id)
        .order_by(desc(ErrorEvent.received_at))
        .limit(1)
    )
    event = latest.scalar_one_or_none()

    detail = ErrorGroupDetailOut.model_validate(group)
    detail.latest = ErrorEventOut.model_validate(event) if event else None
    return detail


@router.get("/{group_id}/events", response_model=list[ErrorEventOut])
async def list_error_events(
    group_id: uuid.UUID,
    _reader: ErrorsReader,
    session: DbSession,
    reported_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ErrorEventOut]:
    """أحداثُ المجموعة — **و`reported_only` تُظهر ما كتبه الناسُ وحدَه**.

    وهي القراءةُ التي تستحقّ وقتاً: جملةُ إنسانٍ تقول ما كان يحاول أن يفعل،
    **وأثرُ المكدَّس لا يقول ذلك أبداً**.
    """
    stmt = select(ErrorEvent).where(ErrorEvent.group_id == group_id)
    if reported_only:
        stmt = stmt.where(ErrorEvent.user_reported.is_(True))
    rows = await session.execute(
        stmt.order_by(desc(ErrorEvent.received_at)).limit(limit)
    )
    return [ErrorEventOut.model_validate(row) for row in rows.scalars()]


async def _set_status(
    session: DbSession,
    admin,
    group_id: uuid.UUID,
    target: ErrorStatus,
    action_text: str,
) -> ErrorGroupOut:
    group = await _locked_group(session, group_id)
    before = group.status
    group.status = target
    group.resolved_at = func.now() if target is ErrorStatus.RESOLVED else None
    group.resolved_by = admin.id if target is ErrorStatus.RESOLVED else None

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="error_group",
        entity_id=group.id,
        details={"from": before.value, "to": target.value, "what": action_text},
    )
    await session.commit()
    await session.refresh(group)
    return ErrorGroupOut.model_validate(group)


@router.post("/{group_id}/resolve", response_model=ErrorGroupOut)
async def resolve_error_group(
    group_id: uuid.UUID, admin: ErrorsReader, session: DbSession
) -> ErrorGroupOut:
    """**«حُسم» إقرارٌ بأنه أُصلح** — ويحمل اسمَ من أقرّ ووقتَه."""
    return await _set_status(session, admin, group_id, ErrorStatus.RESOLVED, "حُسم")


@router.post("/{group_id}/ignore", response_model=ErrorGroupOut)
async def ignore_error_group(
    group_id: uuid.UUID, admin: ErrorsReader, session: DbSession
) -> ErrorGroupOut:
    """**«كُتم» غيرُ «حُسم»**: «أعرفه ولا أريد أن أراه» لا «أُصلح».

    **وخلطُهما يجعل عطباً مكتوماً يُقرأ مُصلَحاً بعد شهر** — ومن يقرأ اللوحةَ
    حينها يبني على أنّ شيئاً عولج ولم يُعالَج.
    """
    return await _set_status(session, admin, group_id, ErrorStatus.IGNORED, "كُتم")


@router.post("/{group_id}/reopen", response_model=ErrorGroupOut)
async def reopen_error_group(
    group_id: uuid.UUID, admin: ErrorsReader, session: DbSession
) -> ErrorGroupOut:
    """**البابُ في اتجاهه الثاني** — ولولاه لكان حسمٌ بالخطأ نهائيّاً."""
    return await _set_status(session, admin, group_id, ErrorStatus.OPEN, "أُعيد فتحُه")
