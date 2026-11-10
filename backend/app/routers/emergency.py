"""**زرُّ الطوارئ وأرقامُ التواصل** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٧ و٨) — بابُ التطبيقين وبابُ اللوحة.

* `POST /emergency` — الضغطة، من الراكب أو الكبتن، في رحلةٍ أو خارجها. الجوابُ يحمل رقمَ طوارئ الدولة للاتّصال المباشر.
* `GET /support/contacts` — رقمُ الطوارئ وواتسابُ الدعم لدولة — **بلا دخول**: «تواصل معنا» يظهر في شاشة الدخول أيضاً.
* `GET /admin/emergencies` · `POST /admin/emergencies/{id}/handle` — صفحةُ «الطوارئ» للفريق، والطرفان والموقعُ الحيّ.
* `GET/PUT /admin/support-settings/{country}` — الرقمان لكلِّ دولة (`settings.write`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, RedisDep, SettingsWriter, StaffUser
from app.models.driver import Driver
from app.models.enums import CountryCode, RideStatus
from app.models.ride import Ride
from app.models.support import EmergencyAlert
from app.models.user import User
from app.services import emergency, geo

router = APIRouter(tags=["support"])

_LIVE = frozenset({RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS, RideStatus.AT_STOP})


class EmergencyIn(BaseModel):
    #: التطبيقُ الذي ضُغط منه — `rider` أو `driver`
    app: str = Field(pattern="^(rider|driver)$")
    ride_id: uuid.UUID | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class EmergencyOut(BaseModel):
    id: uuid.UUID
    emergency_number: str | None
    created_at: datetime


class ContactsOut(BaseModel):
    country_code: CountryCode
    emergency_number: str | None
    whatsapp_number: str | None


class ContactsIn(BaseModel):
    emergency_number: str | None = Field(default=None, max_length=24)
    whatsapp_number: str | None = Field(default=None, max_length=24)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class Party(BaseModel):
    name: str
    phone: str | None


class EmergencyRow(BaseModel):
    id: uuid.UUID
    status: str
    role: str
    country_code: CountryCode
    created_at: datetime
    reporter: Party
    ride_id: uuid.UUID | None
    ride_status: RideStatus | None
    rider: Party | None
    driver: Party | None
    plate_number: str | None
    pickup_address: str | None
    dropoff_address: str | None
    #: موقعُ الضاغط لحظةَ الضغط
    lat: float | None
    lng: float | None
    #: **الموقعُ الحيُّ الآن** — موقعُ الكبتن في رحلةٍ جارية، و`None` بعدها
    live_lat: float | None
    live_lng: float | None
    handled_at: datetime | None
    handled_by_name: str | None
    note: str | None


@router.post("/emergency", response_model=EmergencyOut)
async def press_emergency(body: EmergencyIn, user: CurrentUser, session: DbSession, redis: RedisDep) -> EmergencyOut:
    alert, contacts = await emergency.raise_alert(
        session, redis, user=user, role=body.app, ride_id=body.ride_id, lat=body.lat, lng=body.lng
    )
    await session.commit()
    return EmergencyOut(id=alert.id, emergency_number=contacts.emergency_number, created_at=alert.created_at)


@router.get("/support/contacts", response_model=ContactsOut)
async def support_contacts(session: DbSession, country_code: CountryCode) -> ContactsOut:
    return _contacts_out(await emergency.contacts_for(session, country_code))


def _contacts_out(contacts: emergency.Contacts) -> ContactsOut:
    return ContactsOut(
        country_code=contacts.country_code,
        emergency_number=contacts.emergency_number,
        whatsapp_number=contacts.whatsapp_number,
    )


def _party(user: User | None) -> Party | None:
    return None if user is None else Party(name=user.name, phone=user.phone)


@router.get("/admin/emergencies", response_model=list[EmergencyRow])
async def list_emergencies(
    session: DbSession,
    redis: RedisDep,
    _: StaffUser,
    status: str = Query(default="open", pattern="^(open|handled|all)$"),
    country_code: CountryCode | None = None,
) -> list[EmergencyRow]:
    query = select(EmergencyAlert).order_by(EmergencyAlert.created_at.desc()).limit(200)
    if status != "all":
        query = query.where(EmergencyAlert.status == status)
    if country_code is not None:
        query = query.where(EmergencyAlert.country_code == country_code)
    rows = (await session.scalars(query)).all()
    out: list[EmergencyRow] = []
    for row in rows:
        reporter = await session.get(User, row.user_id)
        ride = (
            await session.scalar(
                select(Ride)
                .where(Ride.id == row.ride_id)
                .options(
                    selectinload(Ride.driver).selectinload(Driver.user),
                    selectinload(Ride.driver).selectinload(Driver.vehicles),
                )
            )
            if row.ride_id is not None
            else None
        )
        rider = await session.get(User, ride.rider_id) if ride is not None else None
        driver_user = ride.driver.user if ride is not None and ride.driver is not None else None
        plate = (
            ride.driver.vehicles[0].plate_number
            if ride is not None and ride.driver is not None and ride.driver.vehicles
            else None
        )
        live_lat = live_lng = None
        if ride is not None and ride.driver_id is not None and ride.status in _LIVE:
            spot = await geo.last_position(redis, driver_id=ride.driver_id, country_code=ride.country_code)
            if spot is not None:
                live_lat, live_lng = spot.lat, spot.lng
        handler = await session.get(User, row.handled_by) if row.handled_by else None
        out.append(
            EmergencyRow(
                id=row.id,
                status=row.status,
                role=row.role,
                country_code=row.country_code,
                created_at=row.created_at,
                reporter=_party(reporter) or Party(name="—", phone=None),
                ride_id=row.ride_id,
                ride_status=ride.status if ride is not None else None,
                rider=_party(rider),
                driver=_party(driver_user),
                plate_number=plate,
                pickup_address=ride.pickup_address if ride is not None else None,
                dropoff_address=ride.dropoff_address if ride is not None else None,
                lat=row.lat,
                lng=row.lng,
                live_lat=live_lat,
                live_lng=live_lng,
                handled_at=row.handled_at,
                handled_by_name=handler.name if handler else None,
                note=row.note,
            )
        )
    return out


@router.post("/admin/emergencies/{alert_id}/handle", status_code=204)
async def handle_emergency(alert_id: uuid.UUID, body: NoteIn, session: DbSession, actor: StaffUser) -> None:
    await emergency.handle(session, alert_id=alert_id, actor=actor, note=body.note)
    await session.commit()


@router.get("/admin/support-settings/{country_code}", response_model=ContactsOut)
async def get_support_settings(country_code: CountryCode, session: DbSession, _: StaffUser) -> ContactsOut:
    return _contacts_out(await emergency.contacts_for(session, country_code))


@router.put("/admin/support-settings/{country_code}", response_model=ContactsOut)
async def save_support_settings(
    country_code: CountryCode, body: ContactsIn, session: DbSession, actor: SettingsWriter
) -> ContactsOut:
    contacts = await emergency.save_contacts(
        session,
        country=country_code,
        emergency_number=body.emergency_number,
        whatsapp_number=body.whatsapp_number,
        actor=actor,
    )
    await session.commit()
    return _contacts_out(contacts)

