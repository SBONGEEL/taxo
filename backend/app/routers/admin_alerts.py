"""إشعاراتُ المالك في اللوحة (SPEC §٨١) — **الجرسُ والقائمةُ والإعدادُ والمعاينة**.

**وكلُّها بصلاحية `activity_alerts.receive`** (`ActivityAlertsReceiver`): المالكُ يملكها، **ولا يملكها مشرفٌ افتراضاً** (`permissions.SENSITIVE`)
— «وغيرُه إن منحه المالكُ ذلك لاحقاً» من مصفوفة الصلاحيات. **وبابٌ واحدٌ بلا جلسة**: «مقروء» من زرِّ الإشعار (`read_by_token`) —
إذنُه في رمزٍ يخصّ مستلماً وصفّاً، **ولا يفعل غيرَ ذلك**.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, status

from app.core.deps import ActivityAlertsReceiver, DbSession
from app.core.exceptions import NotFound
from app.models.admin_alert import AdminAlert
from app.models.enums import CountryCode
from app.schemas.admin_alerts import (
    AlertCatalogOut,
    AlertKindOut,
    AlertNamedOut,
    AlertOut,
    AlertPage,
    AlertReadIn,
    AlertReadOut,
    AlertSampleOut,
    AlertSettingsBody,
    AlertSummary,
    AlertTestIn,
    AlertTestOut,
    AlertTokenReadIn,
)
from app.services import admin_alerts

router = APIRouter(prefix="/admin/alerts", tags=["admin"])
public_router = APIRouter(prefix="/alerts", tags=["alerts"])


def _out(alert: AdminAlert, read: bool) -> AlertOut:
    title, body = admin_alerts.tray_text(alert)
    return AlertOut(
        id=alert.id,
        kind=alert.kind,
        category=alert.category,
        tone=alert.tone,
        country_code=alert.country_code,
        count=alert.count,
        amount=alert.amount,
        currency=alert.currency,
        record_type=alert.record_type,
        record_id=alert.record_id,
        data=alert.data,
        title=title,
        body=body,
        created_at=alert.created_at,
        last_event_at=alert.last_event_at,
        read=read,
    )


@router.get("", response_model=AlertPage)
async def list_alerts(
    user: ActivityAlertsReceiver,
    session: DbSession,
    category: Literal["accounts", "money", "rides", "support"] | None = None,
    kind: str | None = Query(default=None, max_length=48),
    country_code: CountryCode | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    unread: bool = False,
    before: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AlertPage:
    rows, unread_total = await admin_alerts.page(
        session,
        user,
        category=category,
        kind=kind,
        country=country_code,
        since=since,
        until=until,
        unread_only=unread,
        limit=limit,
        before=before,
    )
    return AlertPage(items=[_out(alert, read) for alert, read in rows], unread=unread_total)


@router.get("/summary", response_model=AlertSummary)
async def summary(user: ActivityAlertsReceiver, session: DbSession) -> AlertSummary:
    """**الجرس**: عددُ غير المقروء وآخرُ ثمانية — تسأله اللوحةُ كلَّ بضع ثوانٍ، فهو قراءتان مفهرستان لا أكثر."""
    rows, unread_total = await admin_alerts.page(session, user, limit=8)
    return AlertSummary(unread=unread_total, latest=[_out(alert, read) for alert, read in rows])


@router.post("/read", response_model=AlertReadOut)
async def mark_read(payload: AlertReadIn, user: ActivityAlertsReceiver, session: DbSession) -> AlertReadOut:
    marked = await admin_alerts.mark_read(session, user, ids=payload.ids, everything=payload.all)
    await session.commit()
    return AlertReadOut(marked=marked, unread=await admin_alerts.unread_count(session, user))


@router.get("/catalog", response_model=AlertCatalogOut)
async def catalog(_user: ActivityAlertsReceiver) -> AlertCatalogOut:
    """**الفهرسُ من بيته الواحد** — الأنواعُ وأسماؤها وفئاتُها وأصواتُها؛ اللوحةُ ترسم منه ولا تكتب نسختَها."""
    return AlertCatalogOut(
        kinds=[
            AlertKindOut(kind=spec.kind, category=spec.category, tone=spec.tone, label=spec.label, plural=spec.plural)
            for spec in admin_alerts.CATALOG.values()
        ],
        categories=[AlertNamedOut(key=key, label=label) for key, label in admin_alerts.CATEGORIES.items()],
        tones=[AlertNamedOut(key=key, label=label) for key, label in admin_alerts.TONES.items()],
        channels=list(admin_alerts.CHANNELS),
    )


@router.get("/settings", response_model=AlertSettingsBody)
async def read_settings(user: ActivityAlertsReceiver, session: DbSession) -> AlertSettingsBody:
    prefs = await admin_alerts.prefs_of(session, user.id)
    return AlertSettingsBody(kinds=prefs.kinds, sounds=prefs.sounds)


@router.put("/settings", response_model=AlertSettingsBody)
async def write_settings(payload: AlertSettingsBody, user: ActivityAlertsReceiver, session: DbSession) -> AlertSettingsBody:
    prefs = await admin_alerts.save_prefs(session, user.id, kinds=payload.kinds, sounds=payload.sounds)
    await session.commit()
    return AlertSettingsBody(kinds=prefs.kinds, sounds=prefs.sounds)


@router.get("/samples", response_model=list[AlertSampleOut])
async def samples(_user: ActivityAlertsReceiver, country_code: CountryCode = CountryCode.JO) -> list[AlertSampleOut]:
    """**صفحةُ المعاينة**: سطرُ كلِّ نوعٍ كما يصل الهاتفَ حرفاً — **من `tray_text` نفسِها** لا نسخةٌ في اللوحة. ومعها صفُّ جمعٍ لكلِّ نوع."""
    found: list[AlertSampleOut] = []
    for spec in admin_alerts.CATALOG.values():
        for count in (1, 12):
            title, body = admin_alerts.tray_text(admin_alerts.sample_alert(spec.kind, country_code, count=count))
            found.append(
                AlertSampleOut(kind=spec.kind, category=spec.category, tone=spec.tone, count=count, title=title, body=body)
            )
    return found


@router.post("/test", response_model=AlertTestOut)
async def send_test(payload: AlertTestIn, user: ActivityAlertsReceiver, session: DbSession) -> AlertTestOut:
    """**المعاينة**: إشعارٌ بالنوع إلى أجهزة من ضغط الزرَّ وحدَه — **بوسم «معاينة» ولا يُكتب منه شيء**."""
    if payload.kind not in admin_alerts.CATALOG:
        raise NotFound("نوعٌ غيرُ معروف")
    alert = admin_alerts.sample_alert(payload.kind, payload.country_code, count=payload.count)
    counts = await admin_alerts.send_to(session, user, [(alert, False)], sample=True)
    title, body = admin_alerts.tray_text(alert)
    return AlertTestOut(title=f"معاينة · {title}", body=body, **counts)


@public_router.post("/{alert_id}/read-by-token", status_code=status.HTTP_204_NO_CONTENT)
async def read_by_token(alert_id: uuid.UUID, payload: AlertTokenReadIn, session: DbSession) -> None:
    """**«مقروء» من زرِّ الإشعار** — المتصفّحُ والهاتفُ يرسلانه بلا جلسة؛ الرمزُ يخصّ هذا المستلمَ وهذا الصفَّ وحدَهما."""
    await admin_alerts.mark_read_by_token(session, alert_id=alert_id, user_id=payload.user_id, token=payload.token)
    await session.commit()
