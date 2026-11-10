"""**الاعتمادُ الاستثنائيُّ ومتابعةُ الوثائق في اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ١ و٢).

**القراءةُ للفريق، والكتابةُ كلُّها `drivers.exceptional`** — حسّاسة: للمالك ومن يمنحه بالاسم (`permissions.SENSITIVE`). وكلُّ فعلٍ
بسببٍ مكتوبٍ في التدقيق. **والإعداداتُ لكلِّ دولة** بالصلاحيّة نفسِها.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import DbSession, ExceptionalManager, RedisDep, StaffUser
from app.core.exceptions import InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode, DocumentType, DriverStatus
from app.models.user import User
from app.services import document_expiry, documents, exceptional_approval, notifications
from app.services.stats import country_today

router = APIRouter(prefix="/admin", tags=["admin"])


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class FollowupIn(BaseModel):
    reminders: bool | None = None
    extend_days: int | None = None


class RequestDocumentsIn(BaseModel):
    #: **فردٌ أو جماعة** — قائمةُ معرّفات، أو `all_flagged` لكلِّ «معتمد دون وثائق» (في دولةٍ إن ذُكرت)
    driver_ids: list[uuid.UUID] = []
    all_flagged: bool = False
    country_code: CountryCode | None = None


class ExceptionalOut(BaseModel):
    driver_id: uuid.UUID
    status: DriverStatus
    exceptional: bool
    approved_at: datetime | None
    approved_by_name: str | None
    reason: str | None
    deadline_at: datetime | None
    reminders_enabled: bool
    reminded_at: datetime | None
    missing_documents: list[str]


class RequestedOut(BaseModel):
    sent: int


class DocumentSettingsOut(BaseModel):
    country_code: CountryCode
    exceptional_deadline_days: int
    exceptional_reminder_days: int
    expiry_notice_days: list[int]


class DocumentSettingsIn(BaseModel):
    exceptional_deadline_days: int
    exceptional_reminder_days: int
    expiry_notice_days: list[int]


async def _driver(session, driver_id: uuid.UUID) -> Driver:
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    return driver


async def _out(session, driver: Driver) -> ExceptionalOut:
    by = await session.get(User, driver.exceptional_approved_by) if driver.exceptional_approved_by else None
    missing = await documents.missing_required(session, driver.id)
    return ExceptionalOut(
        driver_id=driver.id,
        status=driver.status,
        exceptional=driver.exceptional_approved_at is not None,
        approved_at=driver.exceptional_approved_at,
        approved_by_name=by.name if by else None,
        reason=driver.exceptional_reason,
        deadline_at=driver.documents_deadline_at,
        reminders_enabled=driver.document_reminders_enabled,
        reminded_at=driver.document_reminded_at,
        missing_documents=[documents.label_for(item) for item in missing],
    )


@router.get("/drivers/{driver_id}/exceptional", response_model=ExceptionalOut)
async def read_exceptional(driver_id: uuid.UUID, session: DbSession, _: StaffUser) -> ExceptionalOut:
    return await _out(session, await _driver(session, driver_id))


@router.post("/drivers/{driver_id}/approve-exceptional", response_model=ExceptionalOut)
async def approve_exceptional(
    driver_id: uuid.UUID, payload: ReasonIn, session: DbSession, redis: RedisDep, admin: ExceptionalManager
) -> ExceptionalOut:
    """**«اعتماد» وُجدت الوثائقُ أو لم توجد** — بسببٍ مكتوب؛ والوسمُ والمهلةُ يبدآن."""
    driver = await _driver(session, driver_id)
    was_approved = driver.status is DriverStatus.APPROVED
    await exceptional_approval.approve(session, driver=driver, actor=admin, reason=payload.reason)
    await session.commit()
    await session.refresh(driver)
    if not was_approved:
        await notifications.publish_driver_approved(session, redis, user_id=driver.user_id)
    return await _out(session, driver)


@router.post("/drivers/{driver_id}/freeze", response_model=ExceptionalOut)
async def freeze_driver(
    driver_id: uuid.UUID, payload: ReasonIn, session: DbSession, redis: RedisDep, admin: ExceptionalManager
) -> ExceptionalOut:
    driver = await _driver(session, driver_id)
    await exceptional_approval.freeze(session, driver=driver, actor=admin, reason=payload.reason)
    await session.commit()
    await session.refresh(driver)
    await notifications.publish_account_frozen(session, redis, user_id=driver.user_id, reason=payload.reason.strip())
    return await _out(session, driver)


@router.post("/drivers/{driver_id}/unfreeze", response_model=ExceptionalOut)
async def unfreeze_driver(
    driver_id: uuid.UUID, payload: ReasonIn, session: DbSession, redis: RedisDep, admin: ExceptionalManager
) -> ExceptionalOut:
    driver = await _driver(session, driver_id)
    await exceptional_approval.unfreeze(session, driver=driver, actor=admin, reason=payload.reason)
    await session.commit()
    await session.refresh(driver)
    await notifications.publish_account_unfrozen(session, redis, user_id=driver.user_id)
    return await _out(session, driver)


@router.put("/drivers/{driver_id}/document-followup", response_model=ExceptionalOut)
async def set_followup(driver_id: uuid.UUID, payload: FollowupIn, session: DbSession, admin: ExceptionalManager) -> ExceptionalOut:
    """**إطفاءُ التذكير لهذا الشخص، أو تمديدُ مهلته** — والتمديدُ من المهلة القائمة أو من الآن أيُّهما أبعد."""
    driver = await _driver(session, driver_id)
    await exceptional_approval.set_followup(
        session, driver=driver, actor=admin, reminders=payload.reminders, extend_days=payload.extend_days
    )
    await session.commit()
    await session.refresh(driver)
    return await _out(session, driver)


@router.post("/drivers/request-documents", response_model=RequestedOut, status_code=status.HTTP_200_OK)
async def request_documents(
    payload: RequestDocumentsIn, session: DbSession, redis: RedisDep, admin: ExceptionalManager
) -> RequestedOut:
    """**«طلب الوثائق»** — إشعارٌ في الصندوق وPush بزرٍّ إلى شاشة الرفع، لفردٍ أو لكلِّ الموسومين."""
    if payload.all_flagged:
        drivers = await exceptional_approval.flagged(session, country=payload.country_code)
    else:
        if not payload.driver_ids:
            raise InvalidInput("اختر كبتناً أو «الكلّ»")
        drivers = list((await session.scalars(select(Driver).where(Driver.id.in_(payload.driver_ids)))).all())
    sent = await exceptional_approval.request_documents(session, redis, drivers=drivers, actor=admin)
    await session.commit()
    return RequestedOut(sent=sent)


@router.get("/document-settings/{country_code}", response_model=DocumentSettingsOut)
async def read_document_settings(country_code: CountryCode, session: DbSession, _: StaffUser) -> DocumentSettingsOut:
    settings = await exceptional_approval.settings_for(session, country_code)
    return DocumentSettingsOut(
        country_code=country_code,
        exceptional_deadline_days=settings.deadline_days,
        exceptional_reminder_days=settings.reminder_days,
        expiry_notice_days=list(settings.expiry_notice_days),
    )


@router.put("/document-settings/{country_code}", response_model=DocumentSettingsOut)
async def save_document_settings(
    country_code: CountryCode, payload: DocumentSettingsIn, session: DbSession, admin: ExceptionalManager
) -> DocumentSettingsOut:
    settings = await exceptional_approval.save_settings(
        session,
        country=country_code,
        deadline_days=payload.exceptional_deadline_days,
        reminder_days=payload.exceptional_reminder_days,
        expiry_notice_days=payload.expiry_notice_days,
        actor=admin,
    )
    await session.commit()
    return DocumentSettingsOut(
        country_code=country_code,
        exceptional_deadline_days=settings.deadline_days,
        exceptional_reminder_days=settings.reminder_days,
        expiry_notice_days=list(settings.expiry_notice_days),
    )


class ExpiringDocumentRow(BaseModel):
    document_id: uuid.UUID
    driver_id: uuid.UUID
    driver_name: str
    doc_type: DocumentType
    doc_label: str
    expires_on: date
    days_left: int
    driver_status: DriverStatus


@router.get("/documents/expiring", response_model=list[ExpiringDocumentRow])
async def list_expiring_documents(
    session: DbSession,
    _: StaffUser,
    country_code: CountryCode,
    days: int = Query(default=30, ge=1, le=120),
) -> list[ExpiringDocumentRow]:
    """**«وثائق تنتهي قريباً»** (البند ٢) — المطلوبةُ وحدَها، والمنتهيةُ التي لم تُستبدل في رأسها. ويومُ الدولة لا يومُ الخادم."""
    today = await country_today(session, country_code)
    return [
        ExpiringDocumentRow(
            document_id=document.id,
            driver_id=driver.id,
            driver_name=user.name,
            doc_type=document.doc_type,
            doc_label=documents.label_for(document.doc_type),
            expires_on=document.expires_on,
            days_left=(document.expires_on - today).days,
            driver_status=driver.status,
        )
        for document, driver, user in await document_expiry.expiring_within(
            session, today=today, country=country_code, days=days
        )
    ]
