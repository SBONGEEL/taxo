/** أنواع ما تردّه الخلفية — مرآةٌ لـ`backend/app/schemas/`.
 *
 * ما يخصّ الكبتن وحده. وكلُّ نوعٍ هنا يقابل مخططاً في الخلفية بالاسم نفسه،
 * فمن غيّر هناك يجد مقابله هنا باسمه.
 */

// **شكلُ الفُتات يسكن حيث يُبنى** (`lib/breadcrumbs.ts`) لا هنا — وهذا الملفُّ
// مرآةُ الخلفية، والفُتاتُ الشيءُ الوحيدُ في الحمولة **يصنعه العميل**.
// و`import type` يُمحى عند التصريف، **فلا مستوردَ في وقت التشغيل ولا دورة**.
import type { Crumb } from "@/lib/breadcrumbs";

export type CountryCode = "JO" | "LY";
export type Currency = "JOD" | "LYD";
export type UserRole = "rider" | "driver" | "admin" | "support";
export type VehicleCategory = "economy" | "comfort";

export type DriverStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "suspended"
  // **حالٌ تُكتب فعلاً ولم تكن في المرآة** (2026-08-23): `deactivation.py`
  // يكتبها على صفِّ الكبتن، و`withdrawals` يقرؤها. **وكان الاتحادُ أربعةً
  // والخلفيةُ خمسة**، فحسابٌ مُلغىً يصل الشاشةَ **بسطرِ حالٍ فارغ** —
  // و`tsc` لا يراه لأن اتحاداً أصغرَ صحيحٌ في نفسه.
  | "deactivated";

/** تفضيلُ جنس الطرف الآخر — مرآةُ `GenderPreference` في الخلفية. */
export type GenderPreference = "male" | "female" | "any";

/** **من يدفع أجرةَ رحلةٍ طُلبت لشخصٍ آخر أو طرد** (§٦٣-ج/١ و/٤) — مرآةُ `RidePayer` في الخلفية بأعضائها الثلاثة.
 *
 *  `requester` صاحبُ الطلب — **في رحلةٍ لغيره من تطبيقه** (محفظةٌ أو بطاقة) **فلا يقبض الكبتنُ شيئاً**، **وفي الطرد عند
 *  الالتقاط بأيِّ قناةٍ كأيِّ رحلة**؛ و`passenger_cash` الراكبُ الفعليُّ نقداً و`recipient_cash` مستلمُ الطرد نقداً عند التسليم،
 *  **ودفعتُهما تفتحها الخلفيةُ عند الإنهاء** فيؤكّدها الكبتنُ كأيِّ دفعةِ كاش. */
export type RidePayer = "requester" | "passenger_cash" | "recipient_cash";

export type DocumentType =
  
  | "driving_license"
  | "national_id"
  | "vehicle_registration"
  /** مهجورٌ: كان صورةَ المركبة الواحدة قبل أن تصير ستّاً مسمّاة (البند ١١). */
  | "vehicle_photo"
  | "vehicle_front"
  | "vehicle_back"
  | "vehicle_side_right"
  | "vehicle_side_left"
  | "vehicle_interior"
  | "vehicle_plate"
  /** الصورةُ الشخصية (البند ٥٢) — **مستندٌ يُراجَع وصورةٌ تُنشر معاً**.
   *  شرطُ اعتمادٍ إلا على سائقةٍ مثبَّتةِ الجنس، وحيث لا صورةَ يُرسم أوّلُ حرفٍ
   *  من الاسم — لا مربعٌ فارغ ولا أيقونةٌ عامة. */
  | "profile_photo";

export type DocumentReviewStatus = "pending" | "approved" | "rejected";

/** أيُّ مُحقِّقٍ فعّالٌ الآن — تقرؤه الواجهة ولا تختاره (SPEC القسم 15/أ). */
export type VerificationMethod =
  | "firebase"
  | "sms_otp"
  | "whatsapp_otp"
  // **مرآةُ التعداد لا قناةَ إثباتِ رقم**: البريدُ يُثبت البريد، **ولا يصل
  // هذا الاتحادَ من `verification` ولا من `verification_channels`** — تلك
  // تجيب «ما الذي يُثبت ملكيةَ هذا الرقم؟». وبابُه `email_signup` وحدَه.
  | "email_otp"
  | "none";

/** القنواتُ التي نرسل فيها رمزاً نحن — وما بينها مخرجُ ارتدادٍ (12-هـ). */
export type OtpChannel = "whatsapp_otp" | "sms_otp";

export interface User {
  /** **موعدُ حذف حسابه إن طلبه** (SPEC §59) — منه تُرسم شاشةُ الاستعادة. */
  deletion_due_at?: string | null;
  id: string;
  /** `null` نظرياً (المشرف) — والتطبيقان لا يريان إلا صاحبَهما. */
  phone: string | null;
  name: string;
  role: UserRole;
  /** كلُّ ما يملكه من أدوار — به يُقرَّر شكلُ زرِّ التبديل (SPEC §21). */
  roles: UserRole[];
  country_code: CountryCode;
  is_blocked: boolean;
  phone_verified: boolean;
  /** **الرقمُ محجوزٌ ولا يُملَك** — من سجّل ببريده (قرارُ المالك 2026-08-31).
   *
   *  **ولا يُشتقّ من `phone_verified === false`**: لتلك معنيان — حسابٌ أُنشئ
   *  والمفتاحُ مطفأٌ للطوارئ (**كاملُ الصلاحية**)، وحسابٌ سجّل ببريده
   *  (**محدودٌ عمداً**) — والسطرُ المعروضُ لهما مختلف. */
  phone_pending: boolean;
  /** **السببُ والطريقُ لمن أُوقف** — أو `null` (حملةُ تأكيد الأرقام).
   *
   *  **ويُبنى في الخلفية لا هنا**: التطبيقُ لا يكتب عربيّةً لخطأٍ سمّاه
   *  الخادم. **ولا يُشتقّ من `phone_pending`**: ذاك حسابٌ **وُلد محدوداً**،
   *  وهذا **كان كاملاً فأُوقف** — ورسالتاهما مختلفتان. */
  suspension: { code: string; message: string } | null;
  /** بريدُه إن أثبته — و`null` تعني لا بريدَ مُثبَت. */
  email: string | null;
  // جنسُ الكبتن يضبطه المشرف من هويته (المرحلة 10-ج)؛ `null` = لم يُثبَّت
  // بعد. يقرؤه التطبيق لشيءٍ واحد: هل تُتاح السِمة الوردية لصاحبة الشاشة
  gender: "male" | "female" | null;
  /** لحظةُ ختم المشرف — تقرؤها شاشةُ الحساب، وفارغةٌ عند الراكب دائماً. */
  gender_verified_at: string | null;
  ride_gender_preference: GenderPreference;
  created_at: string;
}
// وليس هنا `marketing_push_enabled`: `UserOut` في الخلفية لا يحمله، ومصدرُه
// `GET /notification-preferences` وحده. كان مكتوباً هنا ولا يرسله أحد — حقلٌ
// وهميّ من عائلة `awaiting_confirmation`، وُجد أثناء المرحلة 10-ج وحُذف

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  /** **لحظةُ الانتهاء لا مدّتُه**: الخلفيةُ ترسل `expires_at` (ISO)، وكان هذا
   *  النوع يكتب `expires_in: number` — حقلاً لا يُرسل أبداً. لم يقرأه أحدٌ بعد،
   *  فبقي كذبةً نائمة: أوّلُ من يبني تجديداً استباقياً للتوكن منه يقرأ
   *  `undefined`. كشفه `check:config` حين اتّسع لأجوبة المصادقة. */
  expires_at: string;
}

export interface AuthResponse {
  user: User;
  tokens: TokenPair;
}

export interface AuthMethod {
  /** الدخول كلمةُ مرورٍ دائماً؛ هذا يقول أيُّ مُحقِّقٍ يثبت الرقم. */
  verification: VerificationMethod;
  otp_length: number | null;
  /** **أيُعرض بابُ «سجّل ببريدك» في هذا السوق؟** — العقدُ والمفتاحُ معاً.
   *
   *  **وليس عضواً في `verification_channels`**: تلك تُثبت **ملكيةَ الرقم**،
   *  والبريدُ يُثبت البريد — وخلطُهما يفتح حساباً كاملَ الصلاحية برقمٍ لم
   *  يملكه أحد. */
  email_signup: boolean;
  otp_ttl_seconds: number | null;
  /** القنواتُ المهيأة بترتيب الأولوية — أوّلُها هو `verification` (12-هـ). */
  channels?: string[];
}

/** جوابُ الدخول — إمّا جلسةٌ كاملة، وإمّا تحدٍّ ثانٍ **بلا توكن** (12-د).
 *
 * **مرآةٌ لازمة وإن لم يُسجّل راكبٌ عاملاً ثانياً قط**: حارسُ الخلفية على
 * **الحساب** لا على الدور، و`POST /auth/login` يردّ هذا الشكل لكلِّ من يناديه.
 * وكان هذا الملف يكتبه `AuthResponse` بـ`tokens` غير قابلةٍ للغياب — فحسابٌ
 * يحمل عاملاً كان يمرّ إلى `tokens.save(undefined)` بلا خطأٍ يُرى.
 */
export interface LoginResponse {
  totp_required: boolean;
  user: User | null;
  tokens: TokenPair | null;
  challenge_token: string | null;
  expires_in: number | null;
}

export interface ChallengeResponse {
  sent: boolean;
  expires_in: number | null;
  resend_after: number | null;
  /** القناةُ التي أُرسل فيها الرمز فعلاً — تقولها الشاشة لصاحبها (12-هـ). */
  channel: string | null;
}

export interface CountryConfig {
  country_code: CountryCode;
  currency: Currency;
  features: Record<string, boolean>;
  vehicle_categories: VehicleCategory[];
  /** بادئةُ الدولة وطولُ رقمها الوطني — من `core/phone.py` عبر `/config`. */
  dial_code: string;
  national_number_length: number;
  /** ساعاتُ هدوء الحملات ومِنطقتُها — `null` تعني «لم تُضبط بعد». */
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  quiet_hours_timezone: string | null;
  /** **حسابُ كليك المستقبِل لهذا السوق** — يُضبط من اللوحة، ويُقرأ هنا فلا
   *  يكتب التطبيقُ رقماً من عنده. **و`null` تعني «لم يُضبط»**: تُخفى القناةُ
   *  كلُّها حينها — شاشةٌ تطلب تحويلاً بلا رقمٍ تُنتج حوالةً ضائعة. */
  cliq_alias: string | null;
  /** المُحقِّقُ **لهذه الدولة** وقنواتُه (12-هـ) — لا مُحقِّقُ الدولة الافتراضية.
   *
   * قناةُ واتساب مفتاحُها per-country، فقراءةُ `auth.verification` وحدها تجعل
   * شاشةَ التسجيل تُعلن قناةً وترسل الخلفيةُ في أخرى.
   */
  verification: VerificationMethod;
  verification_channels: string[];
  /** طولُ الرمز **لهذه الدولة** (لا للافتراضية) — و`null` لمُحقِّقٍ لا يأخذ
   *  رمزاً منّا. نُقل `verification` إلى صفِّ الدولة في 12-هـ وبقي هذا يُقرأ
   *  من `auth`، فترسم الشاشةُ خاناتِ سوقٍ وتتحقق الخلفيةُ بطول سوقٍ آخر. */
  otp_length: number | null;
  /** **أيُعرض بابُ «سجّل ببريدك» في هذا السوق؟** — العقدُ والمفتاحُ معاً.
   *
   *  **وليس عضواً في `verification_channels`**: تلك تُثبت **ملكيةَ الرقم**،
   *  والبريدُ يُثبت البريد — وخلطُهما يفتح حساباً كاملَ الصلاحية برقمٍ لم
   *  يملكه أحد. */
  email_signup: boolean;
  /** **التقريبُ في هذا السوق** (SPEC §٧٠-ج/٢ و٦) — من `payment_settings` بعينه. **يُقرأ ليعرض التطبيقُ خطواتِ الوحدة ويفحص ما
   *  يكتبه الكبتنُ بيده** (مبلغُ السحب ودفعةُ الدَّين: «مضاعفٌ للوحدة وإلا رُدّ») — **لا ليحسب به مبلغاً**: أكبرُ ما يُسحب
   *  و«سدّد كلَّه» يصلان من الخلفية محسوبين (§١٤). و`false` = كما كان حرفاً: لا خطوات ولا فحص. */
  rounding_enabled: boolean;
  /** **وحدةُ التقريب نصّاً بثلاث خانات** (`"0.500"`) — تُقرأ مشتعلةً وحدَها (`lib/rounding.ts`). */
  rounding_unit: string;
  /** **اتجاهُه** — مرآةٌ لما يُنشر؛ **ولا يقرؤه هذا التطبيق**: ما يقبضه الكبتنُ يصل مقرَّباً، والاتجاهُ يُضبط ويُقرأ في اللوحة. */
  rounding_mode: RoundingMode;
}

/** اتجاهُ التقريب — مرآةُ `RoundingMode` في الخلفية (`check:enums`). */
export type RoundingMode = "nearest" | "up" | "down";

/** قاعدةُ حقلٍ واحدة كما تنشرها `GET /config`. */
export interface FieldRule {
  type: "text" | "number" | "choice" | "boolean";
  required: boolean;
  label?: string;
  min_length?: number;
  max_length?: number;
  min?: number;
  max?: number;
  choices?: string[];
  /** الشروطُ قائمةً تُعلَّم لحظةَ الكتابة — نصُّها من الخلفية لا يُصاغ هنا. */
  conditions?: { key: string; label: string }[];
  /** نصُّ كل شرطٍ بالعربية — مفاتيحُها: required · type · min_length · max_length · min · max · choices */
  messages: Record<string, string>;
}

export interface AppConfig {
  app: string;
  auth: AuthMethod;
  countries: CountryConfig[];
  /** **الخرائطُ مكتوبةُ النوع وحدَها** (٢٠٢٦-٠٩-٢٩): `ios_public_token` يُقرأ على
   *  iOS بلا رجوع، فخطأُ اسمه خريطةٌ غائبةٌ على كلِّ iPhone — و`check:config`
   *  يقابل هذه الكتلةَ بما يُنشر. والباقي قاموسٌ مفتوحٌ كما كان. */
  providers: {
    mapbox?: { public_token?: string; ios_public_token?: string };
  } & Record<string, Record<string, string | undefined>>;
  /** الدولة التي تفترضها شاشاتُ ما قبل الدخول (لا منتقيَ دولٍ فيها). */
  default_country_code: CountryCode;
  /** قواعدُ التحقق مُشتقّةً من مخططات الخلفية (SPEC ١٧.٣).
   *
   * **ولا نسخةَ منها مكتوبةً هنا**: حدٌّ يُكتب في التطبيق يفترق عن حدِّ المخطط
   * أوّلَ تعديل، فيمنع التطبيقُ ما تقبله الخلفيةُ أو يقبل ما ترفضه. ونصوصُها
   * من السجل المركزي نفسِه، فلا تختلف رسالةُ الشاشة عن رسالة الخادم.
   */
  validation: Record<string, Record<string, FieldRule>>;
  /** **أنصافُ أقطار البحث** من `geo` في الخلفية (§٦٢-ب/٤٨) — ورقةُ الطلب تقول نطاقَها منها، **ولا رقمَ يُكتب هنا**. */
  dispatch: { search_radius_km: number; max_search_radius_km: number; gendered_max_search_radius_km: number };
}

export interface Vehicle {
  id: string;
  driver_id: string;
  make: string;
  model: string;
  year: number;
  color: string;
  plate_number: string;
  category: VehicleCategory;
  created_at: string;
}

export interface DriverDocument {
  id: string;
  doc_type: DocumentType;
  content_type: string;
  size_bytes: number;
  review_status: DocumentReviewStatus;
  review_note: string | null;
  /** تاريخُ انتهاء الصلاحية — `null` يعني «لا تاريخَ لهذا النوع» (البند ب). */
  expires_on: string | null;
  /** `driver` أو `admin` — **من كتبه آخِراً**، فلا يُقرأ تصحيحُ المشرف إقراراً. */
  expiry_source: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Driver {
  id: string;
  user_id: string;
  status: DriverStatus;
  cliq_alias: string | null;
  /** تفضيلُه **الدائم** لجنس الركاب — يملكه هو، بخلاف جنسه (المرحلة 10-ج). */
  gender_preference: GenderPreference;
  /** إذنُه بالتجديد التلقائي من محفظته (البند ١٤) — مطفأٌ حتى يرفعه هو. */
  auto_renew: boolean;
  /** **«طلبات المطار»** (§٦٣-ج/٢) — بيده وحدَه، **ومطفأةٌ حتى يُشعلها**: لا تصله رحلةُ مطارٍ بلا إذنه. */
  accepts_airport: boolean;
  rating_avg: string;
  is_online: boolean;
  current_ride_id: string | null;
  /** **فحصُ المركبة** (§61-ط/٥): موعدٌ ومكانٌ يضعهما المشرف ووقتُ اجتيازه — ولا يشترطها الاعتماد. */
  inspection_at: string | null;
  inspection_place: string | null;
  inspection_passed_at: string | null;
  created_at: string;
}

export interface DriverProfile {
  driver: Driver;
  user: User;
  vehicles: Vehicle[];
  documents: DriverDocument[];
  /** **نسبتُه هو لا نسبةُ السوق** — ترسمها الرئيسيةُ في بلاطة «عمولة TAXO».
   *
   *  **ولا تُحسب هنا** (§14): من اشترى اشتراكاً بوعدِ صفرٍ يرى صفراً ولو رفع
   *  السوقُ نسبتَه، **وهي حرفاً ما يجمّده `rides.accept`**. */
  commission_percent: string;
}

export interface DriverDocuments {
  documents: DriverDocument[];
  /** ما ينقص **حارسَ الاعتماد** — يعدّ المقبولَ وحدَه، فلا يُعرض على الكبتن. */
  missing_required: DocumentType[];
  /** **ما على الكبتن أن يرفعه**: ما لا صفَّ له أو رُفض. والمنتظِرُ مراجعةً
   *  ليس عليه فيه شيء — وخلطُ السؤالين جعله يقرأ «ناقص» عمّا رفعه للتوّ. */
  awaiting_upload: DocumentType[];
  /** ما لا يُعتمد الكبتنُ بدونه كاملاً — لا الناقصَ وحدَه (البند ١١). */
  required: DocumentType[];
}

/** جوابُ الرفع — ومعه أثرُه على حالة الكبتن (سياسة 9-ب). */
export interface DocumentUpload {
  document: DriverDocument;
  driver_status: DriverStatus;
  approval_reverted: boolean;
}

export type RideStatus =
  | "requested"
  | "searching"
  | "accepted"
  | "arrived"
  | "in_progress"
  /** وقوفٌ عند محطةٍ وسيطة (المرحلة 12-ب) — حالةٌ **داخل** الرحلة. */
  | "at_stop"
  | "completed"
  | "cancelled_by_rider"
  | "cancelled_by_driver"
  | "no_driver_found";

export interface Coordinates {
  lat: number;
  lng: number;
}

/** وقفةٌ مفتوحةٌ كما يراها الطرفان (SPEC §5.10-ب).
 *
 * **والوقتُ يرسمه التطبيقُ محلياً والمبلغُ يأتي من الخلفية** (§14): الوقتُ حسابُ
 * وقتٍ والمالُ حسابُ مال. و`started_at` هي **نقطةُ البدء المقيسة** التي يعدّ
 * منها العدّادُ المحليّ — لا رقمٌ يصل مع كلِّ إطار.
 */
export interface RidePause {
  id: string;
  /** `pause` وقفةٌ في منتصف الرحلة · `arrival` انتظارٌ عند الوصول. */
  kind: string;
  started_at: string;
  waited_minutes: string;
  charge: string;
  free_minutes: number;
  /** تجاوزَ السقف — **يُنبَّه عنده ولا تُنهى الرحلة**. */
  over_max: boolean;
}

/** سطرٌ من تفصيل الأجرة — **من الخلفية حرفاً** (§١٤): يُرسم `amount` ولا يُضرب `quantity` في شيء.
 *
 * **و`kind` نصٌّ لا اتحادُ `FareLineKind`** (كما في تطبيق الراكب) — **بقصدٍ مقيس**: هذا التطبيقُ يقرأ صنفاً واحداً (`rounding`،
 * `lib/rideFormat.ts`) ولا يرسم التفصيلَ كلَّه، **واتحادٌ كاملٌ هنا يحمل `"airport_fee"` و`"parcel_fee"` حرفيّتين** يقرؤهما
 * `check:money-visible` مرآتَي مالٍ بلا قارئٍ في هذا السطح (قِيس ٢٠٢٦-١٠-٠٩) — دعوى نشرٍ لا يقع. ويومَ يُرسم التفصيلُ كلُّه هنا
 * يُنقل الاتحادُ بتسمياته كما في `customer-app/src/lib/fareLines.ts`. */
export interface FareLine {
  kind: string;
  amount: string;
  quantity?: string | null;
}

export interface Ride {
  id: string;
  rider_id: string;
  status: RideStatus;
  country_code: CountryCode;
  vehicle_category: VehicleCategory;
  currency: Currency;
  pickup: Coordinates;
  pickup_address: string | null;
  dropoff: Coordinates;
  dropoff_address: string | null;
  distance_km: string;
  actual_distance_km: string | null;
  duration_min: string;
  estimated_fare: string;
  final_fare: string | null;
  cancellation_fee: string | null;
  /** **مبلغٌ مستوفى لكبتنٍ آخر** يُسلَّم نقداً مع الأجرة (`CANCELLATION-FEE.md`
   *  §6-أ) — مجمَّدٌ لحظةَ الطلب، فهو **ما عُرض على الكبتن قبل أن يقبل**.
   *
   *  ووصولُه إلى بطاقة العرض شرطُ صحّة §6-أ نفسِه: من قَبِل وهو يعرف لا يشتكي،
   *  ومن لم يُرد رفض العرضَ بلا عقوبة. فحقلٌ يصل ولا يُرسم يُبطل القاعدةَ.
   *  و`null`/صفرٌ يعني «لا شيءَ محمول». */
  carried_cancellation_fee: string | null;
  commission_percent_at_ride: string;
  cancelled_reason: string | null;
  /** ما طُلب في هذه الرحلة من جنس الكبتن — **وصفُ الطلب لا جنسُ صاحبته**. */
  gender_preference: GenderPreference;
  /** موعدُ الحجز الذي وُلدت منه (12-ط) — و`null` لرحلةٍ فورية. **مجمَّدٌ على
   *  الرحلة** لا مقروءٌ من الحجز: هو ما عُرض على الكبتن حين قَبِل. */
  scheduled_for: string | null;

  /** المشاركة (12-ي): نسبةُ الخصم **المجمَّدة** على هذه الرحلة، ومجموعتُها
   *  ومقعدُها فيها. وصفرُ النسبة يعني «رحلةٌ منفردة» — ولا عمودَ ثانٍ يخالفه.
   *
   *  **ووصولُها إلى بطاقة العرض شرطُ صحّةِ القرار الخامس في SPEC §5.12**:
   *  الكبتنُ يُخطَر بالتحاق راكبٍ ثانٍ ولا يُستأذَن، وما يجعل ذلك مقبولاً أنه
   *  رأى الشارةَ **قبل** أن يقبل. فحقلٌ يصل ولا يُرسم يُبطل القرارَ نفسَه. */
  share_discount_percent: string;
  share_group_id: string | null;
  share_seat: number;

  // --- تعدد الوجهات (المرحلة 12-ب) ---
  stops: RideStop[];
  /** الوقفةُ المفتوحةُ الآن — و`null` تعني لا وقفة (§5.10-ب). */
  open_pause: RidePause | null;
  /** رسمُ الوقفات **حتى اللحظة** — يُقرأ أثناءها كما يُقرأ بعدها. */
  pause_charge: string;
  pause_price_per_min: string;
  pause_max_minutes: number;
  /** **عدّادُ الأجرة** (§٦٢-ج/٤٢): المقدَّرةُ ورسمُ الانتظار والوقفات حتى لحظة القراءة — **يجمعها الخادم** (§14)، **ومقرَّبةً
   *  بقاعدة السوق** (SPEC §٧٠-ج/٤): الأجرةُ كما ستُحفظ لو انتهت الآن. */
  current_fare: string;
  /** **تفصيلُ الأجرة مجمَّداً من الخلفية** (§٦٢-ج/٢٥) — مجموعُ `amount` يساوي `estimated_fare` ثمّ `final_fare` حرفاً. **ويُقرأ
   *  هنا سطرُ «تقريب» وحدَه** (SPEC §٧٠-ج/٤، `lib/rideFormat.ts`): «تفصيل السعر» عند الكبتن يقول المقدَّرَ والرسومَ والنهائيّ،
   *  وفرقُ التقريب هو ما يفسّر النهائيَّ منها. وفارغٌ لرحلةٍ أقدمَ من التجميد. */
  fare_lines: FareLine[];
  /** **أيُطلب رمزُ الرحلة قبل البدء؟** (§٦٢-ج/٥، CW4) — السؤالُ وحدَه؛ والرمزُ عند الراكبة، **ولا يصل هذا التطبيقَ في أيِّ تمثيل**. */
  start_code_required: boolean;

  /** **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — `for_other` و`payer` يُنشران دائماً، **وعلى بطاقة العرض قبل القبول**: من قَبِل وهو
   *  يعرف أنه يقبض من غير صاحب الطلب أو لا يقبض شيئاً لا يشتكي (حجّةُ «محجوزة» و«مشتركة»). **والاسمُ والرقمُ بعد القبول
   *  وحدَه وحتى الانتهاء** (`null` على العرض وبعده) — الرقمُ أُعطي ليتصل به من يأتي، لا ليمرّ على كلِّ من عُرض عليه. */
  for_other: boolean;
  payer: RidePayer;
  passenger_name: string | null;
  passenger_phone: string | null;
  /** **رحلةٌ تمسّ مطاراً** (§٦٣-ج/٢) — شارةُ «مطار» على بطاقة العرض قبل القبول، **والرسمُ سطرُه في `fare_lines`** لا هنا. */
  airport: boolean;
  /** **الطرد** (§٦٣-ج/٤) — النوعُ على بطاقة العرض قبل القبول (شارةُ «طرد» وسطرُ دافعه)، **والمستلمُ اسمُه ورقمُه وعنوانُه بعد
   *  القبول وحدَه وحتى الانتهاء** (`null` على العرض وبعده) — كالراكب الفعليّ. */
  ride_type: "standard" | "parcel" | "hourly";
  recipient_name: string | null;
  recipient_phone: string | null;
  recipient_address: string | null;
  /** **بالساعة** (§٦٣-ج/٥) — الساعاتُ المحجوزة، **والكيلومتراتُ المشمولةُ محسوبةً في الخلفية** (فلا يضرب التطبيقُ شيئاً)، ومن أين
   *  يُدفع المحجوزُ عند البدء: `wallet` يُسوّى لحظةَ البدء (ورصيدٌ لا يكفي يرفضه برسالته)، و`cash` دفعةٌ معلَّقةٌ يؤكّد الكبتنُ
   *  استلامَها. و`null` في غير رحلة الساعة. **وتصل على العرض قبل القبول** — شارةُ «بالساعة» وسطرُها. */
  hourly_hours: number | null;
  hourly_included_km: number | null;
  hourly_prepay_method: "wallet" | "cash" | null;
  /** **رحلةٌ من المشوار الثابت** (§٦٣-ج/٦) — سعرُها المجمَّد دفعه الراكبُ مقدّماً مع اشتراكه، **وتُسوّى من المحفوظ عند الإنهاء**
   *  فيُقيَّد له ما يُقيَّد من أيِّ أجرة: **لا يستلم شيئاً من الراكب**. وتصل على العرض قبل القبول. */
  commute: boolean;
  /** **طريقةُ الدفع التي اختارها الراكبُ مع الطلب** (`design/PAYMENTS-UNCONFIRMED.md` §٢-١، SPEC §٦٤-ز) — «الدفع: كاش» على بطاقة
   *  العرض كما يرى الفئة. **و`null` حين لم تُرسل أو المفتاحُ مطفأ** — فلا يُرسم سطرٌ لطريقةٍ لا يُعرف عنها شيء. */
  payment_method_hint: PaymentMethod | null;

  current_leg: number;
  waiting_charge: string;
  stop_free_minutes: number;
  stop_price_per_min: string;
  stop_max_wait_minutes: number;
  /** رسمُ المحطة الواحدة **مجمَّداً**، و`stops_charge` حاصلُه في عددها.
   *  المجموعُ يأتي من الخلفية: الشاشةُ لا تضرب مالاً (§14). */
  stop_fee: string;
  stops_charge: string;

  created_at: string;
  accepted_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
}

/** محطةٌ وسيطة — و`waiting_charge` **محسوبٌ في الخلفية** لا هنا (القسم 14). */
export interface RideStop {
  id: string;
  sequence: number;
  lat: number;
  lng: number;
  address: string | null;
  arrived_at: string | null;
  resumed_at: string | null;
  waited_minutes: string;
  waiting_charge: string;
  /** تجاوز السقف — وعنده يُفتح للكبتن خيارُ إنهاء الرحلة عند المحطة. */
  over_max_wait: boolean;
}

/** ملخّصُ الأرباح (SPEC القسم 9 و12/7).
 *
 * **ثلاثةُ أرقامٍ لا رقم**: ما دخل المحفظة، وما اقتُطع عمولةً، وما قُبض
 * باليد — والأخيرُ **لا يزيد الرصيد** ويُعرض موسوماً. و`net` قد يكون سالباً
 * حين تُخصم عمولةُ رحلةٍ نقدية بلا أرباحَ تقابلها.
 */
/** يومٌ من نافذة الأرباح **بيوم الدولة** (§٦٢-ج/٣٨) — وأيّامُ النافذة تُجمع إلى `net` نفسِه. */
export interface EarningsDay {
  /** `YYYY-MM-DD` بتقويم الدولة. */
  day: string;
  net: string;
  /** حصّتُه من أكبر أيّام النافذة بإشارته (−١…١) — يُرسم بها العمودُ كما تصل، فلا قسمةَ مالٍ في الواجهة. */
  peak_share: number;
}

export interface Earnings {
  period: "today" | "week" | "month";
  from_at: string;
  to_at: string;
  currency: Currency;
  wallet_earnings: string;
  commission: string;
  /** البقشيش (12-و) — **الدخلُ الوحيد بلا عمولةٍ عليه**، فسطرٌ مستقل. */
  tips: string;
  /** ما اقتُطع سداداً لسلفة (البند ١٥) — وهو داخلٌ في `net`. */
  advance_repaid: string;
  net: string;
  directly_collected: string;
  completed_rides: number;
  /** صافي كلِّ يومٍ في النافذة (§٦٢-ج/٣٨) — يومٌ بلا قيدٍ صفٌّ بصفر. */
  days: EarningsDay[];
  /** التغيّرُ بالمئة عن النافذة السابقة المساوية لها **حتى الساعة نفسِها** — `null` حيث لا أساسَ له. */
  change_percent: number | null;
  /** **دقائقُ اتصاله في النافذة** (§٦٢-ج/٣٧) — `null` حيث `work_hours_enabled` مطفأ: «لم يُقَس» فلا يُرسم شيء. */
  online_minutes?: number | null;
}

export interface Wallet {
  owner_id: string;
  owner_type: "driver" | "rider";
  balance: string;
  currency: Currency;
  frozen: boolean;
  /** مستحقاتٌ معلّقةٌ من رسوم إلغاء — تُعرض ولا تدخل الرصيدَ المتاح. */
  cancellation_debt: string;
  pending_compensation: string;
}

/** محفظة الكبتن: الرصيد **والمتاح منه** بعد حجز الطلبات القائمة (القسم 9). */
export interface DriverWallet extends Wallet {
  available_for_withdrawal: string;
  /** **مالُ كبتنٍ آخر في يده** (`CANCELLATION-FEE.md` §6-أ): قبضه نقداً مع
   *  أجرةِ رحلةٍ وعليه تحويله. **لا أجرةٌ ولا خصمٌ عليه** فسطرُه مستقل،
   *  و**مطروحٌ من المتاح للسحب** لأنه ليس ماله. */
  carrier_dues: string;
  min_withdrawal_amount: string;
  /** يبقى في المحفظة ولا يُسحب — يخرج عند إلغاء التفعيل (البند ١٣). */
  withdrawal_reserve_amount: string;
  /** مجموعُ «عمولة TAXO» في الشهر الجاري — **تقويميّاً** بمِنطقة الدولة، لا
   *  ثلاثين يوماً متدحرجة: من يقرأ «هذا الشهر» يعدّ من أوّله. */
  commission_this_month: string;
}

export type WalletTransactionType =
  | "topup"
  | "ride_payment"
  | "ride_earning"
  | "commission"
  | "transfer_in"
  | "transfer_out"
  | "withdrawal"
  | "refund"
  | "subscription_payment"
  | "adjustment"
  | "tip"
  | "tip_payment"
  // **الستةُ التي كانت ناقصة** (2026-08-23): الاتحادُ كان اثني عشرَ والخلفيةُ
  // ثمانيةَ عشر، **و`check:enums` يمسك المخترَعَ لا الناقص** — فاتحادٌ أصغرُ
  // صحيحٌ في نفسه. والأثرُ أن `TRANSACTION_LABEL[type]` ترجع `undefined`
  // **فتُرسم حركةُ مالٍ بلا اسم** في كشف الكبتن: اقتطاعُ سلفة، ورسمُ إلغاء،
  // وشراءُ مركبة — **كلُّها مبالغُ تخرج من جيبه بلا سطرٍ يسمّيها**.
  | "advance"
  | "advance_repayment"
  | "cancellation_fee"
  | "cancellation_compensation"
  | "referral_bonus"
  | "skin_purchase"
  // **الحجزُ المضمون** (§٦٣-ج/٣): رسمُ الضمان يصله، **وغرامةُ اعتذاره بعد التأكيد** تخرج من محفظته — والثلاثةُ الباقيةُ للراكب
  | "guarantee_hold"
  | "guarantee_fee"
  | "guarantee_refund"
  | "guarantee_penalty"
  | "guarantee_compensation"
  // **المشوارُ الثابت** (§٦٣-ج/٦): **حافزُ الكبتن المعتمد** من TAXO يصله، والاثنان الباقيان للراكب ويُسمّيان للعلّة أعلاه
  | "commute_prepay"
  | "commute_credit"
  | "commute_incentive"
  // **بين المدن** (§٦٣-ج/٧): **أجرةُ رحلته تصله من مال المقاعد المحفوظ** عند الإنهاء، والاثنان الباقيان للراكب ويُسمّيان للعلّة أعلاه
  | "intercity_hold"
  | "intercity_refund"
  | "intercity_earning"
  // **الاسترداد الأسبوعي** (§٦٣-ج/٨): للراكب وحدَه من TAXO — لا يقع للكبتن ولا يُخصم منه، ويُسمّى للعلّة أعلاه
  | "cashback"
  // **التقريب** (§٧٠-ج/٦): **زائدُ «سدّد كلَّه» يعود إلى محفظته قيداً صريحاً** — سدادُ الدَّين بكليك وسدادُ السلفة الكامل
  // يُقرَّبان للأعلى إلى وحدة السوق، والفرقُ له لا يُبتلع
  | "rounding";

export interface WalletTransaction {
  id: string;
  type: WalletTransactionType;
  amount: string;
  balance_after: string;
  ride_id: string | null;
  reference: string | null;
  created_at: string;
  /** النسبةُ المجمَّدة لقيدِ العمولة وحدَه — و`null` لكلِّ ما عداه (§25.11). */
  commission_percent: string | null;
}

/** بطاقةٌ محفوظة كما تراها الواجهة — **لا رمزَ مزودٍ ولا رقمَ بطاقة**. */
export interface SavedCard {
  id: string;
  provider: "telr";
  brand: string | null;
  last4: string;
  expiry_month: number;
  expiry_year: number;
  is_default: boolean;
  created_at: string;
}

/** صفٌّ في صندوق الوارد — `kind` هو `data.type` نفسه، فالنقرُ عليه والنقرُ
 * على إشعار النظام يفتحان الشاشة ذاتها (`services/notifications.py`). */
export interface UserNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  data: Record<string, string> | null;
  read_at: string | null;
  created_at: string;
}

/** طلبُ الدفع لدى المزود كما تراه الواجهة (القسم 6.4) — بلا مرجعٍ داخلي. */
export interface CardOrder {
  cart_id: string;
  provider: "telr";
  purpose: "ride_payment" | "wallet_topup" | "subscription";
  status: "created" | "pending" | "paid" | "failed" | "cancelled" | "refunded";
  amount: string;
  currency: Currency;
  redirect_url: string | null;
}

export interface NotificationPreferences {
  marketing_push_enabled: boolean;
}

export type WithdrawalMethod = "cliq" | "bank";
export type WithdrawalStatus = "pending" | "approved" | "paid" | "rejected";

export interface Withdrawal {
  id: string;
  driver_id: string;
  amount: string;
  method: WithdrawalMethod;
  status: WithdrawalStatus;
  reference: string | null;
  note: string | null;
  transaction_id: string | null;
  processed_at: string | null;
  created_at: string;
}

/** مرآةُ `SubscriptionDurationType` — والخطط الثلاث في القسم 8. */
export type SubscriptionDuration = "daily" | "weekly" | "monthly";

export interface SubscriptionPlan {
  id: string;
  country_code: CountryCode;
  name: string;
  duration_type: SubscriptionDuration;
  price: string;
  currency: Currency;
  is_active: boolean;
  /** عرضُ **هذا الكبتن** محسوباً — لا قائمةُ العروض القائمة (البند ٥٤).
   *
   * `null` يعني لا عرضَ ينطبق عليه، **ولا يُقال له إن ثمّة عرضاً لغيره**:
   * عرضٌ يُرى ولا يُطبَّق عند الضغط أسوأُ من عرضٍ لا يُرى.
   */
  offer_name: string | null;
  offer_discount: string | null;
  /** يُحسب في الخلفية كبقية المال (§14) — لا يُطرح في المتصفح. **و`null` بلا عرضٍ حقيقيّ**: هو وحدَه ما يُرسم السعرُ بجانبه
   *  مشطوباً، فلا شطبَ بلا عرض (مراجعةُ المال البند ٧). */
  price_after_discount: string | null;
  offer_ends_at: string | null;
  /** **ما يُخصم فعلاً** — السعرُ ناقصَ العرض مقرَّباً إلى وحدة السوق (SPEC §٧٠-ج/٥)، **عرضٌ أو لا عرض**. هو الرقمُ المرسومُ والمشترى
   *  به؛ ومطفأً بلا عرضٍ هو `price` حرفاً. و`null` حيث لا يُحسب لكبتن. */
  price_to_pay: string | null;
  /** عرضٌ استفاد منه هذا الكبتنُ سلفاً فاستنفد حدَّه — يُذكر ولا يُطبَّق.
   *  و`null` لمن لم يستحقّ قطُّ: فمن لم يُعرض عليه شيءٌ لا يُقال له شيء. */
  exhausted_offer_name: string | null;
}

export interface MySubscription {
  is_active: boolean;
  coverage_until: string | null;
  days_remaining: number;
  current: DriverSubscription | null;
  plans: SubscriptionPlan[];
}

/** **المسارُ الذي سارته الرحلة** (`GET /rides/{id}/route`، §٦٢-ج/١١) — `[lng, lat]` كـ`route-line`، **وفارغٌ حين صمت بثُّك**
 *  فلا يُرسم خطّ. و`truncated` يقول إن الذيلَ قُصّ عند سقف الخلفية. */
export interface RecordedRoute {
  points: number[][];
  truncated: boolean;
}

/** مرآةُ `PaymentMethod` — أربعُ قنوات. **ولا `mixed` فيها**: الدفعُ المختلط
 * (محفظة + كاش) **صفّان** على رحلةٍ واحدة لا قناةٌ ثالثة، ولذلك لا فهرس فريد
 * على `payments.ride_id` أصلاً (القسم 6). */
/** ومنها `promo` (12-ز): خصمُ كوبونٍ تدفعه الشركة — يُقيَّد للكبتن كأي دفعةٍ
 *  تمرّ بالمنصة، فيراه في كشفه لا في «تقبض الآن». */
export type PaymentMethod =
  "cash" | "wallet" | "card" | "cliq" | "promo" | "share" | "commute";
/** مرآةُ `PaymentStatus` في `app/models/enums.py` — **ستُّ قيمٍ منذ `voided`** (§٦٤-ز: دفعةٌ بدّل الراكبُ طريقتَها
 * قبل تأكيدك، فلا تنتظر منك شيئاً).
 *
 * ولا `awaiting_confirmation` فيها: انتظارُ تأكيد الكبتن **ليس حالاً** بل
 * `pending` على قناةٍ يقبضها بيده — والتمييز من `method` لا من حقلٍ سابع. */
export type PaymentStatus =
  "pending" | "confirmed" | "failed" | "refunded" | "disputed" | "voided";

/** صفٌّ في سجل الرحلات — الرحلةُ **ومعها حالُ دفعها**.
 *
 * الملخّصُ مضمومٌ في الخلفية في استعلامٍ ثانٍ لا نداءٍ لكل صف
 * (`FUTURE-FEATURES` بند 19). **ونوعٌ مستقلٌّ عن `Ride`**: تلك تُبثّ في كل
 * إطار مقبس، فحملُها ملخّصَ دفعٍ عملٌ لا يقرؤه أحد هناك.
 */
export interface RideListItem {
  ride: Ride;
  has_open_dispute: boolean;
  payment_methods: PaymentMethod[];
  paid_amount: string;
  settlement: SettlementState;
}

export interface Payment {
  id: string;
  ride_id: string;
  method: PaymentMethod;
  amount: string;
  currency: Currency;
  status: PaymentStatus;
  confirmed_at: string | null;
  cliq_alias: string | null;
  cliq_reference: string | null;
  cliq_transfer_reference: string | null;
  /** موعدُ انقضاء مهلة التأكيد، مجمَّدٌ على الصف (القسم 6.2/6). */
  cliq_confirmation_expires_at: string | null;
  /** ما كتبه الكبتن حين قال «لم يصلني»، وفصلُ الإدارة فيه (القسم 6.2). */
  dispute_reason: string | null;
  disputed_at: string | null;
  resolution: "paid" | "unpaid" | null;
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

/** حالُ الدفع على رحلةٍ كاملة — الدفع المختلط صفّان (SPEC القسم 6). */
export interface RidePayments {
  ride_id: string;
  currency: Currency;
  final_fare: string | null;
  outstanding: string;
  settlement: SettlementState;
  payments: Payment[];
}

/** **حالُ صفٍّ في «ركّابٌ ينتظرون تأكيدك»** (`design/PAYMENTS-UNCONFIRMED.md` §٦، SPEC §٦٤-ز) — مرآةُ `CaptainUnconfirmedState`
 *  (`Literal` في `schemas/unconfirmed_payment.py`): `awaiting_you` ينتظر «استلمت»/«وصلتني» · `auto_confirmed` أُتمّ آلياً ونافذةُ
 *  اعتراضه مفتوحة. */
export type CaptainUnconfirmedState = "awaiting_you" | "auto_confirmed";

/** «ليلى · أمس 21:58 · 3.364 د.أ كاش» ← «استلمت المبلغ» · «لم يدفع» — **الاسمُ الأوّلُ للراكب وحدَه**، والمبلغُ كما هو (§14). */
export interface CaptainUnconfirmedItem {
  payment_id: string;
  ride_id: string;
  completed_at: string;
  pickup_address: string | null;
  dropoff_address: string | null;
  rider_first_name: string | null;
  amount: string;
  currency: Currency;
  method: PaymentMethod;
  state: CaptainUnconfirmedState;
  status: PaymentStatus;
  /** **أقرّ الراكبُ بالتسليم** — ومنه يعرف الكبتنُ أن الصمتَ سيُتمّه آلياً */
  declared_at: string | null;
  /** كليك: «حوالةٌ بمرجع FT2410… · 21:47»، ومهلةُ التأكيد المجمَّدة */
  cliq_transfer_reference: string | null;
  cliq_reference_at: string | null;
  cliq_confirmation_expires_at: string | null;
  /** **«فاعترض قبل {الوقت}»** — لما أُتمّ آلياً وحدَه */
  objection_deadline: string | null;
}

/** ما ينتظر تأكيدَه — **الأقدمُ أوّلاً**. و`blocked` شرطُ التوزيع نفسُه: «لا تصلك طلباتٌ جديدةٌ حتى تؤكّد ما سبق». */
export interface CaptainUnconfirmed {
  blocked: boolean;
  /** عتبتا الحجب في سوقه — عددُ المعلَّقات وعمرُ أقدمِها بالساعات */
  block_count: number;
  block_hours: number;
  items: CaptainUnconfirmedItem[];
}

export type RatingRaterType = "rider" | "driver";

export interface Rating {
  id: string;
  ride_id: string;
  rater_type: RatingRaterType;
  stars: number;
  comment: string | null;
}

export interface DriverSubscription {
  id: string;
  plan_name: string;
  duration_type: SubscriptionDuration;
  starts_at: string;
  expires_at: string;
  amount_paid: string;
  /** ما سُجّل فعلاً لا ما حسبه العرض — فلا يُعرض خصمٌ لم يُنَل. */
  list_price: string;
  discount_amount: string;
  currency: Currency;
  payment_method: PaymentMethod;
  status: "active" | "expired" | "cancelled";
}


/** إحالةٌ واحدةٌ كما تصل — **حقائقُ لا جملةُ حالة** (المرحلة 12-ح). */
export interface ReferralStage {
  id: string;
  created_at: string;
  /** برنامجُ هذا الصف — **من دور المُحال**، فالرمزُ واحدٌ يخدم الاثنين. */
  referral_type: string;
  driver_approved: boolean;
  has_subscription: boolean;
  /** **علاوةٌ لا شرط**: وسمُها يزيد المبلغَ ولا يمنع الدفع. */
  female_verified: boolean;
  rides_done: number;
  rides_required: number;
  qualifies: boolean;
  rewarded: boolean;
  /** استحقّت ولن تُدفع لأنها فوق سقف الشهر — **يُقال صراحةً لا يُصمت عنه**. */
  over_monthly_cap: boolean;
  reward_amount: string | null;
  reward_currency: string | null;
  rewarded_at: string | null;
}

/** سياسةُ برنامجٍ واحد — والمبلغان مختلفان لأن قيمةَ الحسابين مختلفة. */
export interface ReferralProgram {
  referral_type: string;
  enabled: boolean;
  reward_amount: string;
  required_rides: number;
  /** تُضاف إلى `reward_amount` حين تكون المُحالةُ موثَّقةَ الجنس — لا تحلّ محلَّه. */
  female_bonus_amount: string;
  /** **المُحصَّلُ (الأساسُ + العلاوة) من الخلفية** — لا يُجمع هنا: جمعُ المال
   *  في الواجهة تمريرٌ له عبر عائم، وقد أخرج «٨» بلا كسورٍ بجانب «٥٫٠٠٠». */
  female_total_amount: string;
  /** `null` = بلا سقف. */
  monthly_cap: number | null;
}

/** قسمُ الإحالة في الحساب. **و`reward_amount === "0"` تعني «لم يُحدَّد»**
 *  فلا تعرض الشاشةُ مبلغاً ولا تَعِد به — وعدٌ بمالٍ لم يقرّره أحدٌ أسوأ من صمت. */
export interface MyReferrals {
  code: string;
  programs: ReferralProgram[];
  /** كم دُفع له هذا الشهر — يُقارَن بـ`monthly_cap` **قبل أن يدعو**. */
  paid_this_month: number;
  total_rewarded: string;
  referrals: ReferralStage[];
}

/** حالُ طلب إلغاء التفعيل وموانعُه (البند ١٣). */
export interface DeletionState {
  /** `null` = لا طلب. والموعدُ بعد 30 يوماً من الطلب (SPEC §59). */
  requested_at: string | null;
  due_at: string | null;
  /** رمزُ سبب التأجيل إن حلّ الموعدُ ولم يقع — والنصُّ في الشاشة */
  deferred_reason: string | null;
  /** **قائمةٌ لا أوّلُ سبب**: من أزال مانعاً ثم صُدم بثانٍ يقرأ الرفضَ مماطلة. */
  blockers: string[];
  rider_balance: string;
  driver_balance: string;
  /** ما أقرّ بضياعه كما كتبه — يُقارَن بالرصيد في اليوم الثلاثين */
  forfeit_amount: string | null;
  currency: string;
  is_driver: boolean;
  /** **خيارُ التحويل يظهر حين يكون مفعّلاً في دولته وحدَه** (قرارُ المالك) */
  transfer_enabled: boolean;
}

/** سلفُ الكباتن (البند ١٥). */
export interface Advance {
  id: string;
  driver_id: string;
  amount: string;
  currency: string;
  status: "outstanding" | "repaid" | "written_off";
  due_at: string;
  settled_at: string | null;
  created_at: string;
}

/** شرطُ أهليةٍ **باسمه ورقمه وحاله** — لا «نقاطَ مصداقية» (قرارُ المالك ١).
 *
 * والنصُّ العربيُّ في التطبيق والرمزُ من الخلفية، كرموز موانع إلغاء التفعيل:
 * الخلفيةُ لا تعرف من يقرأ.
 */
export interface AdvanceRequirement {
  key: string;
  met: boolean;
  value: string | null;
  needed: string | null;
}

export interface AdvanceDebt {
  advance: Advance;
  /** **مطروحٌ من الدفتر** لا عمودٌ على السلفة. */
  remaining: string;
  overdue: boolean;
}

export interface AdvanceState {
  /** **«غيرُ معروضة» غيرُ «رُفضتَ»**: بابٌ لا وجودَ له لا بابٌ يُفتح بعمل. */
  offered: boolean;
  eligible: boolean;
  requirements: AdvanceRequirement[];
  cap: string;
  currency: string;
  debt: AdvanceDebt | null;
  /** شرطُ السداد — يُعرض **قبل** الموافقة: السلفةُ دَينٌ لا إنفاقُ رصيد. */
  deduction_percent: number;
  min_kept_amount: string;
  term_days: number;
}

/** حالُ سدادِ رحلة — **محسوبةٌ في الخلفية، ومرآتُها هنا**
 * (`backend/app/services/settlement.py`).
 *
 * كانت كلُّ شاشةٍ تستنتجها بمقارنةٍ خاصةٍ بها فأخطأت ثلاثٌ من أربع: `pending`
 * تُقرأ «اكتمل الدفع»، ورحلةٌ ملغاةٌ تُقرأ «مسدَّدة»، ونزاعٌ مفتوحٌ لا يُرى.
 * وهي قاعدةُ القسم 14 نفسُها — القرارُ الماليُّ في الخلفية والواجهةُ تعرض.
 */
export type SettlementState =
  | "not_due"
  | "due"
  | "awaiting"
  | "disputed"
  | "settled";

// --------------------------------------------- المهامُّ والمستويات (البند ٥٣)

/** مهمّةُ شهرٍ واحدة — والنصُّ من الإدارة، والأرقامُ حقائق. */
export interface Mission {
  id: string;
  country_code: CountryCode;
  month: string;
  title: string;
  description: string | null;
  metric: string;
  target: string;
  is_active: boolean;
}

/** **حقائقُ لا جملةُ حالة** — «أكملتَ ٢٧ من ٤٠» تبنيها الشاشة. */
export interface MissionProgress {
  mission: Mission;
  value: string;
  target: string;
  done: boolean;
}

export interface Badge {
  id: string;
  key: string;
  label: string;
  description: string | null;
  icon: string | null;
  is_active: boolean;
}

/** **ولا `note` هنا**: سببُ المنح كلامُ مشرفٍ لمشرف لا خطابٌ لصاحبه. */
export interface GrantedBadge {
  badge: Badge;
  granted_at: string;
}

/** شاشةُ المهامّ. **و`level_effect_meters` يُقال بصدق أو لا يُقال**: «يقرّبك
 *  ٥٠م» جملةٌ تُقاس، و«أولويةٌ في الطلبات» وعدٌ يعدّه صاحبُه ولا يجده. */
export interface MyProgress {
  enabled: boolean;
  level: number;
  max_level: number;
  level_computed_at: string | null;
  level_effect_meters: number;
  missions_done: number;
  missions_total: number;
  missions: MissionProgress[];
  badges: GrantedBadge[];
}

// ------------------------------------------- مركباتُ الكراج والمتجر (2026-08-22)

/** درجاتُ الندرة — **مرآةُ `schemas/vehicle_skin.py::Rarity` بحرفها**.
 *
 * وهي في الخلفية **نصٌّ لا تعداد Postgres** (`models/vehicle_skin.py`)، فدرجةٌ
 * خامسةٌ غداً كودٌ بلا ترحيلة — **وهنا كسرُ بناءٍ**، وهو المطلوب: قيمةٌ لا
 * تعرفها الشاشةُ تخرج شارةً بلا لونٍ ولا اسم.
 */
export type Rarity = "common" | "premium" | "rare" | "legendary";

/** كيف تملّكها — يُقرأ في الكراج: هديةٌ أم شراءٌ أم منحةُ إدارة. */
export type AcquireSource = "gift" | "purchase" | "grant";

/** **سببُ عدم إمكان الشراء — واحدٌ لا أكثر**، وترتيبُ أسبقيته في العقد.
 *
 * **وهو حالٌ لا رسالةُ خطأ**: الشاشةُ تسمّيه بكلمةٍ على البطاقة كما تسمّي
 * `RIDE_STATUS_LABEL` حالَ الرحلة، **والرفضُ نفسُه** حين تُضغط ورقةُ الشراء
 * يأتي نصُّه من الخلفية (§17) ولا يُصاغ هنا.
 */
export type SkinBlockedReason =
  | "owned"
  | "sold_out"
  | "level_locked"
  | "out_of_season"
  | "insufficient_balance";

/** مركبةٌ كما يراها الكبتنُ في المتجر أو الكراج — مرآةُ `SkinOut`. */
export interface VehicleSkin {
  id: string;
  name: string;
  rarity: Rarity;
  /** مسارٌ **نسبيّ** يُبنى على أصل الخلفية — `lib/skins.ts::skinAssetUrl`. */
  store_image_url: string;
  map_image_url: string;
  /** ٨٠–١٢٠٪ — يُضرب في مقاسٍ **ثابتٍ في الكود**، لا في مقاس الملف. */
  map_scale_percent: number;
  /** **يُقرأ ولا يُستنتج من الندرة**: الرندرُ الواقعيُّ لا يدور. */
  map_rotates: boolean;
  /** **أين تُراها** — يُكتب في بطاقة المتجر نصّاً: من يدفع يعرف ما يشتري. */
  visible_before_accept: boolean;
  /** `null` غيرُ معروضةٍ للبيع (العاديةُ تُوهب ولا تُباع). **ونصٌّ لا رقم.** */
  price: string | null;
  currency: Currency | null;
  /** `null` بلا حدّ — و`0` نفدت. */
  remaining: number | null;
  owners_count: number;
  level_required: number | null;
  valid_until: string | null;
  owned: boolean;
  active: boolean;
  blocked_reason: SkinBlockedReason | null;
}

/** كراجُ الكبتن — **ومعه ما يحتاجه الكراجُ نفسُه** بنداءٍ واحد (`GarageOut`). */
export interface Garage {
  skins: VehicleSkin[];
  active_skin_id: string | null;
  /** **مركبةٌ وُهبت ولم تُعرض ورقتُها بعد** — تُعرض مرةً ثم تُختم. */
  celebrate: VehicleSkin | null;
  /** **لا اشتراكَ له**: الكراجُ يقوله ليُرسم البديلُ الباهتُ ويظهر الزرّ. */
  has_subscription: boolean;
}

/** المتجرُ — **والترتيبُ عقدٌ لا ذوق**، فلا يُعاد ترتيبُه في الشاشة. */
export interface SkinStore {
  skins: VehicleSkin[];
  balance: string;
  currency: Currency;
  driver_level: number | null;
  /** **مجموعُ ما يُعرض في هذا السوق** — لا طولُ الصفحة. به يعرف
   *  التطبيقُ متى يتوقّف بلا أن يطلب صفحةً فارغةً ليكتشف النهاية. */
  total: number;
}

/** ما يُعرض بعد الشراء — **الرصيدُ الجديدُ من الدفتر لا محسوباً في الشاشة**. */
export interface BuySkinResult {
  skin: VehicleSkin;
  balance_after: string;
  currency: Currency;
}

/** مركبةٌ **كما تُرسم على خريطة** — `MapSkinOut`: رسمٌ لا هوية.
 *
 * **ولا اسمَ ولا ندرةَ فيها بقصد**: على الخريطة الحرّة تكفي الرسمةُ للرسم،
 * و«أسطورية» كلمةٌ تجعل من يعدّ السياراتِ يعرف من في أيّها.
 */
export interface MapSkin {
  skin_id: string;
  /** مسارٌ نسبيٌّ **بسابقة الـAPI** — يُبنى على أصل الخلفية لا أصل الصفحة. */
  image_url: string;
  scale_percent: number;
  rotates: boolean;
}

/** كبتنٌ قريبٌ **مجهَّلٌ كما يراه الراكب** — `NearbyDriverOut` نفسُها.
 *
 * **ومركبتُه المنشورةُ معه**: النادرةُ والأسطوريةُ لا تصلان هنا أبداً
 * (`publishable_skin_for`) — فما يُرى ويندر يصير معرّفاً ينقض تجهيلَ §10.
 * **و`null` لا تميّز أحداً**: لا تقع إلا حين لا بديلَ منشورٌ في الكتالوج
 * كلِّه، فتغيب عن الجميع سواءً.
 */
export interface NearbyDriver {
  ref: string;
  lat: number;
  lng: number;
  heading: number | null;
  vehicle_category: VehicleCategory;
  skin: MapSkin | null;
}

/** مطالبةُ دفعٍ يدويٍّ بكليك — مرآةُ `CliqSubscriptionOut`.
 *
 * **والعددان من اللوحة لا من الشيفرة**: «تتم المراجعة خلال {min} إلى {max}
 * دقائق» **وعدٌ يُعدَّل بلا نشر** يومَ تكثر الطلباتُ ولا تلحق المراجعة.
 *
 * **و`qr_url` قد تكون `null`** — والشاشةُ تعمل بلا صورة: حسابٌ ومبلغٌ ومرجع،
 * وسطرٌ يقول إن الرمزَ لم يُرفع. **فلا تسقط على حقلٍ فارغ.**
 */
export interface CliqSubscriptionClaim {
  id: string;
  cart_id: string;
  amount: string;
  currency: Currency;
  status: "created" | "paid" | "failed" | "cancelled";
  qr_url: string | null;
  /** **لحظةُ قوله «حوّلتُ»** — و`null` تعني «فتح الشاشةَ ولم يقل بعد».
   *  **وعليها تُبنى حالُ الشاشة**: زرُّ «تمّ الدفع» أو نافذةُ المراجعة. */
  declared_paid_at: string | null;
  alias: string;
  review_min_minutes: number;
  review_max_minutes: number;
  failure_reason: string | null;
  created_at: string;
}

// ═══════════════ دَينُ الكبتن (الترحيلة `0061`) ═══════════════
//
// **بيتٌ ثالثٌ للدَّين لا رصيدٌ سالب**: عمولةُ رحلةٍ قبضها بيده تخرج من
// الدفتر إلى جدولها، فلا يُمنع من إنهاء رحلةٍ لأن رصيدَه لا يغطّي عمولتَها
// — وهو العطبُ الذي كان حيّاً قبل 2026-08-30.

// **و«بين المدن» مصدرٌ ثانٍ** (§٦٣-ج/٧): السيارةُ كاملةً تُدفع له نقداً، وعمولتُها دَينٌ كعمولة رحلات النقد
export type DriverDebtSource = "ride_commission" | "intercity_commission";
export type DriverDebtStatus = "outstanding" | "settled" | "written_off";

export interface DriverDebtRow {
  id: string;
  source: DriverDebtSource;
  amount: string;
  collected: string;
  currency: Currency;
  status: DriverDebtStatus;
  ride_id: string | null;
  created_at: string;
}

export interface DriverDebtState {
  total: string;
  /** **ما يُحوَّل لسداد الدَّين كلِّه** (SPEC §٧٠-ج/٦) — `total` مقرَّباً **للأعلى** إلى وحدة السوق، **والزائدُ يعود إلى محفظته
   *  قيداً صريحاً** عند التأكيد. **محسوبٌ في الخلفية لا هنا** (§١٤)، ومطفأً هو `total` نفسُه. */
  pay_all_amount: string;
  currency: Currency;
  /** العَلَمُ الذي يقرؤه التوزيع — لا حسابٌ تعيده الشاشة. */
  blocked: boolean;
  /** `null` = لا سقفَ مضبوط، فلا يُعرض رقمٌ لا وجود له. */
  ceiling: string | null;
  /** سبيلُ السداد — و`null` تعني «لم يُضبط بعد» فلا يُرسم حسابٌ فارغ. */
  cliq_alias: string | null;
  review_min_minutes: number;
  review_max_minutes: number;
  rows: DriverDebtRow[];
}

export interface DebtClaim {
  id: string;
  cart_id: string;
  amount: string;
  currency: Currency;
  /** **نفسُ اتحاد مطالبة الاشتراك حرفاً** — قضيبٌ واحدٌ فحالٌ واحدة. */
  status: "created" | "paid" | "failed" | "cancelled";
  failure_reason: string | null;
  created_at: string;
  qr_url: string | null;
  /** **لحظةُ قوله «حوّلتُ»** — و`null` تعني «فتح الشاشةَ ولم يقل بعد».
   *  **وعليها تُبنى حالُ الشاشة**: زرُّ «تمّ الدفع» أو نافذةُ المراجعة. */
  declared_paid_at: string | null;
  alias: string;
  review_min_minutes: number;
  review_max_minutes: number;
}

// ═══════ بلاطاتُ الخدمات واللافتات (الترحيلة `0063`) ═══════
//
// **تُدار من اللوحة لا تُخبز**: إضافةُ خدمةٍ أو لافتةٍ **بلا نشر**.
// **والتصفيةُ في الخلفية**: الجمهورُ والسوقُ والنافذة — فثلاثةُ تطبيقاتٍ
// تسأل السؤالَ نفسَه ولا تحسبه ثلاث مرّات.

export type ServiceTileStatus = "soon" | "active" | "hidden";
export type BannerLinkKind = "internal" | "external" | "none";

export interface ServiceTile {
  id: string;
  key: string;
  title: string;
  subtitle: string | null;
  /** اسمُ أيقونةِ lucide كما تكتبه اللوحة. */
  icon: string;
  status: ServiceTileStatus;
  /** `null` مع «قريباً» — وهي **تُقرأ ولا تُنقر**. */
  destination: string | null;
  /** **محسوبةٌ في الخلفية**: ساعةُ الجهاز يملكها صاحبُه. */
  is_new: boolean;
}

export interface PromoBanner {
  id: string;
  title: string;
  body: string | null;
  /** **الرقمُ الكبير** («30%»، §٦٢-ج/٢٦) — نصٌّ قصيرٌ يكتبه المشرف، و`null` لافتةٌ بلا رقم. */
  headline: string | null;
  /** **أيقونةُ lucide** — زخرفيّةٌ بجانب النصّ، وهي غيرُ صورة اللافتة:
   *  الصورةُ بايتاتٌ تُجلب من `/storefront/banners/{id}/image` (منذ 08-31)،
   *  **ولا حقلَ يقول «لها صورة»** — الطلبُ نفسُه هو الجواب. */
  icon: string | null;
  link_kind: BannerLinkKind;
  link: string | null;
}

/** عرضُ اشتراكٍ حيٌّ **لهذا الكبتن بعينه** — يُعرض في صندوق اللافتات نفسِه.
 *
 * **ولا كيانَ ثانياً بجانب `promo_banners`** (قرارُ المالك 2026-09-07):
 * الصندوقُ واحدٌ، ومصدراه اثنان — **صفوفٌ يكتبها المشرف**، **وعرضٌ يُحسب
 * لكلِّ كبتنٍ على حدة** بجمهوره وحدِّه وميزانيته.
 *
 * **والأرقامُ تصل محسوبةً ولا تُطرح هنا** (§14): `price` و`price_after`
 * عمودان، **و«مجاناً» كلمةٌ في `free` لا رقمٌ صفر يُقرأ خطأً**.
 *
 * **و`null` للراكب دائماً**: الاشتراكُ للكبتن وحدَه — والحقلُ مُصرَّحٌ في
 * التطبيقين لأن الصندوقَ مكوّنٌ واحدٌ **متطابقٌ بايتاً**، ونسختان تفترقان
 * أوّلَ تعديل. */
export interface StorefrontOffer {
  /** **اسمُ العرض كما كتبه المشرفُ في اللوحة** — لا نصٌّ مؤلَّفٌ في الشيفرة. */
  name: string;
  plan_name: string;
  price: string;
  price_after: string;
  currency: Currency;
  free: boolean;
}

export interface Storefront {
  tiles: ServiceTile[];
  banners: PromoBanner[];
  offer: StorefrontOffer | null;
}


/** جوابُ «حوّلتُ» — **وقتُ الختم هو ما تقرؤه الشاشة**. */
export interface CliqDeclare {
  cart_id: string;
  /** **لحظةُ قوله «حوّلتُ»** — و`null` لا تقع من هذا الباب أبداً. */
  declared_paid_at: string | null;
  status: "created" | "paid" | "failed" | "cancelled";
}

// ------------------------------------------------- بوّابةُ التحديث (البند ٨)

/** حكمُ الإقلاع — **محسوبٌ في الخلفية لا هنا** (§43).
 *
 * ثلاثةُ تطبيقاتٍ تقارن رقمين بأنفسها ثلاثُ نسخٍ من قاعدةٍ واحدة، تفترق
 * أوّلَ ما تتغيّر ولا شيءَ يفشل — وهي §14 مطبَّقةً على حكمٍ لا على مبلغ.
 *
 * **و`ok` بحقولٍ فارغةٍ تعني «لا سجلَّ لهذا التطبيق»**: غيابُ السجلِّ يعطّل
 * الحجبَ لا التطبيق.
 */
export interface AppVersion {
  state: "ok" | "optional" | "forced";
  /** `versionCode` آخرِ حزمةٍ مسجَّلة — لا اسمُ نسخة. */
  latest_build: number | null;
  min_supported_build: number | null;
  download_url: string | null;
  release_notes: string | null;
  /** كم يسكت التنبيهُ الاختياريُّ بعد إغلاقه — **من اللوحة لا من التطبيق**. */
  reminder_hours: number | null;
}

/** وثيقةٌ يلزم قبولُها قبل إنشاء حساب — **بمعرّفها ونصِّها معاً**.
 *
 * **والمعرّفُ يُرسَل لا `true`**: علامةٌ منطقيةٌ تقول «وافق» ولا تقول **على
 * ماذا**، فتستنتج الخلفيةُ «المنشورَ الآن» — **ونشرةٌ تقع بين القراءة
 * والإرسال تكتب موافقةً على نصٍّ لم يُقرأ**.
 */
export interface RequiredPolicy {
  id: string;
  doc_type: "privacy_policy" | "terms_of_use";
  app: string;
  version: number;
  body_ar: string;
  published_at: string | null;
}

/** حمولةُ تقرير العطب — **تعريفٌ واحدٌ يقرؤه البابُ والمُرسِل**.
 *
 * ونسختان تفترقان أوّلَ حقلٍ يُضاف، **فيُرسل العميلُ ما لا يقبله الباب**.
 * والخلفيةُ تُسقط ما ليس هنا أصلاً (`schemas/error_report.py`) — فهذا
 * التعريفُ **مرآةُ قائمةٍ بيضاءَ لا مصدرُها**.
 */
export type ErrorReportBody = {
  app: "rider" | "driver" | "panel";
  kind: "error" | "rejection" | "boundary" | "user_report";
  platform: "android" | "ios" | "web";
  release?: string;
  channel?: string;
  os_version?: string;
  device_hash: string;
  route?: string;
  name: string;
  message: string;
  stack?: string;
  component_stack?: string;
  /** خطواتُ ما قبل العطب — **الخادمُ يعيد بناءها من مفاتيحَ مسمّاة**. */
  breadcrumbs?: Crumb[];
  occurred_at: string;
  online: boolean;
  repeat: number;
  request_id?: string;
  note?: string;
};

// ------------------------------------------------ الحجزُ المضمون (§٦٣-ج/٣)

/** حجزٌ مضمونٌ كما يراه الكبتن (`GuaranteeOfferOut`) — عرضاً في «عروضٌ تنتظرك» أو مقبولاً في «القادمة».
 *
 * **بلا اسم الراكب ولا رقمه** — لا يراهما في رحلةٍ عاديّةٍ أصلاً. **والأجرةُ تقديرُ لحظة الحجز**: تُحسب عند التنفيذ.
 */
/** **ما يكلّفه إلغاءُ الكبتن رحلتَه الآن** (§٦٣-ج/٣، §٦٤-د) — يُقرأ في ورقة الإلغاء قبل «تأكيد الإلغاء».
 *
 * `cancel_penalty` رسمُ الضمان المجمَّد حيث رحلةٌ مضمونةٌ أكّدها هو، و`null` حيث لا كلفة. **ويخرج من محفظته بقدر رصيده**
 * (`APPROVALS-62` §٥-١/١٣) — فالسطرُ يقول «حتى». والعتبةُ والأيامُ من إعدادات سوقه لا من الشاشة. */
export interface GuaranteeCancelCost {
  cancel_penalty: string | null;
  currency: Currency;
  ban_threshold: number;
  ban_days: number;
}

export interface GuaranteeOffer {
  id: string;
  scheduled_at: string;
  vehicle_category: VehicleCategory;
  pickup_lat: number;
  pickup_lng: number;
  pickup_address: string | null;
  dropoff_lat: number;
  dropoff_lng: number;
  dropoff_address: string | null;
  /** تقديرٌ لحظةَ الحجز — **لا أجرة**: تُحسب عند التنفيذ. */
  estimated_fare_at_booking: string | null;
  /** **رسمُ الضمان له كاملاً** حين تتمّ الرحلةُ معه في وقتها — مجمَّدٌ على الحجز. */
  guarantee_fee: string;
  currency: Currency;
  accepted: boolean;
  /** **سُئل «هل أنت في الطريق؟»** — يُفتح التأكيدُ قبل الموعد بدقائقِ سوقه، وبلا ردٍّ في المهلة يُسحب منه بلا عقوبة. */
  confirm_requested: boolean;
}

/** **عرضُ المشوار الثابت** كما يراه الكبتن (§٦٣-ج/٦، `CommuteOfferOut`) — **بلا اسم الراكب ولا رقمه**: المسارُ والأيامُ (قناعُ بتاتٍ
 *  بترتيب `weekday()`: الإثنين 1 … الأحد 64) والوقتان «HH:MM:SS» والمدّة، **وسعرُ الرحلة المجمَّدُ وعددُها من الخلفية** — ولا يُضربان
 *  هنا (§14). و`approved` أله كبتنٌ معتمد. */
export interface CommuteOffer {
  id: string;
  pickup_address: string | null;
  dropoff_address: string | null;
  weekdays: number;
  go_time: string;
  return_time: string | null;
  starts_on: string;
  ends_on: string;
  price_per_ride: string;
  rides_total: number;
  currency: Currency;
  approved: boolean;
}

// ═══════════════ بين المدن (§٦٣-ج/٧) ═══════════════
//
// **الكبتنُ سيّدُ رحلته**: يعلنها بمقاعدها وأقلِّ عددٍ ينطلق به، ويلغيها قبل المهلة بلا أثر، وينطلق وينهي — **بتصريحٍ يمنحه
// مشرفٌ بعد فحص المركبة**. والأسعارُ من المسار يضبطها المالك، **وتُجمَّد على الرحلة لحظةَ إعلانها**.

/** **مسارٌ مفعَّلٌ في سوقه** (`RouteOut`) — مدينتان بنقطتي تجمّع، **وسعرا المقعد والسيارة من الخلفية** نصّاً، لا يُحسب منهما شيء. */
export interface IntercityRoute {
  id: string;
  country_code: CountryCode;
  from_city: string;
  to_city: string;
  from_lat: number;
  from_lng: number;
  from_point: string;
  to_lat: number;
  to_lng: number;
  to_point: string;
  price_car: string;
  price_seat: string;
  is_active: boolean;
}

/** **راكبٌ في رحلته** — **الاسمُ قبل الانطلاق بساعة، والرقمُ عند الانطلاق وحدَه** (§٦٣-هـ): قبلهما لا يصل شيءٌ، و`phone` `null`
 *  ما دامت لم تنطلق. ومقاعدُه عددٌ (السيارةُ كاملةً مقاعدُها كلُّها). */
export interface IntercityPassenger {
  name: string;
  seats: number;
  phone: string | null;
}

/** **رحلتُه كما يراها** (`TripOut`) — المقاعدُ عددان من الخلفية (المعروضةُ والمحجوزة) وأقلُّ ما ينطلق به، **والسعران المجمَّدان**.
 *  و`status` **نصٌّ لا اتحادٌ مسمّى بقصد**: عمودٌ نصّيٌّ بقيدٍ في القاعدة لا `StrEnum`، فاتحادٌ باسمٍ يخلط `departed` بقيمٍ يعرفها
 *  `check:enums` من تعداداتٍ أخرى. */
export interface IntercityTrip {
  id: string;
  route: IntercityRoute;
  departs_at: string;
  seats_offered: number;
  seats_booked: number;
  min_seats: number;
  price_car: string;
  price_seat: string;
  currency: Currency;
  status: "open" | "departed" | "completed" | "cancelled";
  passengers: IntercityPassenger[];
}

// ═════════════════════════ محادثةُ الرحلة ومكالمتُها (SPEC §٦٦) — مرايا `schemas/trip_chat.py` و`schemas/ride_call.py`
//
// **ولا رقمَ هاتفٍ ولا اسمَ في شيءٍ منها**: الطرفان يقرآن الجانبَ لا الاسم، **واسمُ الكبتن عند الراكب من الرحلة نفسِها**
// (`ride.driver`) كما يراه اليوم — لا من المحادثة. **والنسخةُ نفسُها في تطبيق الراكب حرفاً**.

/** **جانبُ المرسل أو المتصل** — مرآةُ `RatingRaterType`. */
export type CommsSide = "rider" | "driver";

export interface ChatMessage {
  id: string;
  ride_id: string;
  sender_role: CommsSide;
  /** **منّي؟** — من الخادم، فلا يحسبها التطبيقُ من دوره */
  mine: boolean;
  body: string;
  created_at: string;
  read_at: string | null;
}

/** حالُ مكالمةٍ لأحد طرفَيها (`RideCallOut`) — **و`mine` تقول هل أنا المتصل**. */
export interface RideCall {
  id: string;
  ride_id: string;
  status: "ringing" | "active" | "ended";
  caller_role: CommsSide;
  mine: boolean;
  recording: boolean;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  end_reason: "completed" | "declined" | "no_answer" | "failed" | "ride_ended" | "cancelled" | null;
}

/** **المحادثةُ لطرفها** (`ChatThreadOut`) — وفتحُها يعلّم رسائلَ الطرف الآخر مقروءة، **فلا يُطلب إلا حين تُفتح**. */
export interface ChatThread {
  ride_id: string;
  /** **يُكتب فيها؟** — في النافذة والمفتاحُ مشتعل */
  open: boolean;
  /** **يُرسم زرُّ الاتصال؟** — بالحكم نفسِه لمفتاح المكالمة */
  can_call: boolean;
  /** ما كان جديداً عند هذا الفتح — وقد علّمه الفتحُ مقروءاً */
  unread: number;
  /** سطرُ المراجعة بحرف التصميم المُقَرّ — من الخادم لا من التطبيق */
  notice: string;
  max_chars: number;
  messages: ChatMessage[];
  /** المكالمةُ الحيّةُ إن وُجدت — يعود إليها تطبيقٌ فُتح من إشعار */
  active_call: RideCall | null;
}

/** أسبابُ البلاغ الأربعةُ المُقَرّة — مرآةُ `RideMessageReportReason`. */
export type ChatReportReason = "abuse" | "harassment" | "fraud" | "other";

export interface ChatReport {
  id: string;
  message_id: string;
  reason: ChatReportReason;
  status: "open" | "handled";
  created_at: string;
}

/** `RTCIceServer` كما يقبله المتصفّح — **ببياناتٍ مؤقّتةٍ من مُرحِّلنا**، وقائمةٌ فارغةٌ في التطوير. */
export interface IceServer {
  urls: string[];
  username: string;
  credential: string;
}

export interface CallStart {
  call_id: string;
  ride_id: string;
  ice_servers: IceServer[];
  /** **مسجَّلة؟** — وإن كانت فلا يُمرَّر عرضي حتى أُقِرّ بالتنبيه */
  recording: boolean;
  ring_timeout_seconds: number;
}

export interface CallAnswer {
  call_id: string;
  ride_id: string;
  ice_servers: IceServer[];
  recording: boolean;
}
