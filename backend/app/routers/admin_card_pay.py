"""**«الدفع بالبطاقة المصرفية» في اللوحة** — شاشةٌ واحدةٌ لوسيط البطاقة (NOWPayments، أمرُ المالك ٢٠٢٦-١١-١١).

ما تجمعه: **المفتاحُ الرئيسيُّ لكلِّ دولة** (الأردنُ وحدَه يشتعل؛ الجزائرُ وليبيا مقفلتان بالشيفرة)، **وحالُ العقد** (أأُدخل المفتاحان —
بلا قيمهما)، **وحدّا الدفعة**، **وسقفُ مجموع اليوم وما بلغه**، **وقائمةُ هذه الدفعات** بحالها ومبلغها بالدينار ومرجع NOWPayments وما
وصل منها.

**ولا بابَ كتابةٍ جديدٌ للمفتاح ولا للحدّين**: المفتاحُ يُكتب بـ`PUT /admin/feature-flags` (وفيه القفلُ بالدولة)، والحدّان بـ
`PATCH /admin/payment-methods/{id}` (وفيه التدقيق) — **فبابٌ ثانٍ يكتب الشيءَ نفسَه يفترق عن الأوّل يوماً**. والجديدُ هنا القراءةُ،
وسقفُ اليوم وسعرُ الصرف (حقلان في العقد لا يُكتبان إلا معه).
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import DbSession, ListReader, SettingsWriter
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode, FeatureKey
from app.models.payment_request import PayMethod, PaymentRequest
from app.routers.admin_payment_requests import _rows_out, method_admin_out
from app.schemas.card_pay import CardPayCountryOut, CardPayLimitsIn, CardPayLiveOut, CardPayOverviewOut
from app.services import audit, payment_gateways, payment_requests, settings_service
from app.services.payment_gateways import GatewayError, GatewayUnavailable
from app.services.pricing import as_money
from app.services.providers import credentials as credentials_service

router = APIRouter(prefix="/admin/card-pay", tags=["admin"])

INTEGRATION = "nowpay"
#: **سوقُ الوسيط** — الأردنُ وحدَه (`SWITCH_COUNTRIES`)
MARKET = CountryCode.JO


async def _method(session) -> PayMethod | None:
    return await session.scalar(
        select(PayMethod).where(PayMethod.integration == INTEGRATION, PayMethod.country_code == MARKET)
    )


async def _gateway(session):
    try:
        return await payment_gateways.gateway_for(session, INTEGRATION, MARKET)
    except GatewayUnavailable:
        return None


@router.get("", response_model=CardPayOverviewOut)
async def overview(
    _reader: ListReader,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CardPayOverviewOut:
    """**كلُّ ما يلزم المالكَ في مكانٍ واحد** — ولا قيمةَ سرٍّ فيه: «أُدخل المفتاحان» نعم أو لا."""
    allowed = payment_gateways.SWITCH_COUNTRIES[INTEGRATION]
    countries = [
        CardPayCountryOut(
            country_code=country,
            locked=country not in allowed,
            enabled=country in allowed
            and await settings_service.is_feature_enabled(session, country, FeatureKey.NOWPAY_CARD_ENABLED),
        )
        for country in CountryCode
    ]
    stored = await credentials_service.get_values(
        session, payment_gateways.PROVIDER_KEYS[INTEGRATION], MARKET, active_only=False
    )
    contract_active = await credentials_service.provider_is_active(
        session, payment_gateways.PROVIDER_KEYS[INTEGRATION], MARKET
    )
    gateway = await _gateway(session)
    method = await _method(session)
    rows: list[PaymentRequest] = []
    if method is not None:
        rows = list(
            (
                await session.scalars(
                    select(PaymentRequest)
                    .where(PaymentRequest.provider_id == method.id)
                    .order_by(PaymentRequest.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
    return CardPayOverviewOut(
        countries=countries,
        keys_entered=bool(stored and stored.get("api_key") and stored.get("ipn_secret")),
        contract_active=contract_active,
        ready=gateway is not None,
        sandbox=bool(getattr(gateway, "test_mode", False)),
        usd_per_jod=getattr(gateway, "usd_per_jod", None),
        daily_cap=None if getattr(gateway, "daily_cap", None) is None else as_money(gateway.daily_cap),
        today_total=await payment_requests.daily_total(session, integration=INTEGRATION, country=MARKET),
        webhook_url=payment_gateways.webhook_url(INTEGRATION),
        partner=getattr(gateway, "partner_name", None),
        partner_fee=getattr(gateway, "partner_fee", None),
        method=method_admin_out(method) if method is not None else None,
        requests=await _rows_out(session, rows),
    )


@router.put("/limits", response_model=CardPayOverviewOut)
async def update_limits(payload: CardPayLimitsIn, admin: SettingsWriter, session: DbSession) -> CardPayOverviewOut:
    """**حدّا الدفعة الواحدة، وسقفُ مجموع اليوم، وسعرُ الصرف** — النموذجُ كاملاً في كلِّ حفظ، و`null` «بلا حدّ» أو «الأصل».

    **والحدّان على صفِّ الطريقة** (يقرؤهما `_prepare` لكلِّ طريقة) ويُدقَّقان بقبلهما وبعدهما؛ **والسقفُ والسعرُ حقلان في العقد** فلا
    يُكتبان قبل أن يُدخل المالكُ مفتاحَيه — عقدٌ بلا مفتاحٍ لا يُنشأ من هنا."""
    if payload.min_amount is not None and payload.max_amount is not None and payload.min_amount > payload.max_amount:
        raise InvalidInput("الحدُّ الأدنى أكبرُ من الأعلى", field="min_amount")
    method = await _method(session)
    if method is None:
        raise NotFound("لا طريقةَ دفعٍ بالبطاقة في الأردن")
    method = await payment_requests.get_provider(session, method.id, for_update=True)
    changes = audit.apply_changes(
        method,
        {
            "min_amount": None if payload.min_amount is None else as_money(payload.min_amount),
            "max_amount": None if payload.max_amount is None else as_money(payload.max_amount),
        },
    )
    if changes:
        await audit.record(
            session,
            actor=admin,
            action=AuditAction.UPDATE,
            entity_type="payment_provider",
            entity_id=method.id,
            changes=changes,
        )
    key = payment_gateways.PROVIDER_KEYS[INTEGRATION]
    stored = await credentials_service.get_values(session, key, MARKET, active_only=False)
    if stored is None:
        if payload.daily_cap is not None or payload.usd_per_jod is not None:
            raise InvalidInput("أدخل مفتاحَي NOWPayments في «العقود» أوّلاً — السقفُ والسعرُ يُحفظان مع العقد")
    else:
        await credentials_service.upsert(
            session,
            provider_key=key,
            country_code=MARKET,
            values={
                "daily_cap": "" if payload.daily_cap is None else str(payload.daily_cap),
                "usd_per_jod": "" if payload.usd_per_jod is None else str(payload.usd_per_jod),
            },
            actor=admin,
        )
    await session.commit()
    return await overview(admin, session, limit=50, offset=0)


@router.get("/payments/{request_id}/live", response_model=CardPayLiveOut)
async def live_status(request_id: uuid.UUID, _reader: ListReader, session: DbSession) -> CardPayLiveOut:
    """**ما يقوله NOWPayments الآن عن دفعة** — الحالُ وما دُفع وما وصل حسابَ المالك بالأصل الرقميّ. **قراءةٌ لا تكتب شيئاً**: التسويةُ
    مسارُها الإشعارُ والمطابقةُ الدوريّة."""
    request = await session.get(PaymentRequest, request_id)
    method = await _method(session)
    if request is None or method is None or request.provider_id != method.id or not request.external_id:
        raise NotFound("لا دفعةَ بطاقةٍ بهذا المعرّف")
    gateway = await _gateway(session)
    if gateway is None:
        raise InvalidInput("عقدُ NOWPayments غيرُ مفعَّل — لا يُسأل")
    try:
        details = await gateway.details(request.external_id)  # type: ignore[attr-defined]
    except GatewayError as exc:
        raise InvalidInput(f"لم يُجب NOWPayments: {exc}") from exc
    return CardPayLiveOut(external_id=request.external_id, **details)
