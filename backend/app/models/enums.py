from __future__ import annotations

from enum import StrEnum


class CountryCode(StrEnum):
    LY = "LY"
    JO = "JO"


class Currency(StrEnum):
    LYD = "LYD"
    JOD = "JOD"


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


class SubscriptionDurationType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CommissionAppliesTo(StrEnum):
    """نطاق تطبيق العمولة.

    `cashless_rides` = البطاقة والمحفظة فقط، أي ما تمر أمواله عبر المنصة —
    الرحلات النقدية وكليك يقبضها الكبتن مباشرة (القسم 9 من SPEC).
    """

    ALL_RIDES = "all_rides"
    CASHLESS_RIDES = "cashless_rides"


class ProviderKey(StrEnum):
    """مزودو الخدمات الخارجية المُدارون من صفحة العقود."""

    MAPBOX = "mapbox"
    TELR = "telr"
    SMS = "sms"
    CLIQ_ACQUIRER = "cliq_acquirer"
    FCM = "fcm"
    PAYOUT = "payout"


class FeatureKey(StrEnum):
    """مفاتيح feature_flags المعروفة.

    العمود في القاعدة نص لا ENUM، فإضافة مفتاح لاحقاً (مثل ميزات المرحلة 12)
    تغييرُ كود فقط بلا ترحيلة. هذا النوع يحرس الكتابة عبر طبقة Pydantic.
    """

    # لا مفتاح للعمولة هنا: مصدرها الوحيد `commission_settings` حيث تسكن نسبتها
    # ونطاقها — مفتاح ثانٍ يعني حالتين قابلتين للاختلاف لأمرٍ مالي.
    CLIQ_ENABLED = "cliq_enabled"
    CARD_ENABLED = "card_enabled"
    WALLET_ENABLED = "wallet_enabled"
    WALLET_TRANSFER_ENABLED = "wallet_transfer_enabled"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
