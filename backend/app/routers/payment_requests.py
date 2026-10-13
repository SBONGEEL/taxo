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

import html

import anyio
from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.core import storage
from app.core.config import settings
from app.core.currency import currency_for_country
from app.core.deps import CurrentUser, DbSession, RedisDep
from app.core.exceptions import NotFound
from app.models.enums import PaymentRequestPurpose, WalletOwnerType
from app.models.payment_request import PayMethod, PaymentRequest
from app.schemas.payment_request import (
    MyPaymentRequestOut,
    PaymentCancelIn,
    PaymentCheckoutIn,
    PaymentCheckoutOut,
    PaymentMethodOut,
    PaymentMethodsOut,
)
from app.services import cancellation, payment_gateways, payment_requests

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-requests", tags=["payment-requests"])


def method_out(provider: PayMethod, *, test_mode: bool = False) -> PaymentMethodOut:
    return PaymentMethodOut(
        test_mode=test_mode,
        fee_payer=provider.fee_bearer if provider.integration is not None else None,
        id=provider.id,
        kind=provider.kind,
        name=provider.name,
        account_holder=provider.account_holder,
        account_number=provider.account_number,
        bank_name=provider.bank_name,
        instructions=provider.instructions,
        has_qr=provider.qr_image_path is not None,
        requires_receipt=payment_requests.requires_receipt(provider),
        gateway=provider.integration is not None,
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
    shown: list[PaymentMethodOut] = []
    for provider in providers:
        if provider.integration is None:
            shown.append(method_out(provider))
            continue
        # **الوسيطُ بوضع عقده** (§٧٤-ط/٥): وضعُ التجربة لحساب التجربة وحدَه، والحيُّ لغيره — **وما لا يُفتح لا يُعرض**؛
        # وعقدٌ غائبٌ يُسقط الطريقةَ من القائمة كما يُسقطها الدفعُ نفسُه
        try:
            gateway = await payment_gateways.gateway_for(session, provider.integration, user.country_code)
        except payment_gateways.GatewayUnavailable:
            continue
        test_mode = bool(getattr(gateway, "test_mode", False))
        if test_mode != bool(user.is_test):
            continue
        shown.append(method_out(provider, test_mode=test_mode))
    return PaymentMethodsOut(
        currency=currency_for_country(user.country_code),
        # **كلُّ مفعَّلٍ يُعرض** — اليدويُّ يُراجَع، والوسيطُ الآليُّ يُدفع في صفحته (المرحلة ٣)، وبطاقاتُ TAXO تُدخل برمزها
        methods=shown,
        topup_choices=await payment_requests.topup_choices(session, user.country_code),
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


@router.post("/checkout", response_model=PaymentCheckoutOut, status_code=status.HTTP_201_CREATED)
async def open_checkout(payload: PaymentCheckoutIn, user: CurrentUser, session: DbSession) -> PaymentCheckoutOut:
    """**صفحةُ دفعٍ عند وسيطٍ آليّ** (المرحلة ٣) — يفتحها التطبيقُ ثمّ يعود إلى صفحة العودة ويسأل عن الحال (`/refresh`).

    **والتطبيقُ الذي فتحها يُعرف من المحفظة المعلَنة** — الاشتراكُ والمحفظةُ الكبتنُ يعودان إلى تطبيق الكبتن، وما عداهما إلى الراكب.
    """
    opened_from = (
        "driver"
        if payload.purpose is PaymentRequestPurpose.SUBSCRIPTION or payload.wallet is WalletOwnerType.DRIVER
        else "rider"
    )
    request, url = await payment_requests.start_checkout(
        session,
        owner=user,
        provider_id=payload.provider_id,
        purpose=payload.purpose,
        amount=payload.amount,
        plan_id=payload.plan_id,
        declared=payload.wallet,
        opened_from=opened_from,
    )
    await session.commit()
    await session.refresh(request, attribute_names=["provider"])
    fee = request.fee_amount if request.fee_payer == "user" and request.fee_amount else None
    return PaymentCheckoutOut(
        request=mine_out(request),
        checkout_url=url,
        currency=request.currency,
        fee_amount=fee,
        total_amount=(request.amount + fee) if fee is not None else None,
    )


@router.post("/{request_id}/refresh", response_model=MyPaymentRequestOut)
async def refresh_mine(request_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> MyPaymentRequestOut:
    """**يسأل الوسيطَ عن طلبي المعلَّق** — صفحةُ العودة تناديه؛ وطلبُ غيري ٤٠٤ لا ٤٠٣."""
    row = await payment_requests.get_request(session, request_id)
    if row.user_id != user.id:
        raise NotFound("طلبُ الدفع غيرُ موجود")
    before = row.status
    row = await payment_requests.refresh(session, request_id=request_id)
    await session.commit()
    if row.status is not before:
        await cancellation.announce_settled_for_debtor(session, redis, user=user)
    await session.refresh(row, attribute_names=["provider"])
    return mine_out(row)


@router.post("/webhook/{integration}")
async def gateway_webhook(
    integration: str, request: Request, session: DbSession, redis: RedisDep
) -> dict[str, object]:
    """**الـwebhook الموحّد للوسطاء الآليّين** (§٧٣-هـ/١٠) — **الحمولةُ إشارةُ استيقاظٍ لا مصدرُ حقيقة** (قاعدةُ `card_gateway`).

    التوقيعُ يُتحقَّق حيث يوثّقه الوسيط، **على كلِّ عقدٍ مفعَّلٍ له** (الإشعارُ لا يقول سوقَه)؛ ثمّ **يُسأل الوسيطُ مباشرةً** عن كلِّ معرّف
    (`refresh`) — قبل القفل — ويُطبَّق جوابُه. **ومعرّفٌ لا طلبَ له يُسجَّل ولا يُرفض بغير ٢٠٠**: الوسيطُ يعيد ما لم يرَ له ٢٠٠.
    """
    gateways = await payment_gateways.webhook_gateways(session, integration)
    if not gateways:
        raise NotFound("لا وسيطَ مفعَّلٌ بهذا الاسم")
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    ids: list[str] | None = None
    signed = False
    for gateway in gateways:
        try:
            ids = gateway.webhook_ids(headers, body)
            # **«موقَّعٌ» لمن يوقّع إشعارَه** (Chargily) — وSofizPay لا توقيعَ موثَّقاً له، فإشعارُه يوقظ ولا يشهد
            signed = bool(getattr(gateway, "confirms_by_webhook", False))
            break
        except payment_gateways.WebhookSignatureInvalid:
            continue
    if ids is None:
        raise payment_gateways.WebhookSignatureInvalid()

    applied = 0
    owners = []
    for external_id in ids:
        row = await payment_requests.find_external(session, integration=integration, external_id=external_id)
        if row is None:
            logger.error("إشعارُ وسيط %s لمعرّفٍ لا طلبَ له: %s", integration, external_id)
            continue
        # **من إشعارٍ تحقّق توقيعُه** — وهو وحدَه ما يقيِّد «دُفع» عند Chargily (§٧٤-ط/٥)
        row, settled = await payment_requests.settle_from_gateway(session, request_id=row.id, signed=signed)
        if settled:
            applied += 1
            owners.append(row.user_id)
    await session.commit()
    for owner_id in owners:
        from app.models.user import User

        owner = await session.get(User, owner_id)
        if owner is not None:
            await cancellation.announce_settled_for_debtor(session, redis, user=owner)
    return {"ok": True, "applied": applied}


# ------------------------------------------------------------------ صفحةُ الوسيط الوهميّ (التطوير والاختبار وحدَهما)


def _require_mock_allowed() -> None:
    if settings.is_production:
        raise NotFound()


@router.get("/mock/{external_id}", response_class=HTMLResponse, include_in_schema=False)
async def mock_page(external_id: str) -> HTMLResponse:
    """**«صفحةُ الدفع» الوهميّة** — زرّان، **وممنوعةٌ في الإنتاج** (`404`)."""
    _require_mock_allowed()
    safe = html.escape(external_id)
    return HTMLResponse(
        "<!doctype html><html lang=ar dir=rtl><meta charset=utf-8><title>وسيطٌ وهميّ</title>"
        f"<body style='font-family:sans-serif;padding:24px'><h1>وسيطٌ وهميّ</h1><p dir=ltr>{safe}</p>"
        f"<form method=post action='{safe}/paid'><button style='padding:12px 24px'>نجح الدفع</button></form><br>"
        f"<form method=post action='{safe}/failed'><button style='padding:12px 24px'>فشل الدفع</button></form></body></html>"
    )


@router.post("/mock/{external_id}/{outcome}", include_in_schema=False)
async def mock_settle(external_id: str, outcome: str) -> RedirectResponse:
    _require_mock_allowed()
    if outcome not in ("paid", "failed"):
        raise NotFound()
    from app.services.payment_gateways import mock

    back = await mock.return_url_of(external_id)
    await mock.settle(external_id, outcome)
    return RedirectResponse(back or "/", status_code=303)
