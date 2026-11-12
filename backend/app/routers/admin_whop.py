"""**«الدفع بالبطاقة عبر Whop» في اللوحة** — شاشةٌ واحدةٌ للمالك (أمرُ المالك ٢٠٢٦-١١-١٣).

ما تجمعه: **المفاتيحُ الثلاثة للأردن** (دفعُ الكباتن · شحنُ محفظة الراكب · دفعُ الرحلة بالبطاقة) — والجزائرُ وليبيا مقفلتان بالشيفرة،
**وحالُ العقد** (أأُدخلت القيمُ الثلاث — بلا قيمها)، **وطريقتا الدفع بحدّيهما** (الكبتنُ والراكب)، **وقائمةُ دفعات Whop** بنوعها
وحالها ومبلغها ومرجع Whop وما قاله Whop عنها.

**والمفاتيحُ بـ`PUT /admin/settings/feature-flags`** (وفيه القفلُ بالدولة) لا ببابٍ ثانٍ يكتب الشيءَ نفسَه فيفترق عنه يوماً.
**والكتابةُ الجديدةُ واحدة**: حدّا كلِّ طريقة (`PUT /admin/whop/methods/{id}/limits`) — كبابِ حدَّي NOWPayments، مدقَّقاً بقبله وبعده،
**ولا تمسّ إلا صفَّي Whop في الأردن**.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import DbSession, ListReader, SettingsWriter
from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.payment_request import PayMethod, PaymentRequest
from app.routers.admin_payment_requests import _rows_out, method_admin_out
from app.schemas.whop_pay import WhopLimitsIn, WhopLiveOut, WhopMethodOut, WhopOverviewOut, WhopRequestOut, WhopSwitchOut
from app.services import audit, payment_gateways, payment_requests, settings_service
from app.services.payment_gateways import GatewayError, GatewayUnavailable
from app.services.pricing import as_money
from app.services.providers import credentials as credentials_service

router = APIRouter(prefix="/admin/whop", tags=["admin"])

INTEGRATION = "whop"
MARKET = CountryCode.JO

#: **ما يُقال عن كلِّ مفتاح** — بالعربيّة، بجانبه
SWITCH_LABELS: dict[str, tuple[str, str]] = {
    "whop_card_enabled": (
        "دفعُ الكباتن بالبطاقة",
        "الاشتراكُ الشهريُّ وسدادُ المستحقّات من صفحة Whop الآمنة، جوارَ كليك. يُفعَّل الاشتراكُ أو تُسدَّد المستحقّاتُ فورَ تأكيد Whop.",
    ),
    "whop_rider_topup_enabled": (
        "شحنُ محفظة الراكب بالبطاقة",
        "يشحن الراكبُ محفظتَه ببطاقته بين الحدّين أدناه، ويُضاف المبلغُ فورَ تأكيد Whop.",
    ),
    "whop_rider_trip_enabled": (
        "دفعُ الرحلة بالبطاقة",
        "يظهر للراكب «الدفع بالبطاقة» عند دفع الرحلة: يُشحن رصيدُه بقيمتها عبر Whop ثمّ تُدفع الرحلةُ من المحفظة كأيِّ رحلةٍ بالمحفظة "
        "(أرباحُ الكبتن ناقصَ العمولة في الدفتر القائم). وإن أُلغيت الرحلةُ بعد الدفع بقي المبلغُ في محفظة الراكب.",
    ),
}

#: **من يدفع بهذه الطريقة** — كودُ الصفّ ⇐ اسمُه في اللوحة
AUDIENCE_LABEL = {"driver": "الكباتن", "rider": "الركّاب"}


async def _gateway(session):
    try:
        return await payment_gateways.gateway_for(session, INTEGRATION, MARKET)
    except GatewayUnavailable:
        return None


async def _methods(session) -> list[PayMethod]:
    return list(
        (
            await session.scalars(
                select(PayMethod)
                .where(PayMethod.integration == INTEGRATION, PayMethod.country_code == MARKET)
                .order_by(PayMethod.sort_order, PayMethod.code)
            )
        ).all()
    )


@router.get("", response_model=WhopOverviewOut)
async def overview(
    _reader: ListReader,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WhopOverviewOut:
    """**كلُّ ما يلزم المالكَ في مكانٍ واحد** — ولا قيمةَ سرٍّ فيه: «أُدخلت القيم» نعم أو لا."""
    switches = [
        WhopSwitchOut(
            key=key,
            title=title,
            hint=hint,
            enabled=await settings_service.is_feature_enabled(session, MARKET, key),
        )
        for key, (title, hint) in SWITCH_LABELS.items()
    ]
    stored = await credentials_service.get_values(
        session, payment_gateways.PROVIDER_KEYS[INTEGRATION], MARKET, active_only=False
    )
    gateway = await _gateway(session)
    methods = await _methods(session)
    by_id = {method.id: method for method in methods}
    rows: list[PaymentRequest] = []
    if methods:
        rows = list(
            (
                await session.scalars(
                    select(PaymentRequest)
                    .where(PaymentRequest.provider_id.in_(list(by_id)))
                    .order_by(PaymentRequest.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
    requests = [
        WhopRequestOut(
            **item.model_dump(),
            audience=AUDIENCE_LABEL.get(payment_gateways.audience_of(INTEGRATION, by_id[row.provider_id].code) or "", "—"),
        )
        for row, item in zip(rows, await _rows_out(session, rows), strict=True)
    ]
    return WhopOverviewOut(
        switches=switches,
        locked_countries=[c for c in CountryCode if c not in payment_gateways.SWITCH_COUNTRIES[INTEGRATION]],
        keys_entered=bool(stored and stored.get("api_key") and stored.get("webhook_secret") and stored.get("company_id")),
        contract_active=await credentials_service.provider_is_active(
            session, payment_gateways.PROVIDER_KEYS[INTEGRATION], MARKET
        ),
        ready=gateway is not None,
        sandbox=bool(getattr(gateway, "test_mode", False)),
        currency=getattr(gateway, "card_currency", None),
        webhook_url=payment_gateways.webhook_url(INTEGRATION),
        methods=[
            WhopMethodOut(
                audience=AUDIENCE_LABEL.get(payment_gateways.audience_of(INTEGRATION, method.code) or "", "—"),
                method=method_admin_out(method),
            )
            for method in methods
        ],
        requests=requests,
    )


@router.get("/payments/{request_id}/live", response_model=WhopLiveOut)
async def live_status(request_id: uuid.UUID, _reader: ListReader, session: DbSession) -> WhopLiveOut:
    """**ما يقوله Whop الآن عن دفعة** — محاولاتُها بحالها ومبلغها. **قراءةٌ لا تكتب شيئاً**: التسويةُ مسارُها الإشعارُ والمطابقةُ الدوريّة."""
    request = await session.get(PaymentRequest, request_id)
    methods = {method.id for method in await _methods(session)}
    if request is None or request.provider_id not in methods or not request.external_id:
        raise NotFound("لا دفعةَ Whop بهذا المعرّف")
    gateway = await _gateway(session)
    if gateway is None:
        raise InvalidInput("عقدُ Whop غيرُ مفعَّل — لا يُسأل")
    try:
        details = await gateway.details(request.external_id)  # type: ignore[attr-defined]
    except GatewayError as exc:
        raise InvalidInput(f"لم يُجب Whop: {exc}") from exc
    return WhopLiveOut(external_id=request.external_id, **details)


@router.put("/methods/{method_id}/limits", response_model=WhopMethodOut)
async def update_limits(
    method_id: uuid.UUID, payload: WhopLimitsIn, admin: SettingsWriter, session: DbSession
) -> WhopMethodOut:
    """**حدّا الدفعة الواحدة لطريقةٍ من طريقتَي Whop** — ويقرؤهما `_prepare` لكلِّ دفعة. **ولا يمسّ غيرَ صفَّي Whop في الأردن.**"""
    if payload.min_amount is not None and payload.max_amount is not None and payload.min_amount > payload.max_amount:
        raise InvalidInput("الحدُّ الأدنى أكبرُ من الأعلى", field="min_amount")
    if method_id not in {method.id for method in await _methods(session)}:
        raise NotFound("لا طريقةَ Whop بهذا المعرّف")
    method = await payment_requests.get_provider(session, method_id, for_update=True)
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
    await session.commit()
    await session.refresh(method)
    return WhopMethodOut(
        audience=AUDIENCE_LABEL.get(payment_gateways.audience_of(INTEGRATION, method.code) or "", "—"),
        method=method_admin_out(method),
    )
