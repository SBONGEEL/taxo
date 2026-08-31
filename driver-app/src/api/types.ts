/** أنواع ما تردّه الخلفية — مرآةٌ لـ`backend/app/schemas/`.
 *
 * ما يخصّ الكبتن وحده. وكلُّ نوعٍ هنا يقابل مخططاً في الخلفية بالاسم نفسه،
 * فمن غيّر هناك يجد مقابله هنا باسمه.
 */

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
}

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
  providers: Record<string, Record<string, string | undefined>>;
  /** الدولة التي تفترضها شاشاتُ ما قبل الدخول (لا منتقيَ دولٍ فيها). */
  default_country_code: CountryCode;
  /** قواعدُ التحقق مُشتقّةً من مخططات الخلفية (SPEC ١٧.٣).
   *
   * **ولا نسخةَ منها مكتوبةً هنا**: حدٌّ يُكتب في التطبيق يفترق عن حدِّ المخطط
   * أوّلَ تعديل، فيمنع التطبيقُ ما تقبله الخلفيةُ أو يقبل ما ترفضه. ونصوصُها
   * من السجل المركزي نفسِه، فلا تختلف رسالةُ الشاشة عن رسالة الخادم.
   */
  validation: Record<string, Record<string, FieldRule>>;
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
  rating_avg: string;
  is_online: boolean;
  current_ride_id: string | null;
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
  | "skin_purchase";

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
  /** يُحسب في الخلفية كبقية المال (§14) — لا يُطرح في المتصفح. */
  price_after_discount: string | null;
  offer_ends_at: string | null;
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

/** مرآةُ `PaymentMethod` — أربعُ قنوات. **ولا `mixed` فيها**: الدفعُ المختلط
 * (محفظة + كاش) **صفّان** على رحلةٍ واحدة لا قناةٌ ثالثة، ولذلك لا فهرس فريد
 * على `payments.ride_id` أصلاً (القسم 6). */
/** ومنها `promo` (12-ز): خصمُ كوبونٍ تدفعه الشركة — يُقيَّد للكبتن كأي دفعةٍ
 *  تمرّ بالمنصة، فيراه في كشفه لا في «تقبض الآن». */
export type PaymentMethod =
  "cash" | "wallet" | "card" | "cliq" | "promo" | "share";
/** مرآةُ `PaymentStatus` في `app/models/enums.py` — خمسُ قيمٍ لا ستّ.
 *
 * ولا `awaiting_confirmation` فيها: انتظارُ تأكيد الكبتن **ليس حالاً** بل
 * `pending` على قناةٍ يقبضها بيده — والتمييز من `method` لا من حقلٍ سادس. */
export type PaymentStatus =
  "pending" | "confirmed" | "failed" | "refunded" | "disputed";

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
export interface DeactivationRequest {
  id: string;
  driver_id: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reason: string | null;
  review_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface DeactivationState {
  request: DeactivationRequest | null;
  /** **قائمةٌ لا أوّلُ سبب**: من أزال مانعاً ثم صُدم بثانٍ يقرأ الرفضَ مماطلة. */
  blockers: string[];
  reserve_amount: string;
  currency: string;
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

export type DriverDebtSource = "ride_commission";
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
  /** **أيقونةُ lucide لا صورةٌ مرفوعة** — لا بابَ يخدم رفعاً بعد،
   *  **وعنوانٌ يُنشر لمسارٍ لا وجودَ له يرسم صورةً مكسورة**. */
  icon: string | null;
  link_kind: BannerLinkKind;
  link: string | null;
}

export interface Storefront {
  tiles: ServiceTile[];
  banners: PromoBanner[];
}
