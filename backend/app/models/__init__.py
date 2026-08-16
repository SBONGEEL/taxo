"""نماذج SQLAlchemy — كل النماذج تُستورد هنا ليراها Alembic autogenerate."""

from app.models.booking import RideBooking
from app.models.advance import AdvanceSetting, DriverAdvance
from app.models.audit import AdminAuditLog
from app.models.cancellation import CancellationSetting, RideCancellationCharge
from app.models.otp_setting import OtpSetting
from app.models.base import Base
from app.models.commission import CommissionSetting
from app.models.device import DeviceToken
from app.models.deactivation import DeactivationRequest
from app.models.driver import REQUIRED_DOCUMENT_TYPES, Driver, DriverDocument
from app.models.enums import (
    AdvanceStatus,
    AuditAction,
    CancellationChargeStatus,
    CampaignAudience,
    CampaignStatus,
    CommissionAppliesTo,
    CountryCode,
    Currency,
    DeliveryStatus,
    DevicePlatform,
    DisputeResolution,
    DocumentReviewStatus,
    DocumentType,
    DriverStatus,
    FeatureKey,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PromoDiscountType,
    ProviderKey,
    ProviderOrderPurpose,
    ProviderOrderStatus,
    RatingRaterType,
    RideStatus,
    SubscriptionDurationType,
    SubscriptionStatus,
    TopupMethod,
    TopupRequestStatus,
    UnpaidCancellationOutcome,
    UserRole,
    VehicleCategory,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalMethod,
    WithdrawalStatus,
)
from app.models.feature_flag import FeatureFlag
from app.models.notification import (
    NotificationCampaign,
    NotificationDelivery,
    NotificationSetting,
    UserNotification,
)
from app.models.payment import Payment, SavedCard
from app.models.payment_setting import PaymentSetting
from app.models.pricing import PricingRule
from app.models.promo import PromoCode
from app.models.provider_credential import ProviderCredential
from app.models.provider_order import ProviderOrder
from app.models.rating import Rating
from app.models.badge import Badge, DriverBadge
from app.models.mission import LevelSetting, Mission
from app.models.referral import Referral, ReferralSetting
from app.models.place import SavedPlace
from app.models.security_setting import SecuritySetting
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.ride import Ride, RideRoutePoint, RideStop
from app.models.sharing import RideSharingSetting
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.tip import Tip
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import (
    WalletTopupRequest,
    WalletTransaction,
    WithdrawalRequest,
)
from app.models.wallet_setting import WalletSetting

__all__ = [
    "AdminAuditLog",
    "AdvanceSetting",
    "AdvanceStatus",
    "DriverAdvance",
    "AuditAction",
    "CancellationChargeStatus",
    "CancellationSetting",
    "OtpSetting",
    "RideCancellationCharge",
    "UnpaidCancellationOutcome",
    "Base",
    "BookingStatus",
    "CampaignAudience",
    "CampaignStatus",
    "CommissionAppliesTo",
    "CommissionSetting",
    "CountryCode",
    "Currency",
    "DeliveryStatus",
    "DevicePlatform",
    "DeviceToken",
    "DisputeResolution",
    "DocumentReviewStatus",
    "DocumentType",
    "DeactivationRequest",
    "Driver",
    "DriverDocument",
    "Badge",
    "DriverBadge",
    "LevelSetting",
    "Mission",
    "Referral",
    "DriverStatus",
    "DriverSubscription",
    "FeatureFlag",
    "FeatureKey",
    "Payment",
    "NotificationCampaign",
    "NotificationDelivery",
    "NotificationSetting",
    "PaymentConfirmedBy",
    "PaymentMethod",
    "PaymentProvider",
    "PaymentStatus",
    "PricingRule",
    "PromoCode",
    "PromoDiscountType",
    "ProviderCredential",
    "ProviderKey",
    "ProviderOrder",
    "ProviderOrderPurpose",
    "ProviderOrderStatus",
    "Rating",
    "RatingRaterType",
    "ReferralSetting",
    "REQUIRED_DOCUMENT_TYPES",
    "Ride",
    "RideBooking",
    "RideRoutePoint",
    "SavedPlace",
    "RideStop",
    "RideSharingSetting",
    "RideStatus",
    "SavedCard",
    "SecuritySetting",
    "SubscriptionDurationType",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "Tip",
    "TopupMethod",
    "TopupRequestStatus",
    "User",
    "UserNotification",
    "UserRecoveryCode",
    "UserRole",
    "UserTotp",
    "Vehicle",
    "VehicleCategory",
    "WalletOwnerType",
    "PaymentSetting",
    "WalletSetting",
    "WalletTopupRequest",
    "WalletTransaction",
    "WalletTransactionType",
    "WithdrawalMethod",
    "WithdrawalRequest",
    "WithdrawalStatus",
]
