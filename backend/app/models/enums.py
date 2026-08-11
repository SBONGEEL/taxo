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
    """المزود الذي مرّت عليه العملية — فارغ لما لا مزود له (كاش، كليك، محفظة).

    `cliq_acquirer` أضافته **المرحلة 8**: حساب التاجر الذي يشهد على شحن
    المحفظة بكليك آلياً (SPEC القسم 7/15-أ). لا يظهر على `payments` أبداً —
    دفعُ الرحلة بكليك يذهب إلى alias الكبتن لا إلى حساب الشركة، فلا مزود له
    ولا تأكيد آلي (القسم 6).
    """

    TELR = "telr"
    CLIQ_ACQUIRER = "cliq_acquirer"


class ProviderOrderPurpose(StrEnum):
    """لماذا فُتح طلبٌ لدى مزود الدفع (SPEC القسم 6.4/7/8).

    ثلاثة أغراض، وكلٌّ منها يستقر في مكانٍ مختلف عند النجاح: أجرةُ رحلة تستقر
    في صفّ `payments`، وشحنُ محفظة يستقر في قيد `topup` مباشرةً بلا طلبِ شحنٍ
    ينتظر إنساناً — شحن البطاقة فوريٌّ آلي (القسم 7) — واشتراكُ كبتنٍ يستقر في
    صفّ `driver_subscriptions` بلا قيدٍ في الدفتر أصلاً: مالُه خرج من بطاقته لا
    من محفظته (المرحلة 7، القسم 8).
    """

    RIDE_PAYMENT = "ride_payment"
    WALLET_TOPUP = "wallet_topup"
    SUBSCRIPTION = "subscription"


class ProviderOrderStatus(StrEnum):
    """حالة الطلب لدى المزود.

    `created` تعني «فُتح ولم يُحسم»: الراكب على صفحة الدفع أو غادرها. الحسم
    يأتي من المزود وحده — بـ webhook أو باستعلامٍ من الخلفية — لا من العميل.
    """

    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


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


class SubscriptionStatus(StrEnum):
    """حال اشتراك الكبتن (SPEC القسم 4/8).

    حالتان لا ثالثة: الاشتراك يُنشأ مدفوعاً — لا صفّ لاشتراكٍ لم يصل ماله —
    ويصير `expired` حين تتجاوزه الساعة. لا `cancelled`: اشتراكٌ مدفوعٌ مقدماً
    لا يُلغى، ولا `pending`: القنوات اليدوية (كاش/كليك) تُسجَّل بعد قبض المال
    لا قبله، تماماً كما لا يتغيّر رصيدٌ قبل تأكيد شحنته (القسم 7).
    """

    ACTIVE = "active"
    EXPIRED = "expired"


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
    # التحقق من الهاتف لدى Firebase (المرحلة 8-ب): عقدٌ مستقل عن `fcm` وإن
    # كان المشروع واحداً — إطفاءُ الإشعارات لا يجوز أن يُطفئ الدخول
    FIREBASE_AUTH = "firebase_auth"


class Gender(StrEnum):
    """جنسُ صاحب الحساب (المرحلة 10-ج).

    **قيمتان لا ثلاث، والغيابُ `NULL` لا عضوٌ ثالث**: «غير معروف» ليس جنساً،
    وجعلُه قيمةً يجعل الاستعلام يقارنها بجنسٍ فيطابق.

    ومصدرُها يختلف باختلاف من يعلنها، وهذا فرقٌ في الأمان لا في التنفيذ:
    **الراكبة تعلن جنسها بنفسها** — إعلانُها يقيّد رحلتَها هي؛ أما **جنسُ
    الكبتن فيضبطه المشرف من الهوية المرفوعة** ويُختم بـ`gender_verified_at`،
    لأن إعلانَه يقيّد أمانَ غيره. ولذلك تقرأ المطابقةُ **الكبتنَ المختوم
    وحده**: رجلٌ يكتب في حقلٍ أنه امرأة لا يصير سائقةً للنساء.
    """

    MALE = "male"
    FEMALE = "female"


class GenderPreference(StrEnum):
    """تفضيلُ جنس الطرف الآخر (المرحلة 10-ج).

    ثلاثيٌّ لأن «لا يهمّني» موقفٌ صريح لا غيابُ موقف: `any` هو الافتراضي،
    وهو ما يجعل تشغيل الميزة لا يغيّر شيئاً لمن لم يطلبها.
    """

    MALE = "male"
    FEMALE = "female"
    ANY = "any"


class CancelReasonCode(StrEnum):
    """سببُ إلغاءٍ **مصنَّف** بجانب النصّ الحر (المرحلة 10-ج).

    عمودُه `String(32)` محروسٌ بهذا التعداد في طبقة Pydantic لا `ENUM` في
    القاعدة — نفس استثناء `feature_flags.feature_key`: أسبابٌ جديدة تُضاف
    كوداً بلا ترحيلة.

    و`gender_mismatch` ليست تصنيفاً للتقارير فقط: هي التي تجعل الإلغاء **بلا
    رسوم** وتُدخل بلاغاً على حساب الطرف الآخر، فلا يجوز أن تكون نصاً حراً
    يكتبه من يشاء كما يشاء.
    """

    GENDER_MISMATCH = "gender_mismatch"
    OTHER = "other"


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
    # **الاستثناء الوحيد لقاعدة «غياب الصف = معطّل»** (المرحلة 8-ب): هذا
    # مفتاح **حارس** لا ميزة، وإطفاؤه يفتح باباً لا يغلقه. فغيابُ صفّه يعني
    # **مفعّلاً**، لأن القاعدة الأصلية وُضعت كي لا تُفتح ميزةٌ بالسكوت — وهنا
    # السكوتُ يُطفئ حارساً. انظر `settings_service.DEFAULT_ENABLED_FLAGS`
    OTP_VERIFICATION_ENABLED = "otp_verification_enabled"
    # خدمة التوصيل النسائي (المرحلة 10-ج). **ميزةٌ لا حارس**، فغيابُ صفّها
    # يعني معطّلة كبقية الميزات — وتبقى كذلك حتى تُراجَع أجناسُ الكباتن
    # المعتمدين المتراكمين. وحين تكون مطفأةً **لا مطابقةَ جنسٍ أصلاً**: لا
    # يُرشَّح تفضيلٌ ولا يُصفّى سائق، وإلا لأبقى تفضيلٌ قديمٌ على حساب كبتنٍ
    # يحجب عنه الطلبات في سوقٍ لا خدمةَ نسائيةً فيه
    WOMEN_SERVICE_ENABLED = "women_service_enabled"


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


class DevicePlatform(StrEnum):
    """منصة الجهاز المسجَّل لإشعارات Push (SPEC القسم 4 — المرحلة 8).

    تُقرأ عند الإرسال: أولوية FCM العالية تُكتب بحقلٍ مختلف لكل منصة
    (`android.priority` و`apns-priority` و`Urgency`).
    """

    ANDROID = "android"
    IOS = "ios"
    WEB = "web"


class CampaignAudience(StrEnum):
    """جمهور الحملة الإدارية/التسويقية (SPEC القسم 13 — المرحلة 8).

    `by_country` يعني «كل مستخدمي الدولة» ركاباً وكباتن؛ وعمود `country_code`
    يبقى مستقلاً عن هذا الحقل لأنه **مُضيِّق** لأي جمهور: «كل الكباتن في
    الأردن» جمهورٌ وتضييق، لا قيمةٌ ثالثة في الأنواع.

    `segment` محجوزة لشرائح المرحلة 12 (الكوبونات والعروض) — تُرفض اليوم
    برسالة صريحة بدل أن يُخترع لها معنى.
    """

    ALL_RIDERS = "all_riders"
    ALL_DRIVERS = "all_drivers"
    BY_COUNTRY = "by_country"
    SEGMENT = "segment"


class CampaignStatus(StrEnum):
    """`draft → scheduled → sent`، و`cancelled` مخرجٌ من الأوليين.

    لا حالة «قيد الإرسال»: الحملة تُرسل في دورةِ مهمةٍ واحدة على دفعات، وصفُّها
    مقفولٌ طوالها — فمهمتان متزامنتان لا ترسلان حملةً مرتين. وسجلُّ
    `notification_deliveries` هو ما يقول من وصله الإشعار فعلاً.
    """

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    """نتيجة إرسال حملةٍ إلى مستخدم بعينه.

    `skipped` ليست فشلاً: أطفأ التسويق، أو لا جهاز مسجّل له — والفرق بينها
    وبين `failed` هو الفرق بين «لم نرسل عمداً» و«أرسلنا فلم يصل».
    """

    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    # قراءةٌ تُسجَّل — نادرةٌ عمداً: تُكتب حيث تكون القراءةُ نفسها فعلاً يُسأل
    # عنه، كفتح خريطة مواقع الناس بهوياتهم (القسم 13/1)
    READ = "read"
