/** أنواع ما تردّه الخلفية — مرآةٌ لـ`backend/app/schemas/`.
 *
 * ما يخصّ الكبتن وحده. وكلُّ نوعٍ هنا يقابل مخططاً في الخلفية بالاسم نفسه،
 * فمن غيّر هناك يجد مقابله هنا باسمه.
 */

export type CountryCode = "JO" | "LY";
export type Currency = "JOD" | "LYD";
export type UserRole = "rider" | "driver" | "admin" | "support";
export type VehicleCategory = "economy" | "comfort";

export type DriverStatus = "pending" | "approved" | "rejected" | "suspended";

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
  | "vehicle_plate";

export type DocumentReviewStatus = "pending" | "approved" | "rejected";

/** أيُّ مُحقِّقٍ فعّالٌ الآن — تقرؤه الواجهة ولا تختاره (SPEC القسم 15/أ). */
export type VerificationMethod =
  | "firebase"
  | "sms_otp"
  | "whatsapp_otp"
  | "none";

/** القنواتُ التي نرسل فيها رمزاً نحن — وما بينها مخرجُ ارتدادٍ (12-هـ). */
export type OtpChannel = "whatsapp_otp" | "sms_otp";

export interface User {
  id: string;
  phone: string;
  name: string;
  role: UserRole;
  country_code: CountryCode;
  is_blocked: boolean;
  phone_verified: boolean;
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
}

export interface AppConfig {
  app: string;
  auth: AuthMethod;
  countries: CountryConfig[];
  providers: Record<string, Record<string, string | undefined>>;
  /** الدولة التي تفترضها شاشاتُ ما قبل الدخول (لا منتقيَ دولٍ فيها). */
  default_country_code: CountryCode;
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
  current_leg: number;
  waiting_charge: string;
  stop_free_minutes: number;
  stop_price_per_min: string;
  stop_max_wait_minutes: number;

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
  min_withdrawal_amount: string;
  /** يبقى في المحفظة ولا يُسحب — يخرج عند إلغاء التفعيل (البند ١٣). */
  withdrawal_reserve_amount: string;
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
  | "tip_payment";

export interface WalletTransaction {
  id: string;
  type: WalletTransactionType;
  amount: string;
  balance_after: string;
  ride_id: string | null;
  reference: string | null;
  created_at: string;
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
  currency: Currency;
  payment_method: PaymentMethod;
  status: "active" | "expired" | "cancelled";
}


/** إحالةٌ واحدةٌ كما تصل — **حقائقُ لا جملةُ حالة** (المرحلة 12-ح). */
export interface ReferralStage {
  id: string;
  created_at: string;
  driver_approved: boolean;
  gender_ready: boolean;
  rides_done: number;
  rides_required: number;
  qualifies: boolean;
  rewarded: boolean;
  reward_amount: string | null;
  reward_currency: string | null;
  rewarded_at: string | null;
}

/** قسمُ الإحالة في الحساب. **و`reward_amount === "0"` تعني «لم يُحدَّد»**
 *  فلا تعرض الشاشةُ مبلغاً ولا تَعِد به — وعدٌ بمالٍ لم يقرّره أحدٌ أسوأ من صمت. */
export interface MyReferrals {
  code: string;
  enabled: boolean;
  reward_amount: string;
  required_rides: number;
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
