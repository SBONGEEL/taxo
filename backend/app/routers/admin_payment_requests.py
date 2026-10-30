"""نظامُ الدفع الجديد في اللوحة — طرقُ الدفع لكلِّ دولة، وطابورُ الموظّف الماليّ (SPEC §٧٣-هـ المرحلة ١).

**وصلاحيتان لا واحدة** (§٧٣-هـ/١١): **الاعتمادُ والرفضُ والردُّ والإلغاء `finance.manage`**، **وتحريرُ الطرق — أرقامُ RIP والحسابات وصورةُ
QR — `settings.write`**: تبديلُ رقم الحساب أخطرُ بابٍ في النظام، فلا يملكه من يعتمد الطلبات وحدَه، **وكلُّ تغييرٍ فيه يُدقَّق بقبله وبعده**.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import storage
from app.core.deps import DbSession, FinanceManager, ListReader, OwnerUser, RedisDep, SettingsWriter
from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode, PaymentRequestStatus
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.user import User
from app.schemas.payment_request import (
    AdminPaymentMethodCreate,
    AdminPaymentMethodOut,
    AdminPaymentMethodUpdate,
    AdminPaymentRequestOut,
    PaymentApproveIn,
    PaymentReasonIn,
)
from app.services import audit, cancellation, payment_breaker, payment_requests, transfers

router = APIRouter(prefix="/admin", tags=["admin"])

#: صورةُ الرمز — PNG أو JPEG أو WebP، **لا PDF**: تُرسم في التطبيق صورةً
_QR_TYPES = ("image/png", "image/jpeg", "image/webp")


def method_admin_out(provider: PayMethod, streak: int = 0) -> AdminPaymentMethodOut:
    return AdminPaymentMethodOut(
        id=provider.id,
        country_code=provider.country_code,
        kind=provider.kind,
        code=provider.code,
        name=provider.name,
        integration=provider.integration,
        enabled=provider.enabled,
        for_topup=provider.for_topup,
        for_subscription=provider.for_subscription,
        account_holder=provider.account_holder,
        account_number=provider.account_number,
        bank_name=provider.bank_name,
        instructions=provider.instructions,
        has_qr=provider.qr_image_path is not None,
        sort_order=provider.sort_order,
        fee_bearer=provider.fee_bearer,
        updated_at=provider.updated_at,
        account_holder_latin=provider.account_holder_latin,
        min_amount=provider.min_amount,
        max_amount=provider.max_amount,
        hidden_reason=provider.hidden_reason,
        hidden_at=provider.hidden_at,
        hidden_auto=provider.hidden_auto,
        failure_streak=streak,
    )


def _require_destination(provider: PayMethod) -> None:
    """**لا طريقةَ تحويلٍ مفعَّلةً بلا حسابٍ يستقبل** (قرارُ المالك ٢٠٢٦-٠٨-٢٩ في كليك، حرفاً): شاشةٌ تطلب تحويلاً ولا تقول إلى أين
    **تُنتج حوالةً ضائعة**، وهي أسوأُ من غياب الطريقة."""
    if (
        provider.enabled
        and payment_requests.requires_receipt(provider)
        and not (provider.account_number or "").strip()
        and provider.qr_image_path is None
    ):
        raise InvalidInput("طريقةُ تحويلٍ بلا رقمِ حسابٍ ولا رمزِ QR لا تُفعَّل", field="enabled")


async def _require_gateway_ready(session, provider: PayMethod) -> None:
    """**الوسيطُ الآليُّ لا يُفعَّل بلا عقده في سوقه** — طريقةٌ تُعرض ثمّ تردّ «غيرُ متاح» عند الضغط بابٌ بلا زرٍّ مقلوباً؛ **ومن يحمل
    الرسوم ما يقبله الوسيطُ بوثائقه** (`FEE_BEARERS`)، **والطريقةُ اليدويّةُ لا رسومَ وسيطٍ لها** (TAXO افتراضاً).
    """
    from app.services import payment_gateways
    from app.services.providers import credentials as credentials_service

    if provider.integration is None:
        if provider.fee_bearer != "taxo":
            raise InvalidInput("الطريقةُ اليدويّةُ لا رسومَ وسيطٍ لها", field="fee_bearer")
        return
    if provider.fee_bearer not in payment_gateways.FEE_BEARERS.get(provider.integration, frozenset()):
        raise InvalidInput("هذا الوسيطُ لا يوثّق تحميلَ رسومه بهذا الشكل — اتركها على TAXO", field="fee_bearer")
    if provider.enabled and not await credentials_service.provider_is_active(
        session, payment_gateways.PROVIDER_KEYS[provider.integration], provider.country_code
    ):
        raise InvalidInput("فعّل عقدَ الوسيط لهذه الدولة في «عقود مزوّدي API» أوّلاً", field="enabled")


@router.get("/payment-methods", response_model=list[AdminPaymentMethodOut])
async def list_methods(
    _reader: ListReader,
    session: DbSession,
    country: CountryCode | None = Query(default=None),
) -> list[AdminPaymentMethodOut]:
    rows = await payment_requests.all_providers(session, country)
    return [
        method_admin_out(p, await payment_breaker.failure_streak(session, p.id) if p.integration else 0) for p in rows
    ]


@router.post("/payment-methods", response_model=AdminPaymentMethodOut, status_code=status.HTTP_201_CREATED)
async def create_method(
    payload: AdminPaymentMethodCreate, admin: SettingsWriter, session: DbSession
) -> AdminPaymentMethodOut:
    provider = PayMethod(**payload.model_dump(mode="python"))
    transfers.require_owner_for(provider, admin)
    provider.fee_bearer = payload.fee_bearer.value
    _require_destination(provider)
    await _require_gateway_ready(session, provider)
    session.add(provider)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("هذا المعرّفُ مستعملٌ لطريقةٍ أخرى في السوق نفسِه") from exc
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="payment_provider",
        entity_id=provider.id,
        details=payload.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(provider)
    return method_admin_out(provider)


@router.patch("/payment-methods/{provider_id}", response_model=AdminPaymentMethodOut)
async def update_method(
    provider_id: uuid.UUID, payload: AdminPaymentMethodUpdate, admin: SettingsWriter, session: DbSession
) -> AdminPaymentMethodOut:
    """**يُدقَّق كلُّ تغييرٍ بقبله وبعده** — ورقمُ الحساب أوّلُها."""
    provider = await payment_requests.get_provider(session, provider_id, for_update=True)
    transfers.require_owner_for(provider, admin)
    fields = payload.model_dump(exclude_unset=True)
    # **مخفيّةٌ بسببٍ مكتوب لا تُفعَّل من هنا** (SPEC §٨٧/١) — زرُّ «إعادة التشغيل» للمالك وحدَه
    payment_breaker.require_not_hidden(provider, enabling=bool(fields.get("enabled")) and not provider.enabled)
    if "fee_bearer" in fields and fields["fee_bearer"] is not None:
        fields["fee_bearer"] = str(fields["fee_bearer"].value if hasattr(fields["fee_bearer"], "value") else fields["fee_bearer"])
    changes = audit.apply_changes(provider, fields)
    _require_destination(provider)
    await _require_gateway_ready(session, provider)
    if changes:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="payment_provider",
            entity_id=provider.id,
            changes=changes,
        )
    await session.commit()
    await session.refresh(provider)
    return method_admin_out(provider)


@router.post("/payment-methods/{provider_id}/hide", response_model=AdminPaymentMethodOut)
async def hide_method(
    provider_id: uuid.UUID, payload: PaymentReasonIn, owner: OwnerUser, session: DbSession
) -> AdminPaymentMethodOut:
    """**المالكُ يُخفي طريقةً بسببٍ مكتوب** (SPEC §٨٧/١) — فلا يعيدها غيرُه، ويرى الدافعُ لافتةَ البدائل."""
    provider = await payment_requests.get_provider(session, provider_id, for_update=True)
    await payment_breaker.hide(session, provider=provider, actor=owner, reason=payload.reason)
    await session.commit()
    await session.refresh(provider)
    return method_admin_out(provider)


@router.post("/payment-methods/{provider_id}/restore", response_model=AdminPaymentMethodOut)
async def restore_method(
    provider_id: uuid.UUID, payload: PaymentReasonIn, owner: OwnerUser, session: DbSession
) -> AdminPaymentMethodOut:
    """**«إعادة التشغيل» — المالكُ وحدَه، بسببٍ ووقت** (SPEC §٨٧/١)؛ وحرّاسُ التفعيل نفسُها (العقدُ والحساب) تُسأل."""
    provider = await payment_requests.get_provider(session, provider_id, for_update=True)
    await payment_breaker.restore(session, provider=provider, actor=owner, reason=payload.reason)
    _require_destination(provider)
    await _require_gateway_ready(session, provider)
    await session.commit()
    await session.refresh(provider)
    return method_admin_out(provider)


@router.put("/payment-methods/{provider_id}/qr", response_model=AdminPaymentMethodOut)
async def upload_method_qr(
    provider_id: uuid.UUID,
    admin: SettingsWriter,
    session: DbSession,
    file: Annotated[UploadFile, File(description="صورةُ رمز QR")],
) -> AdminPaymentMethodOut:
    """**يرفع صورةَ رمز QR للطريقة** — `PUT` لأنها إحلال، والقديمةُ تُحذف بعد الـcommit لا قبله (قاعدةُ رفع الوثائق)."""
    provider = await payment_requests.get_provider(session, provider_id, for_update=True)
    transfers.require_owner_for(provider, admin)
    stored = await storage.save(file, folder=str(provider.id))
    if stored.content_type not in _QR_TYPES:
        await storage.delete(stored.relative_path)
        raise InvalidInput("رمزُ QR صورةٌ (PNG أو JPEG أو WebP) لا PDF", field="file")
    superseded = provider.qr_image_path
    provider.qr_image_path = stored.relative_path
    provider.qr_content_type = stored.content_type
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="payment_provider",
        entity_id=provider.id,
        details={"fields": ["qr_image_path"]},
    )
    await session.commit()
    if superseded:
        await storage.delete(superseded)
    await session.refresh(provider)
    return method_admin_out(provider)


@router.get("/payment-methods/{provider_id}/qr")
async def method_qr(provider_id: uuid.UUID, _reader: ListReader, session: DbSession) -> FileResponse:
    provider = await payment_requests.get_provider(session, provider_id)
    if provider.qr_image_path is None:
        raise NotFound("لا رمزَ لهذه الطريقة")
    return FileResponse(
        storage.resolve(provider.qr_image_path),
        media_type=provider.qr_content_type or "image/png",
        headers={"Cache-Control": "private, no-store"},
    )


# ------------------------------------------------------------------ طابورُ الموظّف الماليّ


async def _rows_out(session, rows: list[PaymentRequest]) -> list[AdminPaymentRequestOut]:
    owners = {
        user.id: user
        for user in (
            await session.scalars(select(User).where(User.id.in_({row.user_id for row in rows})))
        ).all()
    } if rows else {}
    out = []
    for row in rows:
        owner = owners.get(row.user_id)
        out.append(
            AdminPaymentRequestOut(
                id=row.id,
                user_id=row.user_id,
                user_name=owner.name if owner else None,
                user_phone=owner.phone if owner else None,
                owner_type=row.owner_type,
                country_code=row.country_code,
                currency=row.currency,
                provider_id=row.provider_id,
                provider_name=row.provider.name,
                kind=row.kind,
                purpose=row.purpose,
                plan_id=row.plan_id,
                amount=row.amount,
                credited_amount=row.credited_amount,
                status=row.status,
                reference=row.reference,
                external_id=row.external_id,
                has_receipt=row.receipt_path is not None,
                receipt_content_type=row.receipt_content_type,
                rejection_reason=row.rejection_reason,
                cancel_reason=row.cancel_reason,
                refund_reason=row.refund_reason,
                outcome_note=row.outcome_note,
                gateway_code=row.gateway_code,
                gateway_message=row.gateway_message,
                transaction_id=row.transaction_id,
                subscription_id=row.subscription_id,
                reviewed_at=row.reviewed_at,
                created_at=row.created_at,
                transfer_date=row.transfer_date,
                public_ref=payment_requests.public_ref(row.id),
            )
        )
    return out


async def _one_out(session, row: PaymentRequest) -> AdminPaymentRequestOut:
    return (await _rows_out(session, [row]))[0]


@router.get("/payment-requests", response_model=list[AdminPaymentRequestOut])
async def list_requests(
    _reader: ListReader,
    session: DbSession,
    status_filter: PaymentRequestStatus | None = Query(default=None, alias="status"),
    country: CountryCode | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120, description="اسمُ صاحبه أو رقمُه أو مرجعُ التحويل"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminPaymentRequestOut]:
    rows = await payment_requests.list_all(
        session, status=status_filter, country=country, q=q, limit=limit, offset=offset
    )
    return await _rows_out(session, list(rows))


@router.get("/payment-requests/{request_id}/receipt")
async def request_receipt(request_id: uuid.UUID, _staff: FinanceManager, session: DbSession) -> FileResponse:
    """**صورةُ الإيصال** — للموظّف الماليّ وحدَه: فيها حسابُ صاحب الدفعة واسمُه، فلا تُفتح بصلاحية قراءة."""
    row = await payment_requests.get_request(session, request_id)
    if row.receipt_path is None:
        raise NotFound("لا إيصالَ لهذا الطلب")
    return FileResponse(
        storage.resolve(row.receipt_path),
        media_type=row.receipt_content_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/payment-requests/{request_id}/approve", response_model=AdminPaymentRequestOut)
async def approve_request(
    request_id: uuid.UUID, payload: PaymentApproveIn, admin: FinanceManager, session: DbSession, redis: RedisDep
) -> AdminPaymentRequestOut:
    """**الاعتماد → الرصيدُ يتحرّك الآن** — بمبلغ الموظّف كما قرأه في كشفه (قرارُ المالك ٢٠٢٦-٠٨-٢٩)."""
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.approve(session, request=row, actor=admin, credited=payload.credited_amount)
    await session.commit()
    owner = await session.get(User, row.user_id)
    if owner is not None:
        # **بعد الـcommit** كبقية البثّ — شحنٌ اكتمل قد يكون سدّد رسمَ إلغاءٍ معلّقاً
        await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return await _one_out(session, row)


@router.post("/payment-requests/{request_id}/reject", response_model=AdminPaymentRequestOut)
async def reject_request(
    request_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession
) -> AdminPaymentRequestOut:
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.reject(session, request=row, actor=admin, reason=payload.reason)
    await session.commit()
    return await _one_out(session, row)


@router.post("/payment-requests/{request_id}/refund", response_model=AdminPaymentRequestOut)
async def refund_request(
    request_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession
) -> AdminPaymentRequestOut:
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.refund(session, request=row, actor=admin, reason=payload.reason)
    await session.commit()
    return await _one_out(session, row)


@router.post("/payment-requests/{request_id}/cancel", response_model=AdminPaymentRequestOut)
async def cancel_request(
    request_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession
) -> AdminPaymentRequestOut:
    row = await payment_requests.get_request(session, request_id, for_update=True)
    row = await payment_requests.cancel(session, request=row, actor=admin, reason=payload.reason, by_owner=False)
    await session.commit()
    return await _one_out(session, row)
