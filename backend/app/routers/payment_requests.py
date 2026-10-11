"""نظامُ الدفع الجديد للراكب والكبتن — الطرقُ والطلباتُ والـwebhook الموحّد (SPEC §٧٣-هـ المرحلة ١).

**مطفأً في سوق السائل لا يُفتح طلبٌ ولا تُعرض طريقة** (`payment_requests_enabled`) — والأردنُ وليبيا مطفآن، فلا يتغيّر عليهما شيء.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import anyio
from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core import storage
from app.core.currency import currency_for_country
from app.core.deps import CurrentUser, DbSession, RedisDep
from app.core.exceptions import NotFound
from app.models.enums import PaymentProviderKind, PaymentRequestPurpose, WalletOwnerType
from app.models.payment_request import PaymentProvider, PaymentRequest
from app.schemas.payment_request import (
    MyPaymentRequestOut,
    PaymentCancelIn,
    PaymentMethodOut,
    PaymentMethodsOut,
)
from app.services import cancellation, payment_gateways, payment_requests

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-requests", tags=["payment-requests"])


def method_out(provider: PaymentProvider) -> PaymentMethodOut:
    return PaymentMethodOut(
        id=provider.id,
        kind=provider.kind,
        name=provider.name,
        account_holder=provider.account_holder,
        account_number=provider.account_number,
        bank_name=provider.bank_name,
        instructions=provider.instructions,
        has_qr=provider.qr_image_path is not None,
        requires_receipt=payment_requests.requires_receipt(provider),
    )


def mine_out(request: PaymentRequest) -> MyPaymentRequestOut:
    return MyPaymentRequestOut(
        id=request.id,
        provider_name=request.provider.name,
        kind=request.kind,
        purpose=request.purpose,
        amount=request.amount,
        credited_amount=request.credited_amount,
        currency=request.currency,
        status=request.status,
        reference=request.reference,
        rejection_reason=request.rejection_reason,
        cancel_reason=request.cancel_reason,
        refund_reason=request.refund_reason,
        outcome_note=request.outcome_note,
        created_at=request.created_at,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


@router.get("/methods", response_model=PaymentMethodsOut)
async def list_methods(
    user: CurrentUser,
    session: DbSession,
    purpose: PaymentRequestPurpose = Query(default=PaymentRequestPurpose.WALLET_TOPUP),
) -> PaymentMethodsOut:
    """**طرقُ الدفع المفعَّلة في سوقي لهذا الغرض** — بما يلزم لأدفع: إلى أين، وما يُطلب مني."""
    await payment_requests.require_enabled(session, user.country_code)
    providers = await payment_requests.providers_for(session, user.country_code, purpose)
    return PaymentMethodsOut(
        currency=currency_for_country(user.country_code),
        # **والوسيطُ الآليُّ لا يُعرض قبل أن يُبنى** (المرحلة ٣) — ولا بطاقاتُ الشحن (المرحلة ٢)
        methods=[
            method_out(p)
            for p in providers
            if p.integration is None and p.kind is not PaymentProviderKind.PURCHASE_CODE
        ],
    )


@router.get("/methods/{provider_id}/qr")
async def method_qr(provider_id: uuid.UUID, user: CurrentUser, session: DbSession) -> FileResponse:
    """**صورةُ رمز QR للطريقة** — لمن في سوقها وهي مفعَّلة؛ وما عداه ٤٠٤."""
    await payment_requests.require_enabled(session, user.country_code)
    provider = await payment_requests.available_provider(session, provider_id, user.country_code)
    if provider.qr_image_path is None:
        raise NotFound("لا رمزَ لهذه الطريقة")
    return FileResponse(
        storage.resolve(provider.qr_image_path),
        media_type=provider.qr_content_type or "image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("", response_model=MyPaymentRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    user: CurrentUser,
    session: DbSession,
    provider_id: Annotated[uuid.UUID, Form()],
    purpose: Annotated[PaymentRequestPurpose, Form()],
    amount: Annotated[Decimal, Form(gt=0, max_digits=12, decimal_places=3)],
    reference: Annotated[str | None, Form(max_length=120)] = None,
    plan_id: Annotated[uuid.UUID | None, Form()] = None,
    wallet: Annotated[WalletOwnerType | None, Form()] = None,
    receipt: Annotated[UploadFile | None, File(description="صورةُ الإيصال أو PDF")] = None,
) -> MyPaymentRequestOut:
    """**طلبٌ بعد الدفع** — معلَّقٌ حتى يعتمده موظّفٌ ماليّ؛ **والإيصالُ إجباريٌّ في التحويلات** (§٧٣-هـ/٢).

    **والملفُّ يُحفظ قبل الصفّ ويُحذف إن لم يُكتب** — كرفع الوثائق: ملفٌّ يتيمٌ نفايةٌ تُنظَّف، وصفٌّ يعد بملفٍّ غائبٍ عطلٌ يراه موظّف.
    """
    request_id = uuid.uuid4()
    stored = None
    digest = None
    if receipt is not None:
        stored = await storage.save(receipt, folder=str(request_id))
        digest = await anyio.to_thread.run_sync(_sha256, storage.resolve(stored.relative_path))
    try:
        request = await payment_requests.create(
            session,
            request_id=request_id,
            owner=user,
            provider_id=provider_id,
            purpose=purpose,
            amount=amount,
            reference=reference,
            plan_id=plan_id,
            receipt_path=stored.relative_path if stored else None,
            receipt_content_type=stored.content_type if stored else None,
            receipt_sha256=digest,
            declared=wallet,
        )
        await session.commit()
    except BaseException:
        await session.rollback()
        if stored is not None:
            await storage.delete(stored.relative_path)
        raise
    await session.refresh(request, attribute_names=["provider"])
    return mine_out(request)


@router.get("/me", response_model=list[MyPaymentRequestOut])
async def list_mine(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[MyPaymentRequestOut]:
    rows = await payment_requests.list_for_owner(session, user.id, limit=limit, offset=offset)
    return [mine_out(row) for row in rows]


@router.post("/{request_id}/cancel", response_model=MyPaymentRequestOut)
async def cancel_mine(
    request_id: uuid.UUID, payload: PaymentCancelIn, user: CurrentUser, session: DbSession
) -> MyPaymentRequestOut:
    """**يلغي صاحبُ الطلب طلبَه المعلَّق** — وطلبُ غيره ٤٠٤ لا ٤٠٣."""
    request = await payment_requests.get_request(session, request_id, for_update=True)
    if request.user_id != user.id:
        raise NotFound("طلبُ الدفع غيرُ موجود")
    request = await payment_requests.cancel(
        session, request=request, actor=user, reason=payload.reason, by_owner=True
    )
    await session.commit()
    return mine_out(request)


@router.post("/webhook/{integration}")
async def gateway_webhook(
    integration: str, request: Request, session: DbSession, redis: RedisDep
) -> dict[str, object]:
    """**الـwebhook الموحّد للوسطاء الآليّين** (§٧٣-هـ/١٠) — **التوقيعُ قبل أيِّ قراءة**، ثمّ يطبَّق ما قاله الوسيطُ بالأبواب نفسِها.

    **ومعرّفٌ لا طلبَ له يُسجَّل ولا يُرفض بغير ٢٠٠**: الوسيطُ يعيد ما لم يرَ له ٢٠٠ إلى ما لا نهاية، وإعادتُه لا تجعل المعرّفَ معروفاً.
    """
    gateway = payment_gateways.gateway_for(integration)
    if gateway is None:
        raise NotFound("لا وسيطَ بهذا الاسم")
    body = await request.body()
    events = await gateway.parse_webhook(headers={k.lower(): v for k, v in request.headers.items()}, body=body)
    applied = 0
    owners = []
    for event in events:
        try:
            row = await payment_requests.request_for_external(
                session, integration=integration, external_id=event.external_id
            )
        except NotFound:
            logger.error("إشعارُ وسيط %s لمعرّفٍ لا طلبَ له: %s", integration, event.external_id)
            continue
        before = row.status
        row = await payment_requests.apply_gateway_outcome(
            session, request=row, outcome=event.outcome, amount=event.amount, reason=event.reason
        )
        if row.status is not before:
            applied += 1
            owners.append(row.user_id)
    await session.commit()
    for owner_id in owners:
        from app.models.user import User

        owner = await session.get(User, owner_id)
        if owner is not None:
            await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return {"ok": True, "applied": applied}
