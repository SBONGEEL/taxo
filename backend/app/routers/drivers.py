from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import CurrentDriver, CurrentUser, DbSession
from app.core.exceptions import Conflict
from app.models.driver import DriverDocument
from app.models.vehicle import Vehicle
from app.schemas.auth import UserOut
from app.schemas.driver import (
    DriverDocumentOut,
    DriverOut,
    DriverProfileOut,
    VehicleCreate,
    VehicleOut,
)

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
