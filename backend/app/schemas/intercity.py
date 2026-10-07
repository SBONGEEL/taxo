"""بين المدن (SPEC §٦٣-ج/٧)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode, Currency


class RouteIn(BaseModel):
    country_code: CountryCode
    from_city: str = Field(min_length=2, max_length=60)
    to_city: str = Field(min_length=2, max_length=60)
    from_lat: float
    from_lng: float
    from_point: str = Field(min_length=2, max_length=255)
    to_lat: float
    to_lng: float
    to_point: str = Field(min_length=2, max_length=255)
    price_car: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    price_seat: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    is_active: bool = True


class RoutePatch(BaseModel):
    from_point: str | None = Field(default=None, min_length=2, max_length=255)
    to_point: str | None = Field(default=None, min_length=2, max_length=255)
    price_car: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    price_seat: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    is_active: bool | None = None


class RouteOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    country_code: CountryCode
    from_city: str
    to_city: str
    from_lat: float
    from_lng: float
    from_point: str
    to_lat: float
    to_lng: float
    to_point: str
    price_car: Decimal
    price_seat: Decimal
    is_active: bool


class PermitIn(BaseModel):
    vehicle_id: uuid.UUID
    seats: int = Field(ge=4, le=8)
    insurance_expires_on: date


class PermitOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    seats: int
    insurance_expires_on: date
    revoked_at: datetime | None


class TripIn(BaseModel):
    route_id: uuid.UUID
    departs_at: datetime
    seats: int = Field(ge=1, le=8)
    min_seats: int = Field(ge=1, le=8)


class TripOut(BaseModel):
    id: uuid.UUID
    route: RouteOut
    departs_at: datetime
    seats_offered: int
    seats_booked: int
    min_seats: int
    price_car: Decimal
    price_seat: Decimal
    currency: Currency
    status: str
    #: **أسماءُ الركّاب للكبتن قبل الانطلاق بساعة، وأرقامُهم عند الانطلاق وحدَه** (§٦٣-هـ) — وفارغةٌ لغيره
    passengers: list[dict] = []


class BookingIn(BaseModel):
    trip_id: uuid.UUID
    seats: int = Field(default=1, ge=1, le=8)
    whole_car: bool = False


class BookingOut(BaseModel):
    id: uuid.UUID
    trip: TripOut
    seats: int
    whole_car: bool
    amount: Decimal
    payment: str
    status: str
