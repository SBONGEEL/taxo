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


class RideStatus(StrEnum):
    """دورة حياة الرحلة (SPEC القسم 4/5).

    `searching` تدخلها خوارزمية التوزيع في المرحلة 4، و`no_driver_found`
    مخرجها حين تنفد المحاولات.
    """

    REQUESTED = "requested"
    SEARCHING = "searching"
    ACCEPTED = "accepted"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED_BY_RIDER = "cancelled_by_rider"
    CANCELLED_BY_DRIVER = "cancelled_by_driver"
    NO_DRIVER_FOUND = "no_driver_found"


class PaymentMethod(StrEnum):
    """قنوات دفع الرحلة (SPEC القسم 4/6).

    `card` هنا منذ الآن وإن كان مساره معطّلاً حتى المرحلة 6-ب: إضافة قيمة إلى
    ENUM في postgres لاحقاً ترحيلةٌ وتعديلُ قيود، وشاشة الدفع تعرض القناة
    مطفأةً لا محذوفة.
    """

    CASH = "cash"
    CLIQ = "cliq"
    CARD = "card"
    WALLET = "wallet"


class PaymentProvider(StrEnum):
    """المزود الذي مرّت عليه العملية — فارغ لما لا مزود له (كاش، كليك، محفظة)."""

    TELR = "telr"


class PaymentStatus(StrEnum):
    """`pending → confirmed | failed | disputed | refunded` (SPEC القسم 4)."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"


class PaymentConfirmedBy(StrEnum):
    """من أكّد التحصيل: الكبتن يدوياً، أو المزود آلياً، أو الإدارة فصلاً لنزاع."""

    DRIVER = "driver"
    SYSTEM = "system"
    ADMIN = "admin"


class DisputeResolution(StrEnum):
    """حكم الإدارة في نزاع دفعة (SPEC القسم 6/13.4).

    `paid` = المبلغ وصل الكبتنَ فعلاً فتصير الدفعة `confirmed`، و`unpaid` =
    لم يصل فتصير `failed`. القيمتان تصفان الواقعة لا الحالة الناتجة، فحالةُ
    الدفعة تُشتق منهما في مكان واحد.
    """

    PAID = "paid"
    UNPAID = "unpaid"


class RatingRaterType(StrEnum):
    """من يقيّم من — التقييم متبادل بعد `completed` (SPEC القسم 5.9)."""

    RIDER = "rider"
    DRIVER = "driver"


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


class WalletOwnerType(StrEnum):
    """صاحب المحفظة — الراكب أو الكبتن (SPEC القسم 4).

    `owner_id` يشير إلى `users.id` في الحالتين؛ هذا العمود يميّز أي المحفظتين
    هي، فحسابُ كبتنٍ ما هو إلا امتداد لحساب مستخدم.
    """

    RIDER = "rider"
    DRIVER = "driver"


class WalletTransactionType(StrEnum):
    """أنواع قيود دفتر المحفظة (SPEC القسم 4).

    ما لا يُنشئه كودُ هذه المرحلة موجود هنا لأن النوع جزء من المواصفة:
    `ride_payment`/`ride_earning`/`commission`/`refund` تأتي مع الدفع
    (المرحلة 6)، و`subscription_payment` مع الاشتراكات (المرحلة 7).
    """

    TOPUP = "topup"
    RIDE_PAYMENT = "ride_payment"
    RIDE_EARNING = "ride_earning"
    COMMISSION = "commission"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"
    SUBSCRIPTION_PAYMENT = "subscription_payment"
    ADJUSTMENT = "adjustment"


class TopupMethod(StrEnum):
    """قنوات شحن محفظة الراكب (SPEC القسم 7).

    `card` هو Telr — شحن فوري آلي يأتي في المرحلة 6، فلا يمر بطلب ينتظر
    تأكيداً بشرياً كما تمر `cliq` و`cash`.
    """

    CLIQ = "cliq"
    CASH = "cash"
    CARD = "card"


class TopupRequestStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class WithdrawalMethod(StrEnum):
    CLIQ = "cliq"
    BANK = "bank"


class WithdrawalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
