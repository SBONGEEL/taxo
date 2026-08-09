from __future__ import annotations

from enum import StrEnum


class CountryCode(StrEnum):
    LY = "LY"
    JO = "JO"


class UserRole(StrEnum):
    RIDER = "rider"
    DRIVER = "driver"
    ADMIN = "admin"
    SUPPORT = "support"


class DriverStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class VehicleCategory(StrEnum):
    ECONOMY = "economy"
    COMFORT = "comfort"


class DocumentType(StrEnum):
    DRIVING_LICENSE = "driving_license"
    NATIONAL_ID = "national_id"
    VEHICLE_REGISTRATION = "vehicle_registration"
    VEHICLE_PHOTO = "vehicle_photo"


class DocumentReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
