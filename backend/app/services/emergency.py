"""**زرُّ الطوارئ وأرقامُ التواصل** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٧ و٨).

## الزرّ

الراكبُ أو الكبتنُ يضغط ⇐ صفٌّ في `emergency_alerts` بالموقع والرحلة ⇐ **تنبيهٌ عاجلٌ** لمن يستقبل إشعاراتِ اللوحة (`admin_alerts`، نوعُ
`emergency` بلا نافذة جمع: كلُّ ضغطةٍ إشعارٌ وحدَها) ⇐ وفي اللوحة صفحةُ «الطوارئ» بالطرفين والموقع الحيّ حتى يعالجها مشرف.
**والتطبيقُ يعرض رقمَ طوارئ الدولة للاتّصال المباشر** — الزرُّ لا ينتظر المشرفَ ليتّصل الإنسانُ بالشرطة.

**وضغطتان متتاليتان في الرحلة نفسِها حالةٌ واحدة** (`DEDUPE`): من يضغط مرّتين في ذعرٍ لا يُنشئ حالتين يعالجهما مشرفان.

## الأرقام

`support_settings` لكلِّ دولة — **وغيابُ الصفِّ = الرقمُ الرسميُّ وواتسابٌ غائب**.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode
from app.models.ride import Ride
from app.models.support import DEFAULT_EMERGENCY, EmergencyAlert, SupportSetting
from app.models.user import User
from app.services import alert_capture, audit, geo

#: ضغطةٌ ثانيةٌ في الرحلة نفسِها (أو بلا رحلة) خلال هذه المدّة تُقرأ الحالةَ المفتوحةَ نفسَها
DEDUPE = timedelta(minutes=10)
_EMERGENCY = re.compile(r"^\+?[0-9]{2,15}$")
_WHATSAPP = re.compile(r"^[1-9][0-9]{7,14}$")


@dataclass(frozen=True, slots=True)
class Contacts:
    country_code: CountryCode
    emergency_number: str | None
    whatsapp_number: str | None


async def contacts_for(session: AsyncSession, country: CountryCode) -> Contacts:
    row = await session.get(SupportSetting, country)
    if row is None:
        return Contacts(country, DEFAULT_EMERGENCY.get(country), None)
    return Contacts(country, row.emergency_number, row.whatsapp_number)


def _clean(value: str | None, pattern: re.Pattern[str], field: str, label: str) -> str | None:
    if value is None:
        return None
    value = re.sub(r"[\s\-()]", "", value)
    if value == "":
        return None
    if value.startswith("+") and pattern is _WHATSAPP:
        value = value[1:]
    if not pattern.match(value):
        raise InvalidInput(f"{label} غيرُ صالح", field=field)
    return value


async def save_contacts(
    session: AsyncSession, *, country: CountryCode, emergency_number: str | None, whatsapp_number: str | None, actor: User
) -> Contacts:
    emergency = _clean(emergency_number, _EMERGENCY, "emergency_number", "رقمُ الطوارئ")
    whatsapp = _clean(whatsapp_number, _WHATSAPP, "whatsapp_number", "رقمُ واتساب (بالصيغة الدوليّة: 9627…)")
    row = await session.get(SupportSetting, country, with_for_update=True)
    before = None if row is None else {"emergency_number": row.emergency_number, "whatsapp_number": row.whatsapp_number}
    if row is None:
        row = SupportSetting(country_code=country)
        session.add(row)
    row.emergency_number = emergency
    row.whatsapp_number = whatsapp
    row.updated_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="support_settings",
        details={
            "country_code": country.value,
            "from": before,
            "to": {"emergency_number": emergency, "whatsapp_number": whatsapp},
        },
    )
    await session.flush()
    return Contacts(country, emergency, whatsapp)


async def _ride_for(session: AsyncSession, *, ride_id: uuid.UUID, user: User, role: str) -> Ride:
    ride = await session.get(Ride, ride_id)
    if ride is None:
        raise NotFound("الرحلة غير موجودة")
    if role == "rider":
        if ride.rider_id != user.id:
            raise NotFound("الرحلة غير موجودة")
    else:
        driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
        if driver is None or ride.driver_id != driver.id:
            raise NotFound("الرحلة غير موجودة")
    return ride


async def raise_alert(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    role: str,
    ride_id: uuid.UUID | None,
    lat: float | None,
    lng: float | None,
    now: datetime | None = None,
) -> tuple[EmergencyAlert, Contacts]:
    """**الضغطة** — صفٌّ وتنبيه، أو الحالةُ المفتوحةُ نفسُها إن ضُغط قبل قليل. ويُعاد رقمُ طوارئ الدولة مع الجواب."""
    if role not in ("rider", "driver"):
        raise InvalidInput("صفةٌ غيرُ معروفة", field="app")
    now = now or datetime.now(UTC)
    ride = await _ride_for(session, ride_id=ride_id, user=user, role=role) if ride_id is not None else None
    country = ride.country_code if ride is not None else user.country_code
    contacts = await contacts_for(session, country)

    recent = await session.scalar(
        select(EmergencyAlert)
        .where(
            EmergencyAlert.user_id == user.id,
            EmergencyAlert.status == "open",
            EmergencyAlert.created_at >= now - DEDUPE,
            EmergencyAlert.ride_id == ride_id if ride_id is not None else EmergencyAlert.ride_id.is_(None),
        )
        .order_by(EmergencyAlert.created_at.desc())
        .limit(1)
    )
    if recent is not None:
        if lat is not None and lng is not None:
            recent.lat, recent.lng = lat, lng
        return recent, contacts

    if (lat is None or lng is None) and ride is not None and ride.driver_id is not None:
        spot = await geo.last_position(redis, driver_id=ride.driver_id, country_code=ride.country_code)
        if spot is not None:
            lat, lng = spot.lat, spot.lng
    alert = EmergencyAlert(
        user_id=user.id, role=role, ride_id=ride.id if ride else None, country_code=country, lat=lat, lng=lng, status="open"
    )
    session.add(alert)
    await session.flush()
    alert_capture.ship_after_commit(session, "emergency", "emergency", alert.id)
    return alert, contacts


async def handle(session: AsyncSession, *, alert_id: uuid.UUID, actor: User, note: str) -> EmergencyAlert:
    """**عولجت** — بملاحظةٍ إلزاميّةٍ مدقَّقة. **والقفلُ قبل قراءة الحال**: مشرفان يعالجان معاً لا يكتب أحدُهما فوق الآخر."""
    note = (note or "").strip()
    if len(note) < 3:
        raise InvalidInput("اكتب ما فُعل (3 أحرفٍ على الأقل)", field="note")
    alert = await session.get(EmergencyAlert, alert_id, with_for_update=True, populate_existing=True)
    if alert is None:
        raise NotFound("الحالة غير موجودة")
    if alert.status == "handled":
        raise InvalidInput("عولجت هذه الحالةُ قبلك", field="note")
    alert.status = "handled"
    alert.handled_at = datetime.now(UTC)
    alert.handled_by = actor.id
    alert.note = note[:2000]
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="emergency_alert",
        entity_id=alert.id,
        details={"from": "open", "to": "handled", "note": alert.note},
    )
    await session.flush()
    return alert
