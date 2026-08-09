from __future__ import annotations

import secrets

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentDriver, CurrentUser, DbSession, RedisDep, RiderUser
from app.core.exceptions import Conflict
from app.models.driver import DriverDocument
from app.models.vehicle import Vehicle
from app.schemas.auth import UserOut
from app.schemas.driver import (
    DriverDocumentOut,
    DriverLocationIn,
    DriverOut,
    DriverProfileOut,
    NearbyDriverOut,
    VehicleCreate,
    VehicleOut,
)
from app.services import drivers as drivers_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/me", response_model=DriverProfileOut)
async def get_my_driver_profile(
    driver: CurrentDriver, user: CurrentUser, session: DbSession
) -> DriverProfileOut:
    vehicles = (
        await session.scalars(
            select(Vehicle).where(Vehicle.driver_id == driver.id).order_by(Vehicle.created_at)
        )
    ).all()
    documents = (
        await session.scalars(
            select(DriverDocument)
            .where(DriverDocument.driver_id == driver.id)
            .order_by(DriverDocument.created_at)
        )
    ).all()

    return DriverProfileOut(
        driver=DriverOut.model_validate(driver),
        user=UserOut.model_validate(user),
        vehicles=[VehicleOut.model_validate(v) for v in vehicles],
        documents=[DriverDocumentOut.model_validate(d) for d in documents],
    )


@router.get("/me/vehicles", response_model=list[VehicleOut])
async def list_my_vehicles(driver: CurrentDriver, session: DbSession) -> list[VehicleOut]:
    vehicles = (
        await session.scalars(
            select(Vehicle).where(Vehicle.driver_id == driver.id).order_by(Vehicle.created_at)
        )
    ).all()
    return [VehicleOut.model_validate(v) for v in vehicles]


@router.post(
    "/me/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED
)
async def add_my_vehicle(
    payload: VehicleCreate, driver: CurrentDriver, session: DbSession
) -> VehicleOut:
    vehicle = Vehicle(
        driver_id=driver.id,
        make=payload.make.strip(),
        model=payload.model.strip(),
        year=payload.year,
        color=payload.color.strip(),
        plate_number=payload.plate_number.strip().upper(),
        category=payload.category,
    )
    session.add(vehicle)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("رقم اللوحة مسجّل مسبقاً") from exc

    await session.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


# ------------------------------------------------- الاتصال والموقع اللحظي


@router.post("/me/online", response_model=DriverOut)
async def go_online(driver: CurrentDriver, session: DbSession) -> DriverOut:
    """مفتاح Online في تطبيق الكبتن (SPEC القسم 12.2).

    يصير الكبتن مرئياً للتوزيع بعد أول بث موقع — لا بمجرد رفع المفتاح.
    """
    await drivers_service.go_online(session, driver)
    await session.commit()
    return DriverOut.model_validate(driver)


@router.post("/me/offline", response_model=DriverOut)
async def go_offline(
    driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> DriverOut:
    await drivers_service.go_offline(session, redis, driver)
    await session.commit()
    return DriverOut.model_validate(driver)


@router.post("/me/location", status_code=status.HTTP_204_NO_CONTENT)
async def report_location(
    payload: DriverLocationIn,
    driver: CurrentDriver,
    session: DbSession,
    redis: RedisDep,
) -> Response:
    """بديل REST لبث الموقع.

    القناة الأساسية هي `WS /ws/driver` (كل ثلاث ثوانٍ بلا كلفة طلب كامل)؛
    هذا المسار لتطبيقٍ فقد مقبسه ولم يُعِده بعد، فلا يختفي الكبتن من الخريطة
    لأجل انقطاع لحظي.
    """
    context = await drivers_service.presence_context(session, driver)
    await drivers_service.report_location(
        redis, context, lat=payload.lat, lng=payload.lng, heading=payload.heading
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/nearby", response_model=list[NearbyDriverOut])
async def list_nearby_drivers(
    rider: RiderUser,
    session: DbSession,
    redis: RedisDep,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> list[NearbyDriverOut]:
    """لقطة واحدة من سيارات خريطة الراكب — البث المستمر على `WS /ws/rider`.

    تُستعمل لأول رسمة للخريطة وبعد انقطاع المقبس (SPEC القسم 10: الاسترجاع
    عبر REST). المِلح جديد لكل طلب، فلا يربط `ref` لقطتين ببعضهما.
    """
    salt = secrets.token_hex(16)
    presences = await drivers_service.nearby_available(
        redis, session, country_code=rider.country_code, lat=lat, lng=lng
    )
    return [
        NearbyDriverOut(
            ref=drivers_service.anonymous_ref(presence.driver_id, salt),
            lat=presence.lat,
            lng=presence.lng,
            heading=presence.heading,
            vehicle_category=presence.vehicle_category,
        )
        for presence in presences
    ]
