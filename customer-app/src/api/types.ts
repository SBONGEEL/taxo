/** أنواع ما تعيده الخلفية — مرآةٌ لـ `backend/app/schemas`.
 *
 * تُكتب بيدٍ ولا تُولَّد: التوليد من OpenAPI يجرّ أداةً وخطوةَ بناءٍ لواجهةٍ
 * تقرأ عشرين مساراً. وما يهم هنا أن يكون كل حقلٍ **بنفس اسمه ونوعه** في
 * الطرفين — فالمبالغ نصوصٌ لا أرقام (`NUMERIC(12,3)` يصل JSON نصّاً، وتحويله
 * إلى `number` يفتح باب الفاصلة العائمة على مالٍ حقيقي).
 */

export type CountryCode = "JO" | "LY";
export type Currency = "JOD" | "LYD";
export type VehicleCategory = "economy" | "comfort";
export type UserRole = "rider" | "driver" | "admin" | "support";

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

/** ومنها `promo` (12-ز): **قناةٌ لا يدفعها الراكب** — تُنشئها المنصةُ بقيمة
 *  خصم الكوبون فتظهر صفَّاً في الإيصال. لا تُعرض خياراً في شاشة الدفع. */
export type PaymentMethod =
  "cash" | "cliq" | "card" | "wallet" | "promo" | "share";
export type PaymentStatus =
  "pending" | "confirmed" | "failed" | "disputed" | "refunded";

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

export interface AuthMethod {
  login: "password";
  verification: VerificationMethod;
  otp_length: number | null;
  /** **أيُعرض بابُ «سجّل ببريدك» في هذا السوق؟** — العقدُ والمفتاحُ معاً.
   *
   *  **وليس عضواً في `verification_channels`**: تلك تُثبت **ملكيةَ الرقم**،
   *  والبريدُ يُثبت البريد — وخلطُهما يفتح حساباً كاملَ الصلاحية برقمٍ لم
   *  يملكه أحد. */
  email_signup: boolean;
  /** القنواتُ المهيأة بترتيب الأولوية — أوّلُها هو `verification` (12-هـ). */
  channels?: string[];
}

/** تفضيلُ جنس الطرف الآخر — مرآةُ `GenderPreference` في الخلفية. */
export type GenderPreference = "male" | "female" | "any";

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
  /** **السببُ والطريقُ لمن أُوقف** — أو `null` (حملةُ تأكيد الأرقام).
   *
   *  **ويُبنى في الخلفية لا هنا**: التطبيقُ لا يكتب عربيّةً لخطأٍ سمّاه
   *  الخادم. **ولا يُشتقّ من `phone_pending`**: ذاك حسابٌ **وُلد محدوداً**،
   *  وهذا **كان كاملاً فأُوقف** — ورسالتاهما مختلفتان. */
  suspension: { code: string; message: string } | null;
  /** بريدُه إن أثبته — و`null` تعني لا بريدَ مُثبَت. */
  email: string | null;
  /** تعلنه الراكبة عن نفسها (المرحلة 10-ج)؛ `null` = لم تعلن. */
  gender: "male" | "female" | null;
  /** ختمُ المشرف — للكبتن وحده، وفارغٌ عند الراكبة دائماً. */
  gender_verified_at: string | null;
  /** تفضيلُها الافتراضي لجنس الكبتن — يُنسخ إلى الرحلة عند الطلب. */
  ride_gender_preference: GenderPreference;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_at: string;
}

export interface AuthResponse {
  user: User;
  tokens: TokenPair;
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
  /** القناةُ التي أُرسل فيها الرمز فعلاً — تقولها الشاشة لصاحبها. */
  channel: string | null;
}

/** معاينةُ كوبونٍ كما ردّتها الخلفية (12-ز) — **لا تحسبها الشاشة**. */
export interface PromoPreview {
  code: string;
  discount_type: "percent" | "fixed";
  discount: string;
  fare_after: string;
  currency: Currency;
}

/** البقشيش (المرحلة 12-و) — **والخلفيةُ تقرّر أن يُعرض أصلاً**. */
export interface TipOptions {
  offered: boolean;
  currency: Currency;
  presets: string[];
  max_amount: string;
  given: Tip | null;
}

export interface Tip {
  id: string;
  ride_id: string;
  amount: string;
  currency: Currency;
  created_at: string;
}

export interface CountryConfig {
  country_code: CountryCode;
  currency: Currency;
  features: Record<string, boolean>;
  vehicle_categories: VehicleCategory[];
  /** بادئةُ الدولة وطولُ رقمها الوطني — من `core/phone.py` عبر `/config`. */
  dial_code: string;
  national_number_length: number;
  /** ساعاتُ هدوء الحملات ومنطقتُها (`FUTURE-FEATURES` 5) — تنشرها الخلفيةُ منذ
   *  المرحلة 8 ولم يكن هذا النوعُ يحملها، فلم تصل الشاشة. و`null` تعني «لم
   *  تُضبط بعد» فلا يُعرض رقمٌ لا مصدرَ له. */
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
  providers: {
    mapbox?: { public_token?: string };
    firebase_auth?: {
      project_id?: string;
      api_key?: string;
      auth_domain?: string;
      app_id?: string;
    };
    fcm?: {
      project_id?: string;
      api_key?: string;
      app_id?: string;
      sender_id?: string;
      vapid_key?: string;
    };
    cliq_acquirer?: { endpoint?: string; company_alias?: string };
    payout?: { endpoint?: string };
    sms?: { provider_name?: string; sender_id?: string; endpoint?: string };
    telr?: { test_mode?: boolean };
  };
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

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface RideEstimate {
  country_code: CountryCode;
  vehicle_category: VehicleCategory;
  currency: Currency;
  distance_km: string;
  duration_min: string;
  estimated_fare: string;
  minimum_fare_applied: boolean;
  /** سعرُ المشاركة **محسوباً في الخلفية** (12-ي): الخصمُ والأجرةُ بعده.
   *
   *  و`null` تعني «لا مشاركةَ في هذا السوق» — وليست صفراً: صفرٌ في حقلِ مالٍ
   *  يُقرأ سعراً، والغيابُ يُقرأ غياباً. والتطبيقُ لا يضرب نسبةً في أجرةٍ
   *  ليصل إليهما (القسم 14). */
  share_discount: string | null;
  share_fare: string | null;
  /** شروطُ الوقوف كما ستُجمَّد لو طُلبت الرحلةُ الآن (§5.10).
   *
   *  **ومحلُّها التقديرُ لا `/config`**: الأربعةُ لكلِّ (دولة × فئة)، والتقديرُ
   *  هو الموضعُ الذي عُرفت فيه الفئة. ومنها تُصاغ الجملةُ التي يقرؤها الراكب
   *  **قبل** أن يقبل السعر — لا من ثابتٍ في التطبيق (القسم 14). */
  stop_fee: string;
  stop_free_minutes: number;
  stop_price_per_min: string;
  stop_max_wait_minutes: number;
}

export interface RideVehicle {
  make: string;
  model: string;
  color: string;
  plate_number: string;
  category: VehicleCategory;
}

/** مركبةُ الكبتن كما تُرسم — **رسمٌ لا هوية** (`MapSkinOut` في الخلفية).
 *
 * **أربعةُ حقولٍ لا أكثر، وهذا هو العقد**: لا اسمَ ولا ندرةَ ولا سعر —
 * **لأن ما يُرى ويندر يصير معرّفاً** ينقض تجهيلَ §10. والمعرّفُ موجودٌ
 * ليُميَّز رسمان بلا مقارنةِ نصوصِ مسارات، لا ليُستعلَم به.
 *
 * **و`image_url` يحمل سابقةَ الـAPI** (`/api/v1/vehicle-skins/…/art/map`)،
 * لأن `<img src="/…">` يُبنى على **أصل الصفحة** لا على أصل الـAPI — وهما
 * مضيفان مختلفان هنا. و`lib/skin.ts` هو من يبني العنوانَ الكامل.
 */
export interface RideDriverSkin {
  skin_id: string;
  image_url: string;
  /** **يُضرب في الحجم الثابت المكتوب في `lib/skin.ts`** — يضبطه المشرف. */
  scale_percent: number;
  /** **العلويّةُ المرسومةُ تدور مع الاتجاه، والرندرُ الواقعيُّ لا يدور** —
   *  ويُقرأ من الصفّ **ولا يُستنتج من الندرة**. */
  rotates: boolean;
}

export interface RideDriver {
  id: string;
  name: string;
  rating_avg: string;
  vehicle: RideVehicle | null;
  /** مركبتُه النشطة — **تصل بعد القبول**، و`null`/غيابٌ يعني «ارسم السيارةَ
   *  العامّة» **بلا أيِّ فرقٍ مرئيّ** (الشكلُ الثالثَ عشر). */
  skin?: RideDriverSkin | null;
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
  /** ما طُلب في هذه الرحلة من جنس الكبتن — **تفضيلُ الطلب لا جنسُ أحد**. */
  gender_preference: GenderPreference;
  driver: RideDriver | null;

  /** المشاركة (12-ي): نسبةُ الخصم **المجمَّدة** على هذه الرحلة، ومجموعتُها
   *  ومقعدُها فيها. وصفرُ النسبة يعني «رحلةٌ منفردة» — ولا عمودَ ثانٍ يخالفه.
   *
   *  **والنسبةُ لا تُضرب في التطبيق**: ما يُعرض من مال يصل محسوباً (القسم 14)،
   *  وهذه تُقرأ لسؤالٍ واحد: هل هذه رحلةٌ مشتركة. */
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
  /** رسمُ الانتظار **حتى اللحظة** — يصل محسوباً ويتجدد مع كل قراءة. */
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

/** محطةٌ وسيطة ومعها **ما استحقّ عندها** — والمبلغُ محسوبٌ في الخلفية.
 *
 * الواجهةُ ترسم العدّاد من `arrived_at` (حسابُ وقت)، ولا تحسب مبلغاً
 * (حسابُ مال — القسم 14). فما تعرضه من رسمٍ هو `waiting_charge` كما وصل.
 */
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
  over_max_wait: boolean;
}

/** مكانٌ محفوظ — و`icon` نصٌّ محروسٌ في الخلفية لا `ENUM` في القاعدة. */
export type PlaceIcon = "home" | "work" | "star";

export interface SavedPlace {
  id: string;
  label: string;
  address: string | null;
  lat: number;
  lng: number;
  icon: string;
  created_at: string;
}

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
  provider: string | null;
  provider_payment_id: string | null;
  amount: string;
  currency: Currency;
  status: PaymentStatus;
  confirmed_by: string | null;
  confirmed_at: string | null;
  transaction_id: string | null;
  cliq_alias: string | null;
  cliq_reference: string | null;
  cliq_transfer_reference: string | null;
  cliq_reference_at: string | null;
  dispute_reason: string | null;
  disputed_at: string | null;
  resolution: string | null;
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

/** بطاقة دفع كليك: ما يُمسح، وما يُفتح، وما يُكتب (SPEC القسم 6.2). */
export interface CliqCharge {
  payment_id: string;
  alias: string;
  reference: string;
  amount: string;
  currency: Currency;
  qr_payload: string;
  deep_link: string;
  transfer_reference: string | null;
  transfer_reference_at: string | null;
}

export interface CardOrder {
  cart_id: string;
  provider: string;
  purpose: string;
  status: "created" | "paid" | "failed" | "cancelled";
  amount: string;
  currency: Currency;
  redirect_url: string | null;
  failure_reason: string | null;
  transaction_id: string | null;
  created_at: string;
}

export interface RidePayments {
  ride_id: string;
  currency: Currency;
  final_fare: string | null;
  outstanding: string;
  settlement: SettlementState;
  /** **رسمُ إلغاءٍ سابقٌ يُسدَّد مع هذه الرحلة** (`CANCELLATION-FEE.md` §4/§5)
   *  — **بجانب `outstanding` لا داخله**: ذاك أجرةُ هذه الرحلة ومنها تُحسب
   *  العمولةُ ونصيبُ الكبتن. ويُعرض كي يعرف الراكبُ كم يسلّم نقداً. */
  cancellation_debt: string;
  payments: Payment[];
  cliq_charge: CliqCharge | null;
  card_order: CardOrder | null;
}

export interface Wallet {
  owner_id: string;
  owner_type: "rider" | "driver";
  balance: string;
  currency: Currency;
  frozen: boolean;
  /** رسومُ إلغاءٍ عليه لم تُحصَّل — تُعرض **بجانب** الرصيد لا مطروحةً منه. */
  cancellation_debt: string;
  pending_compensation: string;
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
  // **الستّةُ أُضيفت 2026-09-07**: كانت في الخلفية ولا يعرفها الراكب،
  // **فتُرسم بمفتاحها الإنجليزيّ في دفتر محفظته** — وهو أسوأُ من اللوحة:
  // المشرفُ يعرف المفاتيح، **والراكبُ لا يعرف شيئاً**.
  | "skin_purchase"
  | "referral_bonus"
  | "advance"
  | "advance_repayment"
  | "cancellation_fee"
  | "cancellation_compensation";

export interface WalletTransaction {
  id: string;
  owner_id: string;
  owner_type: "rider" | "driver";
  type: WalletTransactionType;
  amount: string;
  balance_after: string;
  currency: Currency;
  ride_id: string | null;
  reference: string | null;
  created_at: string;
}

export interface TopupRequest {
  id: string;
  owner_id: string;
  method: "cliq" | "cash" | "card";
  amount: string;
  currency: Currency;
  reference: string | null;
  note: string | null;
  status: "pending" | "confirmed" | "rejected";
  transaction_id: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface CliqTopup {
  cart_id: string;
  amount: string;
  currency: Currency;
  status: "created" | "paid" | "failed" | "cancelled";
  qr_payload: string | null;
  deep_link: string | null;
  transaction_id: string | null;
}

export interface TransferRecipient {
  phone: string;
  name: string;
}

export interface SavedCard {
  id: string;
  provider: string;
  brand: string | null;
  last4: string;
  expiry_month: number;
  expiry_year: number;
  is_default: boolean;
  created_at: string;
}

export interface Rating {
  id: string;
  ride_id: string;
  rater_type: "rider" | "driver";
  stars: number;
  comment: string | null;
  created_at: string;
}

/** كبتنٌ قريبٌ على الخريطة الحرّة — **مجهَّلٌ بحكم §10**.
 *
 * **و`skin` تُقرأ وتُرسم** (قرارُ المالك 2026-08-22). والحمايةُ ليست في صمت
 * هذه المرآة بل في **الخلفية**: `publishable_skin_for` لا تُرسل نادرةً هنا
 * أبداً — تُرسل النشطةَ إن كانت `visible_before_accept`، **وإلّا البديلَ
 * المنشور**، وهو **أشيعُ ما يُملَك** (مركبةُ الهدية) فلا يفرّق من يعدّ
 * السيارات. **ولا تُرسل `null` لمن هو على الخريطة**: غيابُها يقول «عنده
 * نادرة» — وهو الشكلُ الثالثَ عشر بعينه.
 *
 * **ولمَ لا تُترك مسقَطة**: حقلٌ ينتقل على السلك ولا يقرؤه أحدٌ **بابٌ بلا
 * زرّ** — وهو الشكلُ الذي بُني له `check:doors` في هذا المشروع.
 */
export interface NearbyDriver {
  ref: string;
  lat: number;
  lng: number;
  heading: number | null;
  vehicle_category: VehicleCategory;
  skin?: RideDriverSkin | null;
}

export interface Device {
  id: string;
  device_id: string;
  platform: "ios" | "android" | "web";
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface NotificationPreferences {
  marketing_push_enabled: boolean;
}

/** حالُ حجزٍ مجدول (12-ط) — **ثلاثٌ ولا رابعة**: ما جرى بعد التسليم تقوله
 *  الرحلةُ نفسُها، فلا `fulfilled` هنا ولا `no_driver`. */
export type BookingStatus = "pending" | "dispatched" | "missed" | "cancelled";

export interface Booking {
  id: string;
  status: BookingStatus;
  scheduled_at: string;
  vehicle_category: VehicleCategory;
  gender_preference: GenderPreference;
  payment_method_hint: PaymentMethod | null;
  pickup_lat: number;
  pickup_lng: number;
  pickup_address: string | null;
  dropoff_lat: number;
  dropoff_lng: number;
  dropoff_address: string | null;
  /** **تقديرٌ لحظةَ الحجز لا أجرة**: تُحسب عند التنفيذ (القسم 5.11). */
  estimated_fare_at_booking: string | null;
  currency: Currency;
  ride_id: string | null;
  /** مقروءةٌ من الرحلة — لا عمودٌ على الحجز. */
  ride_status: RideStatus | null;
  cancelled_at: string | null;
  created_at: string;
}


/** صفٌّ في صندوق الوارد (9-ب).
 *
 * **و`kind` هو `data.type` نفسه**، فالنقرُ على الصف والنقرُ على إشعار نظام
 * التشغيل يفتحان الشاشةَ ذاتها — لا خريطتان تفترقان. و`title`/`body` لدرج
 * النظام حين يكون التطبيق مغلقاً؛ وما تعرف الشاشةُ صياغتَه تصوغه من `data`.
 */
export interface UserNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  data: Record<string, string> | null;
  read_at: string | null;
  created_at: string;
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

// ------------------------------------------------- حوافزُ الإحالة (تعميمُ 12-ح)

/** أين وصلت إحالةٌ واحدة — **حقائقُ لا جملةُ حالة**: النصَّ تبنيه الشاشة. */
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
  /** **أيقونةُ lucide** — زخرفيّةٌ بجانب النصّ، وهي غيرُ صورة اللافتة:
   *  الصورةُ بايتاتٌ تُجلب من `/storefront/banners/{id}/image` (منذ 08-31)،
   *  **ولا حقلَ يقول «لها صورة»** — الطلبُ نفسُه هو الجواب.
   *
   *  **وكان هنا `image_url: string | null`** ونُزع في 2026-09-07: **الخلفيةُ
   *  لا تنشره ولا قارئَ له في هذا التطبيق**، وأخوه في تطبيق الكبتن لا يحمله.
   *  **ومرآةٌ بلا مُرسِلٍ تُقرأ ميزةً قائمة** — من يفتح النوعَ يظنّ العنوانَ
   *  يصل فيبني عليه `<img src>`، **فيرسم صورةً مكسورة**. */
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
