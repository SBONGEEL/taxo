"""**مراجعةُ تحويلات BaridiMob في الجزائر** — صفحةُ المراجع والمالك، وبطاقةُ إعداد المالك، وحسابُ المراجع (SPEC §٨٢-ب).

**ثلاثةُ أبوابٍ بحارسين**:
- الطابورُ والإيصالُ والاعتمادُ والرفض — `TransferReviewer` (المراجعُ والمالك). **والنطاقُ BaridiMob في الجزائر وحدَه**، وما خارجه ٤٠٤.
- الإعدادُ وحسابُ المراجع — `OwnerUser` (المالكُ وحدَه)؛ لا صلاحيةَ من المصفوفة تفتحهما.

**والاعتمادُ بابُ نظام الدفع نفسُه** (`payment_requests.approve`) — قفلُ الصفّ قبل الحال، وقيدٌ واحدٌ بمفتاح الطلب؛ **والمراجعُ لا يغيّر
المبلغ**: يُقيَّد ما ادّعاه صاحبُه بعد أن يطابقه بما وصل.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core import storage
from app.core.currency import currency_for_country
from app.core.deps import DbSession, OwnerUser, RedisDep, TransferReviewer
from app.core.exceptions import NotFound
from app.models.admin_credential import AdminCredential
from app.models.enums import PaymentRequestStatus
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.schemas.payment_request import PaymentReasonIn
from app.schemas.transfers import (
    ReviewerCreateIn,
    ReviewerOut,
    TransferOut,
    TransferSettingsIn,
    TransferSettingsOut,
)
from app.services import cancellation, payment_requests, totp, transfers

router = APIRouter(prefix="/admin/transfers", tags=["admin"])


async def _out(session, rows: list[PaymentRequest]) -> list[TransferOut]:
    ids = {row.user_id for row in rows} | {row.reviewed_by for row in rows if row.reviewed_by}
    people = {u.id: u for u in (await session.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    out = []
    for row in rows:
        owner = people.get(row.user_id)
        reviewer = people.get(row.reviewed_by) if row.reviewed_by else None
        out.append(
            TransferOut(
                id=row.id,
                public_ref=payment_requests.public_ref(row.id),
                country_code=row.country_code,
                currency=row.currency,
                purpose=row.purpose,
                amount=row.amount,
                credited_amount=row.credited_amount,
                status=row.status,
                reference=row.reference,
                transfer_date=row.transfer_date,
                created_at=row.created_at,
                reviewed_at=row.reviewed_at,
                reviewed_by=payment_requests.decided_by(reviewer) if reviewer else None,
                rejection_reason=row.rejection_reason,
                has_receipt=row.receipt_path is not None,
                receipt_content_type=row.receipt_content_type,
                first_name=transfers.first_name(owner.name if owner else None),
                masked_phone=transfers.mask_phone(owner.phone if owner else None, row.country_code),
            )
        )
    return out


@router.get("", response_model=list[TransferOut])
async def list_transfers(
    _reviewer: TransferReviewer,
    session: DbSession,
    status_filter: PaymentRequestStatus | None = Query(default=PaymentRequestStatus.PENDING, alias="status"),
    everything: bool = Query(default=False, alias="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TransferOut]:
    rows = await transfers.queue(session, status=None if everything else status_filter, limit=limit, offset=offset)
    return await _out(session, list(rows))


@router.get("/settings", response_model=TransferSettingsOut)
async def read_settings(_owner: OwnerUser, session: DbSession) -> TransferSettingsOut:
    provider = await transfers.method(session)
    return _settings_out(provider)


def _settings_out(provider) -> TransferSettingsOut:
    return TransferSettingsOut(
        exists=provider is not None,
        configured=transfers.is_configured(provider),
        enabled=bool(provider and provider.enabled),
        account_number=provider.account_number if provider else None,
        account_holder=provider.account_holder if provider else None,
        account_holder_latin=provider.account_holder_latin if provider else None,
        min_amount=provider.min_amount if provider else None,
        max_amount=provider.max_amount if provider else None,
        currency=currency_for_country(transfers.COUNTRY),
    )


@router.put("/settings", response_model=TransferSettingsOut)
async def save_settings(payload: TransferSettingsIn, owner: OwnerUser, session: DbSession) -> TransferSettingsOut:
    provider = await transfers.save_settings(
        session,
        actor=owner,
        account_number=payload.account_number,
        account_holder=payload.account_holder,
        account_holder_latin=payload.account_holder_latin,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        enabled=payload.enabled,
    )
    await session.commit()
    await session.refresh(provider)
    return _settings_out(provider)


@router.get("/reviewers", response_model=list[ReviewerOut])
async def list_reviewers(_owner: OwnerUser, session: DbSession) -> list[ReviewerOut]:
    out = []
    for user in await transfers.reviewers(session):
        credential = await session.scalar(select(AdminCredential).where(AdminCredential.user_id == user.id))
        out.append(
            ReviewerOut(
                id=user.id,
                name=user.name,
                username=credential.username if credential else None,
                is_blocked=user.is_blocked,
                has_factor=await totp.has_confirmed_factor(session, user.id),
                must_change_password=bool(credential and credential.must_change_password),
                created_at=user.created_at,
            )
        )
    return out


@router.post("/reviewers", response_model=ReviewerOut, status_code=status.HTTP_201_CREATED)
async def create_reviewer(
    payload: ReviewerCreateIn, owner: OwnerUser, session: DbSession, redis: RedisDep
) -> ReviewerOut:
    """**ينشئه المالكُ بيده** — الاسمُ واسمُ الدخول وكلمةٌ مؤقّتة؛ والعاملُ الثاني يُسجَّل عند أوّل دخول قبل أيِّ صفحة."""
    user = await transfers.create_reviewer(
        session, redis, actor=owner, name=payload.name, username=payload.username, password=payload.password
    )
    await session.commit()
    credential = await session.scalar(select(AdminCredential).where(AdminCredential.user_id == user.id))
    return ReviewerOut(
        id=user.id, name=user.name, username=credential.username if credential else None, is_blocked=False,
        has_factor=False, must_change_password=True, created_at=user.created_at,
    )


@router.get("/{request_id}/receipt")
async def transfer_receipt(request_id: uuid.UUID, _reviewer: TransferReviewer, session: DbSession) -> FileResponse:
    """**الإيصالُ للمراجع والمالك وحدَهما** — من مجلّدٍ خاصّ عبر الجلسة، **لا رابطَ عامّاً**، ولا يُخبَّأ."""
    row = await transfers.scoped(session, request_id)
    if row.receipt_path is None:
        raise NotFound("لا إيصالَ لهذا الطلب")
    return FileResponse(
        storage.resolve(row.receipt_path),
        media_type=row.receipt_content_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/{request_id}/approve", response_model=TransferOut)
async def approve_transfer(
    request_id: uuid.UUID, reviewer: TransferReviewer, session: DbSession, redis: RedisDep
) -> TransferOut:
    """**اعتمادٌ واحدٌ يكفي** — من المراجع أو المالك؛ واعتمادان متزامنان يمرّ أحدُهما ويُردّ الآخرُ ٤٠٩ (قفلُ الصفّ قبل الحال)."""
    await transfers.scoped(session, request_id)
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.approve(session, request=row, actor=reviewer, credited=None)
    await session.commit()
    owner = await session.get(User, row.user_id)
    if owner is not None:
        await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return (await _out(session, [row]))[0]


@router.post("/{request_id}/reject", response_model=TransferOut)
async def reject_transfer(
    request_id: uuid.UUID, payload: PaymentReasonIn, reviewer: TransferReviewer, session: DbSession
) -> TransferOut:
    await transfers.scoped(session, request_id)
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.reject(session, request=row, actor=reviewer, reason=payload.reason)
    await session.commit()
    return (await _out(session, [row]))[0]

