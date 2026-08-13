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
    # وقوفٌ عند محطةٍ وسيطة (المرحلة 12-ب). حالةٌ **داخل** الرحلة لا فاصلٌ
    # بينها وبين غيرها: الراكب في السيارة، فلا إلغاءَ منها كما لا إلغاء من
    # `in_progress`. ومخرجاها `in_progress` باستئنافٍ، أو `completed` حين
    # يُنهي الكبتن عند المحطة بعد تجاوز سقف الانتظار (SPEC القسم 5.10)
    AT_STOP = "at_stop"
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
    # خصمُ الكوبون (المرحلة 12-ز): **قناةٌ لا يدفعها الراكب** — تُنشئها المنصةُ
    # وتؤكّدها بنفسها لحظةَ الإنهاء بقيمة الخصم. وهي **كالبطاقة: ليست في أيٍّ من
    # تصنيفَي القنوات** — لا في `DIRECTLY_COLLECTED_METHODS` (كي يُكتب للكبتن
    # `ride_earning`) ولا في `WALLET_FUNDED_METHODS` (كي لا يُخصم من محفظة
    # الراكب شيء). ولو وُضعت في الثاني لدفع الراكبُ الخصمَ من رصيده — أي لانقلب
    # الكوبونُ ضريبةً عليه، وهو نقيضُ الغرض كلِّه
    PROMO = "promo"


class PaymentProvider(StrEnum):
    """المزود الذي مرّت عليه العملية — فارغ لما لا مزود له (كاش، كليك، محفظة).

    `cliq_acquirer` أضافته **المرحلة 8**: حساب التاجر الذي يشهد على شحن
    المحفظة بكليك آلياً (SPEC القسم 7/15-أ). لا يظهر على `payments` أبداً —
    دفعُ الرحلة بكليك يذهب إلى alias الكبتن لا إلى حساب الشركة، فلا مزود له
    ولا تأكيد آلي (القسم 6).
    """

    TELR = "telr"
    CLIQ_ACQUIRER = "cliq_acquirer"


class PromoDiscountType(StrEnum):
    """نوعُ خصم الكوبون (المرحلة 12-ز).

    النسبةُ للحملات، والثابتُ لأول رحلةٍ مجاناً وللتعويضات (قرارُ المالك).
    والنسبةُ تحتاج سقفاً (`max_discount`) وإلا ابتلع كوبونُ ٥٠٪ رحلةً طويلة.
    """

    PERCENT = "percent"
    FIXED = "fixed"


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
    # واتساب مُحقِّقاً ثالثاً عبر WhatsApp Cloud API الرسمي من ميتا (12-هـ).
    # **عقدٌ عامٌّ لا per-country** كعقد SMS: رقمُ الهاتف يحمل دولته، ورقمُ
    # الأعمال الواحد يخدم السوقين. والذي يختلف بالدولة هو **المفتاح**
    # `whatsapp_otp_enabled` — فالعقد يقول «نستطيع» والمفتاح يقول «نفعل هنا»
    WHATSAPP = "whatsapp"


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
    # تعدد الوجهات (المرحلة 12-ب). **ميزةٌ لا حارس**، فغيابُ صفّها معطَّلة —
    # ولا تُضاف إلى `DEFAULT_ENABLED_FLAGS` مهما بدت صغيرة. وإطفاؤها يمنع
    # **الطلبات الجديدة** وحدها: رحلةٌ جارية بمحطاتها تكمل، ومحطاتُها مجمَّدة
    MULTI_STOP_ENABLED = "multi_stop_enabled"
    # واتساب مُحقِّقاً للرقم (12-هـ). **ميزةٌ لا حارس** فغيابُ صفّها معطَّلة،
    # ولا تُضاف إلى `DEFAULT_ENABLED_FLAGS`: إشعالُها يعني إرسالَ رمزٍ في قناةٍ
    # مدفوعةٍ لها قوالبُ معتمدة، وسكوتٌ يفتحها يُرسل في قناةٍ لم يُعتمد قالبُها.
    # وهي **per-country كبقية المفاتيح** بينما العقد عام: العقدُ يقول «نستطيع»
    # والمفتاحُ يقول «نفعل في هذا السوق» — فيُجرَّب في سوقٍ قبل الآخر
    WHATSAPP_OTP_ENABLED = "whatsapp_otp_enabled"
    # البقشيش (المرحلة 12-و). **ميزةٌ لا حارس** فغيابُ صفّها معطَّلة، ولا
    # تُضاف إلى `DEFAULT_ENABLED_FLAGS`. وتحكم **ما يُرسله التطبيق كما تحكم ما
    # يرسمه**: مطفأةً لا تظهر الأزرار ولا يُقبل النداء
    TIPS_ENABLED = "tips_enabled"
    # الكوبونات (المرحلة 12-ز). **ميزةٌ لا حارس** فغيابُ صفّها معطَّلة، وتحكم
    # **ما يُرسله التطبيق كما تحكم ما يرسمه**: مطفأةً لا تظهر ورقةُ الكوبون ولا
    # يُقبل رمزٌ في طلب الرحلة
    PROMO_CODES_ENABLED = "promo_codes_enabled"
    # حافزُ إحالة السائقات (المرحلة 12-ح). **ميزةٌ لا حارس** فغيابُ صفّها
    # معطَّلة. **ومفتاحُها ليس `women_service_enabled`** وإن كان الغرضُ واحداً:
    # ذاك مطفأٌ حتى يُصفّى متراكمُ إثبات الجنس، والحافزُ هو ما يبني العرضَ الذي
    # تنتظره الخدمةُ لتُشعَل — فربطُهما يجعلها تنتظر ما لا سبيلَ لبنائه.
    # وإطفاؤها يوقف **الدفعَ والعرض**، ولا يمحو إحالةً سُجّلت (SPEC القسم 9.1)
    DRIVER_REFERRALS_ENABLED = "driver_referrals_enabled"
    # الرحلاتُ المجدولة (المرحلة 12-ط). **ميزةٌ لا حارس** فغيابُ صفّها معطَّلة،
    # وتحكم **ما يُقبل كما تحكم ما يُرسم**: مطفأةً لا تُنشأ حجوزٌ جديدة —
    # **وما حُجز قبل الإطفاء يُنفَّذ**، كقاعدةِ المحطات: الإطفاءُ يمنع الجديد
    # ولا يخلف وعداً قائماً لراكبٍ رتّب موعدَه عليه
    SCHEDULED_RIDES_ENABLED = "scheduled_rides_enabled"
    # مشاركةُ الرحلة بين ركاب (المرحلة 12-ي). **ميزةٌ لا حارس** فغيابُ صفّها
    # معطَّلة. وتحكم **ما يُقبل كما تحكم ما يُرسم**: مطفأةً لا يُقبل طلبٌ
    # بمشاركة ولا تُعرض. **وإطفاؤها لا يفكّ مجموعةً قائمة** (قاعدةُ المحطات
    # والحجوزات): راكبان في سيارةٍ واحدةٍ الآن يكملان رحلتَهما بخصمهما.
    #
    # **ولا تكفي وحدَها**: `ride_sharing_settings.discount_percent` صفرٌ يعني
    # «لم تُقرَّر النسبةُ بعد» فتبقى الميزةُ مخفيةً ولو أُشعل المفتاح — كالبقشيش
    # بمبالغه الصفرية، فوعدُ خصمٍ مقدارُه صفرٌ أسوأ من غياب الوعد
    RIDE_SHARING_ENABLED = "ride_sharing_enabled"


class BookingStatus(StrEnum):
    """حالُ حجزٍ مجدول (SPEC القسم 5.11).

    **ثلاثُ حالاتٍ ولا رابعة**: `pending` ينتظر موعدَه، و`dispatched` سُلّم إلى
    التوزيع (و`ride_id` مكتوبٌ حينها)، و`missed` حلَّ موعدُه وصاحبُه في رحلةٍ
    جارية فلم تُنشأ ثانية، و`cancelled` ألغاه صاحبُه.

    **ولا `fulfilled` ولا `no_driver`**: ما جرى بعد التسليم تقوله الرحلةُ نفسُها،
    وقيمةٌ هنا تكرّرها بيتٌ ثانٍ يفترق عن الأول أولَ مرةٍ تُلغى فيها رحلةٌ وُجد
    لها كبتن — وهي قاعدةُ «لا عمودَ مشتقّاً» نفسُها (رصيدُ المحفظة، حالُ
    الاشتراك، استحقاقُ الإحالة).
    """

    PENDING = "pending"
    DISPATCHED = "dispatched"
    MISSED = "missed"
    CANCELLED = "cancelled"


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
    # البقشيش (المرحلة 12-و) — زوجٌ يقابل زوجَ الأجرة حرفياً: خصمٌ على الراكب
    # وإضافةٌ للكبتن. **ولا `commission` يقابلهما**: الكبتن يقبضه كاملاً
    # (قرارُ المالك)، فهو دخلُه الوحيد بلا عمولةٍ عليه
    TIP = "tip"
    TIP_PAYMENT = "tip_payment"
    # حافزُ الإحالة (المرحلة 12-ح) — **دائنٌ بلا مدينٍ مقابل**: الشركةُ تتحمّله
    # كما تتحمّل خصمَ الكوبون، ووعاءُ الشركة ليس محفظةً في هذا النظام. ولا
    # عمولةَ عليه ولا يدخل أرباحَ الرحلات (SPEC القسم 9.1)
    REFERRAL_BONUS = "referral_bonus"


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
