/** أنواعُ ما تردّه الخلفية — مرآةٌ حرفية لـ`backend/app/models/enums.py`
 * و`backend/app/schemas/`.
 *
 * **تُنسخ ولا تُكتب**: اتحادٌ يُخترع في الواجهة يبني عليه المنطق حالاً لا
 * وجود لها — وهو ما وقع مرتين في تطبيق الكبتن قبل أن يُكتب `check:enums`،
 * الذي يعمل هنا كذلك.
 */

export type CountryCode = "JO" | "LY";
export type Currency = "JOD" | "LYD";
export type UserRole = "rider" | "driver" | "admin" | "support";

export interface User {
  id: string;
  /** `null` للمشرف — يدخل باسمِ مستخدمٍ لا برقم (SPEC §25.9). */
  phone: string | null;
  name: string;
  role: UserRole;
  /** **كلُّ ما يملكه من أدوار** — تنشرها الخلفيةُ منذ نموذج الأدوار (§21).
   *  وبها تعرف اللوحةُ أن الحسابَ **بمحفظتين** فتسأل عن أيِّهما، بدل أن
   *  تُخمِّن أو تسأل عن كلِّ حساب. */
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
  /** **السببُ والطريقُ لمن أوقفته حملةُ تأكيد الأرقام** — أو `null`.
   *
   *  **وحالٌ مستقلّةٌ عن `is_blocked` لا تُخلط به** (§32٫٤): ذاك قرارُ مشرفٍ
   *  بسببٍ مكتوب، **وهذه آليّةٌ تشفي نفسَها بتأكيد الرقم**. ومن يقرأ «نشط»
   *  عن حسابٍ أوقفته الحملةُ يقرأ غيرَ الواقع.
   *
   *  **والنصُّ يأتي مبنيّاً من الخلفية** — «التطبيقُ لا يكتب عربيّةً لخطأٍ
   *  سمّاه الخادم». */
  suspension: { title?: string; body?: string; [key: string]: string | undefined } | null;
  /** بريدُه إن أثبته — و`null` تعني لا بريدَ مُثبَت. */
  email: string | null;
  marketing_push_enabled: boolean;
  created_at: string;
}

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

/** جوابُ الدخول — إمّا جلسةٌ كاملة، وإمّا تحدٍّ ثانٍ **بلا توكن** (12-د).
 *
 * شكلٌ واحدٌ لا اتحادٌ بين شكلين، كما تردّه الخلفية: `totp_required` يُفحص
 * أولاً، وحين يكون `true` فـ`user` و`tokens` غائبان — ولا توكنَ قبل العاملين.
 */
export interface LoginResponse {
  totp_required: boolean;
  user: User | null;
  tokens: TokenPair | null;
  challenge_token: string | null;
  expires_in: number | null;
}

export interface TotpStatus {
  enrolled: boolean;
  confirmed: boolean;
  confirmed_at: string | null;
  recovery_verified_at: string | null;
  recovery_codes_remaining: number;
  required: boolean;
  session_idle_timeout_minutes: number;
}

export interface TotpEnrollment {
  secret: string;
  uri: string;
  digits: number;
  period_seconds: number;
}

export interface TotpConfirmation {
  confirmed_at: string;
  /** تُعرض **مرةً واحدة** ولا يعيدها أي مسار — فالشاشةُ التي تعرضها هي الوحيدة. */
  recovery_codes: string[];
}

export interface SecurityPolicy {
  admin_totp_required: boolean;
  admin_idle_timeout_minutes: number;
  min_idle_timeout_minutes: number;
  max_idle_timeout_minutes: number;
  my_factor: TotpStatus;
}

export interface CountryConfig {
  country_code: CountryCode;
  currency: Currency;
  features: Record<string, boolean>;
  vehicle_categories: string[];
  dial_code: string;
  national_number_length: number;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  quiet_hours_timezone: string | null;
  /** **حسابُ كليك المستقبِل لهذا السوق** — يُضبط من اللوحة، ويُقرأ هنا فلا
   *  يكتب التطبيقُ رقماً من عنده. **و`null` تعني «لم يُضبط»**: تُخفى القناةُ
   *  كلُّها حينها — شاشةٌ تطلب تحويلاً بلا رقمٍ تُنتج حوالةً ضائعة. */
  cliq_alias: string | null;
  verification: string;
  verification_channels: string[];
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
  messages: Record<string, string>;
}

export interface AppConfig {
  app: string;
  auth: { verification: string; otp_length: number | null };
  countries: CountryConfig[];
  providers: Record<string, Record<string, string | undefined>>;
  default_country_code: CountryCode;
  /** قواعدُ التحقق مُشتقّةً من مخططات الخلفية (SPEC ١٧.٣) — لا نسخةَ منها هنا. */
  validation: Record<string, Record<string, FieldRule>>;
}

// ------------------------------------------------------------ الحملات

/** `segment` محجوزةٌ للمرحلة 12 وترفضها الخلفية اليوم برسالة صريحة. */
export type CampaignAudience =
  "all_riders" | "all_drivers" | "by_country" | "segment";

export type CampaignStatus = "draft" | "scheduled" | "sent" | "cancelled";

/** `skipped` ليست فشلاً: الفرق بين «لم نرسل عمداً» و«أرسلنا فلم يصل». */
export type DeliveryStatus = "sent" | "failed" | "skipped";

export interface Campaign {
  id: string;
  title: string;
  body: string;
  audience: CampaignAudience;
  country_code: CountryCode | null;
  status: CampaignStatus;
  scheduled_at: string | null;
  sent_at: string | null;
  sent_count: number;
  created_at: string;
}

export interface Delivery {
  id: string;
  user_id: string;
  status: DeliveryStatus;
  sent_at: string | null;
}

export interface NotificationSetting {
  country_code: CountryCode;
  quiet_hours_start: string;
  quiet_hours_end: string;
  timezone: string;
}

// ------------------------------------------------------------ الكباتن

// **و`deactivated` أُضيفت 2026-09-07**: كانت في الخلفية ولا يعرفها هذا
// الاتحاد، **فكبتنٌ أُلغي تفعيلُه يُرسم `deactivated` على شاشة المشرف**.
export type DriverStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "suspended"
  | "deactivated";

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

/** قيمتان لا ثلاث، و**الغيابُ `null` لا عضوٌ ثالث**: «غير معروف» ليس جنساً. */
export type Gender = "male" | "female";

export type GenderPreference = "male" | "female" | "any";

export interface AdminDriverRow {
  driver_id: string;
  user_id: string;
  name: string;
  phone: string;
  country_code: CountryCode;
  status: DriverStatus;
  phone_verified: boolean;
  rating_avg: string;
  is_online: boolean;
  /** ما قرأه المشرف من الهوية — و`gender_verified` هو ما تقرؤه المطابقة. */
  gender: Gender | null;
  gender_verified: boolean;
  gender_preference: GenderPreference;
  documents_pending: number;
  documents_rejected: number;
  missing_required: DocumentType[];
  /** سقفُ السلفة الخاصُّ به — `null` لا تخصيص، و`"0.000"` منعٌ من السلف. */
  advance_cap_override: string | null;
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

export interface DriverDocuments {
  documents: DriverDocument[];
  missing_required: DocumentType[];
}

// ------------------------------------------------------------ المالية

// **و`card` ثالثتُها في الخلفية** (أُضيفت هنا 2026-09-07).
export type TopupMethod = "cliq" | "cash" | "card";
export type TopupStatus = "pending" | "confirmed" | "rejected";

export interface TopupRequest {
  id: string;
  owner_id: string;
  method: TopupMethod;
  amount: string;
  status: TopupStatus;
  reference: string | null;
  note: string | null;
  transaction_id: string | null;
  processed_at: string | null;
  created_at: string;
}

export type WithdrawalMethod = "cliq" | "bank";
export type WithdrawalStatus = "pending" | "approved" | "paid" | "rejected";

export interface Withdrawal {
  id: string;
  driver_id: string;
  /** **صاحبُ الطلب** — مرآةُ `AdminWithdrawalRow.driver` (§٤٧٫١٩).
   *
   * **وكان الجدولُ لا يعرض إنساناً البتّة**: المبلغُ والقناةُ والحالُ
   * والتاريخ. **فالمشرفُ يوافق على صرفِ مالٍ ولا يرى لمن.**
   *
   * **و`driver_id` وحدَه لا يفتح ملفّاً**: لا بابَ يقرأ صفَّ كبتنٍ واحد،
   * فالدرجُ يُفتح بمطابقةٍ **داخل القائمة المرشَّحة** — والاسمُ هو ما
   * يُضيَّق به.
   */
  driver: DriverParty;
  amount: string;
  method: WithdrawalMethod;
  status: WithdrawalStatus;
  reference: string | null;
  note: string | null;
  transaction_id: string | null;
  processed_at: string | null;
  created_at: string;
}

// ------------------------------------------------------------ النزاعات

export type PaymentMethod =
  "cash" | "cliq" | "card" | "wallet" | "promo" | "share";
export type PaymentStatus =
  "pending" | "confirmed" | "failed" | "disputed" | "refunded";
export type DisputeResolution = "paid" | "unpaid";

export interface Payment {
  id: string;
  ride_id: string;
  /** **راكبُ الرحلة، لا الدافعُ بالضرورة** (§٤٧٫١٩): الدفعُ المختلط صفّان،
   *  والبطاقةُ قد تكون بطاقةَ غيره. **فالحقلُ يُسمّى بما هو.** */
  rider: Party | null;
  /** **كبتنُ الرحلة** — و`null` واقعةٌ حقيقية: رحلةٌ أُلغيت قبل القبول لا
   *  كبتنَ لها، **ورسمُ إلغائها دفعةٌ بلا كبتن**. */
  driver: DriverParty | null;
  method: PaymentMethod;
  amount: string;
  currency: Currency;
  status: PaymentStatus;
  cliq_alias: string | null;
  cliq_reference: string | null;
  cliq_transfer_reference: string | null;
  cliq_confirmation_expires_at: string | null;
  dispute_reason: string | null;
  disputed_at: string | null;
  resolution: DisputeResolution | null;
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

// ------------------------------------------------------------ الإعدادات

/** مرآةُ `FeatureKey` — والعمود نصٌّ في القاعدة، فالنوع حارسُ كتابةٍ لا أكثر. */
export type FeatureKey =
  | "cliq_enabled"
  | "card_enabled"
  | "wallet_enabled"
  | "wallet_transfer_enabled"
  | "otp_verification_enabled"
  | "women_service_enabled"
  | "multi_stop_enabled"
  | "whatsapp_otp_enabled"
  | "email_otp_enabled"
  | "tips_enabled"
  | "promo_codes_enabled"
  | "driver_referrals_enabled"
  | "rider_referrals_enabled"
  | "referred_reward_enabled"
  | "driver_levels_enabled"
  | "scheduled_rides_enabled"
  | "ride_sharing_enabled"
  | "subscription_offers_enabled"
  | "vehicle_skins_enabled"
  | "driver_advances_enabled"
  | "next_instruction_enabled"
  | "driver_map_nearby_enabled"
  | "country_visible"
  // **حارسا المال** (2026-08-23): تجميدُ التسعير وإيقافُ الصرف. غيابُ صفِّهما
  // **يعمل**، وإطفاؤهما يحتاج سبباً مكتوباً — `design/KILL-SWITCHES.md`
  | "pricing_writes_enabled"
  | "withdrawal_payout_enabled";

/** دولةٌ كما تراها اللوحةُ وحدَها — **بحالها لا مصفاةً** (SPEC §24).
 *
 * `GET /config` يحذف منه ما أُطفئ ظهورُه، فاللوحةُ تقرأ من `GET /admin/countries`
 * وترى الأسواقَ كلَّها: من يُجهّز سوقاً قبل فتحه يحتاج أن يراه مطفأً.
 */
export interface CountryRow {
  country_code: CountryCode;
  name: string;
  visible: boolean;
  config: CountryConfig;
}

export interface CountryFeatureFlags {
  country_code: CountryCode;
  flags: Record<string, boolean>;
}

/** `cashless_rides` = ما تمر أمواله عبر المنصة (بطاقة ومحفظة)؛ والكاش وكليك
 * يقبضهما الكبتن مباشرةً (القسم 9). */
export type CommissionAppliesTo = "all_rides" | "cashless_rides";

export interface CommissionSetting {
  id: string;
  country_code: CountryCode;
  commission_enabled: boolean;
  commission_percent: string;
  applies_to: CommissionAppliesTo;
  updated_at: string;
}

export interface WalletSetting {
  id: string;
  country_code: CountryCode;
  transfer_daily_limit: string;
  transfer_monthly_limit: string;
  min_withdrawal_amount: string;
  /** يبقى في محفظة الكبتن ولا يُسحب — يخرج عند إلغاء التفعيل (البند ١٣). */
  withdrawal_reserve_amount: string;
  updated_at: string;
}

/** حافزُ الإحالة per-country (12-ح) — **صفرُ المبلغ «لم يُحدَّد»** فلا يُدفع. */
export interface ReferralSetting {
  country_code: CountryCode;
  /** برنامجٌ واحد: `rider` أو `driver` — والصفُّ **هو** البرنامج. */
  referral_type: string;
  reward_amount: string;
  required_rides: number;
  /** **تُضاف إلى الأساس لا تحلّ محلَّه** — والشاشةُ تقول ذلك بجملةٍ صريحة. */
  female_bonus_amount: string;
  /** `null` = بلا سقف. والصفرُ في هذا المشروع «لم يُحدَّد»، فلا يُستعمل هنا. */
  monthly_cap: number | null;
}

/** إعداداتُ مشاركة الرحلة (12-ي) — النسبةُ مالٌ والثلاثةُ الباقيةُ معايرةٌ.
 *
 * **والأرقامُ نصوصٌ كما تصل**: `NUMERIC` يُسلسَل نصّاً، وتحويلُه إلى `number`
 * هنا تمريرٌ لمالٍ عبر عائم — وهي القاعدةُ التي يقوم عليها `formatMoney` كلُّه.
 */
export interface RideSharingSetting {
  country_code: CountryCode;
  discount_percent: string;
  corridor_km: string;
  max_detour_minutes: number;
  partner_wait_seconds: number;
}

/** مجاميعُ سوقٍ واحد — **من الخلفية**: جمعُ صفحةٍ مقصوصةٍ هنا يكذب بعنوانه. */
export interface ReferralSummary {
  country_code: CountryCode;
  total_rewarded: string;
  rewarded_count: number;
  pending_count: number;
}

/** صفٌّ في جدول الإحالات — **حقائقُ لا جملةُ حالة**: النصَّ تبنيه الشاشة. */
export interface AdminReferralRow {
  id: string;
  created_at: string;
  referrer_name: string;
  referrer_phone: string;
  referred_name: string;
  referred_phone: string;
  code_used: string;
  referral_type: string;
  driver_approved: boolean;
  has_subscription: boolean;
  female_verified: boolean;
  rides_done: number;
  rides_required: number;
  qualifies: boolean;
  rewarded: boolean;
  reward_amount: string | null;
  reward_currency: string | null;
  rewarded_at: string | null;
}

export interface PaymentSetting {
  id: string;
  country_code: CountryCode;
  cliq_confirmation_hours: number;
  /** **حسابُ كليك المستقبِل** — و`null` تُخفي القناةَ كلَّها. */
  cliq_alias: string | null;
  /** **صورةُ الباركود** — `null` تعني «لم تُرفع»، والشاشةُ تعمل بدونها. */
  cliq_qr_path: string | null;
  cliq_review_min_minutes: number;
  cliq_review_max_minutes: number;
  /** **سقفُ دَينِ الكبتن** — و`null` تعني «لا سقفَ» لا «صفراً»: صفرٌ يحجب
   *  كلَّ كبتنٍ عليه فلسٌ واحد. */
  driver_debt_ceiling: string | null;
  /** مبالغُ البقشيش (12-و) — **صفرٌ يعني «لم يُضبط»** فتُخفى الميزةُ في التطبيق. */
  tip_preset_small: string;
  tip_preset_medium: string;
  tip_max: string;
  updated_at: string;
}

/** رمزُ خصمٍ كما تراه اللوحة (12-ز) — وثلاثةُ أرقامٍ **محسوبة** لا مراكمة. */
/** عرضُ اشتراكٍ — البند ٥٤. **والنوعُ نصٌّ لا اتحادٌ مغلق**: إضافةُ نوعٍ زمنيٍّ
 *  لاحقاً كودٌ بلا ترحيلة، فاتحادٌ هنا يجعل الواجهةَ ترفض ما تقبله الخلفية. */
export interface SubscriptionOffer {
  id: string;
  country_code: CountryCode;
  name: string;
  discount_type: string;
  discount_value: string;
  max_discount: string | null;
  plan_id: string | null;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
  audience: "all" | "new_driver" | "lapsed" | "manual";
  lapsed_days: number | null;
  max_uses_per_driver: number;
  /** نسبةُ العمولة التي يمنحها العرض — **`null` لا يمسّها، وصفرٌ يمنح صفراً**. */
  commission_percent: string | null;
  total_budget: string | null;
  created_at: string;
  /** جدولُ التنازل — محسوبٌ في الخلفية (§14) لا مجموعاً في المتصفح. */
  subscriptions_sold: number;
  total_list_price: string;
  total_given_up: string;
  /** كم مرةً خالف المشرفُ المبلغَ المعبَّأ — مقارنةٌ حيّة لا عمودٌ مخزَّن. */
  manual_adjustments: number;
}

export interface OfferGrant {
  id: string;
  offer_id: string;
  driver_id: string;
  driver_name: string | null;
  note: string | null;
  created_at: string;
}

export interface PromoCode {
  id: string;
  code: string;
  country_code: CountryCode;
  discount_type: "percent" | "fixed";
  discount_value: string;
  max_discount: string | null;
  budget_total: string;
  per_user_limit: number;
  total_usage_limit: number | null;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  /** ما دُفع فعلاً (دفعات `promo` المؤكَّدة). */
  spent: string;
  /** ما دُفع **ومعه ما وُعد به في رحلاتٍ جارية** — وهو ما يُقاس به السقف،
   *  و**قد يتجاوزه**: السقفُ يمنع تطبيقاً جديداً لا رحلةً تحمل الرمز. */
  committed: string;
  used_count: number;
}

// ------------------------------------------------------------ العقود

export type ProviderKey =
  | "mapbox"
  | "telr"
  | "sms"
  | "whatsapp"
  | "fcm"
  | "firebase_auth"
  | "cliq_acquirer"
  | "payout"
  // **و`email` في الخلفية ولا يعرفها هذا الاتحاد** (أُضيفت 2026-09-07):
  // صفحةُ العقود تعرض المزوّدين، **ومزوّدٌ لا يعرفه الاتحادُ لا يُرسم**.
  | "email";

export interface ProviderField {
  key: string;
  label: string;
  /** `text` · `secret` · `toggle` — والأخيرُ يُرسم مفتاحاً لا صندوقَ نصّ. */
  kind: "text" | "secret" | "toggle";
  secret: boolean;
  required: boolean;
}

export interface ProviderSpec {
  provider_key: ProviderKey;
  label: string;
  per_country: boolean;
  feature_key: FeatureKey | null;
  fields: ProviderField[];
}

export interface ProviderCredential {
  id: string;
  provider_key: ProviderKey;
  country_code: CountryCode | null;
  is_active: boolean;
  values: Record<string, string | boolean | null>;
  last_tested_at: string | null;
  updated_at: string;
}

export interface ProviderCatalog {
  providers: ProviderSpec[];
  credentials: ProviderCredential[];
}

export interface ProviderTestResult {
  ok: boolean;
  detail: string;
  credential: ProviderCredential;
}

// ------------------------------------------------------------ الإحصاءات

export type StatsPeriod = "today" | "week" | "month";

/** أرقامٌ جاهزة — التجميعُ في الخلفية حصراً (القسم 13/1). */
export interface Overview {
  period: StatsPeriod;
  from_at: string;
  to_at: string;
  completed_rides: number;
  cancelled_rides: number;
  revenue: string;
  online_drivers: number;
  active_rides: number;
  active_subscriptions: number;
  open_disputes: number;
  pending_documents: number;
  pending_withdrawals: number;
  rides_by_hour: number[];
  payment_mix: Record<string, number>;
}

// ------------------------------------------------------------ الخريطة الحيّة

/** منسوختان حرفياً من `app/models/enums.py` — و`check:enums` يحرسهما. */
export type VehicleCategory = "economy" | "comfort";

/** مركبةُ كبتن — يقرؤها **قسمُ المركبة في الملفِّ الشخصيّ** (§37).
 *
 * **ولا تُكتب من اللوحة**: هوّيةُ المركبة يكتبها صاحبُها من تطبيقه، وتحريرُها
 * يُسقط اعتمادَه إلى `pending` بقفلٍ مكتوب — **وبابُ لوحةٍ يكتبها طريقٌ ثانٍ
 * إلى ذلك السقوط لا يمرّ بالقفل**.
 */
export interface Vehicle {
  id: string;
  driver_id: string;
  make: string;
  model: string;
  year: number;
  color: string;
  /** **لا تُحوَّل خاناتُه** (§20): يُقارَن حرفاً بحرفٍ بلوحةٍ معدنيةٍ في يد. */
  plate_number: string;
  category: VehicleCategory;
  created_at: string;
}

export type RideStatus =
  | "requested"
  | "searching"
  | "accepted"
  | "arrived"
  | "in_progress"
  /** وقوفٌ عند محطةٍ وسيطة (المرحلة 12-ب) — رحلةٌ **جارية** لا حالٌ ثالثة. */
  | "at_stop"
  | "completed"
  | "cancelled_by_rider"
  | "cancelled_by_driver"
  | "no_driver_found";

/** كبتنٌ **بهويته** — الشكلُ الوحيد في المنصة الذي يقرن اسماً بموقع.
 *
 * ولا يُعاد استعماله لأي خريطةٍ أخرى: خريطة الراكب مجهَّلةٌ بحكم القسم 10،
 * ومصدرُها `NearbyDriver` في تطبيقه بحقولٍ مختلفةٍ عمداً.
 */
export interface LiveDriver {
  driver_id: string;
  name: string;
  phone: string;
  lat: number;
  lng: number;
  heading: number | null;
  vehicle_category: VehicleCategory;
  plate_number: string | null;
  on_ride: boolean;
  ride_id: string | null;
  /** **ثلاثُ حالاتٍ لا اثنتان** — و«شاحبٌ» يعني بثّاً توقّف ولمّا ينقضِ
   * مفتاحُ حضوره. تُحسب في الخلفية لا هنا: لوحةٌ تحسبها بنفسها تفترق عن
   * الخلفية أولَ ما يتغيّر عمرُ الحضور، ولا شيءَ يفشل. */
  state: "available" | "on_ride" | "stale";
  /** ثوانٍ منذ آخر بثّ — و`null` تعني أن الختمَ غيرُ موجود (بثٌّ قديمٌ قبل
   * إضافة الختم)، فتُقرأ «غيرُ معلوم» لا «الآن». */
  seconds_since_update: number | null;
}

export interface LivePendingRide {
  ride_id: string;
  lat: number;
  lng: number;
  status: RideStatus;
  created_at: string;
}

export interface LiveMap {
  drivers: LiveDriver[];
  pending_rides: LivePendingRide[];
}

/** موضعُ كبتنٍ بعينه الآن — و**غيابُ الكائن صمتٌ لا موضعٌ عند الصفر**. */
export interface DriverLivePosition {
  lat: number;
  lng: number;
  /** ثوانٍ منذ آخر بثّ — و`null` ختمٌ غيرُ موجود، **لا «الآن»**. */
  seconds_since_update: number | null;
  /** **تُحسب في الخلفية** من عمر مفتاح الحضور — لا تُقارن هنا بعتبةٍ محلية. */
  stale: boolean;
}

/** الرحلةُ الجارية للكبتن ومسارُها وموضعُه — البند ٦ (§39٫٦).
 *
 * **وأضيقُ من `AdminRideDetail` بقصد**: بابُها يقرن هويةً بموقع، فلا يحمل
 * اسمَ راكبٍ ولا رقمَه ولا مالاً. **و`null` من الباب تعني لا رحلةَ جارية**،
 * فيصمت القسم.
 */
export interface DriverLiveRide {
  ride_id: string;
  status: RideStatus;
  pickup_lat: number;
  pickup_lng: number;
  pickup_address: string | null;
  dropoff_lat: number;
  dropoff_lng: number;
  dropoff_address: string | null;
  accepted_at: string | null;
  started_at: string | null;
  route: RidePoint[];
  /** المسارُ الطويل يُقصّ — والقصُّ يُقال. */
  route_truncated: boolean;
  position: DriverLivePosition | null;
}

// ------------------------------------------------------------ طرفٌ إنسانٌ في صفّ

/** مرآةُ `schemas/party.py::PartyOut` — **وليست خاصّةً بالرحلات**.
 *
 * **كان اسمُها `RideParty`** حتى ٢٠٢٦-٠٩-٠٤: صار يستعملها صفُّ الدفعة وصفُّ
 * طلب الصرف، **واسمٌ يبدأ بـ`Ride` على صفِّ طلبِ صرفٍ يُقرأ خطأً**. وهي
 * تسميةٌ واحدةٌ في الطرفين، لا اسمٌ هنا وآخرُ هناك.
 */
export interface Party {
  user_id: string;
  name: string;
  phone: string;
}

/** كبتنٌ — **ومعه `drivers.id`**، وهو ما يفتح به الدرجُ ملفَّه.
 *
 * **و`plate_number` اختياريٌّ بقصد**: صفُّ الرحلة يحمل اللوحةَ، وصفُّ الصرف
 * وصفُّ الدفعة لا يعرضانها — **ولا تُحسب قيمةٌ لا يقرؤها أحد**.
 */
export interface DriverParty extends Party {
  driver_id: string;
  plate_number: string | null;
}

/** صفٌّ في سجل الرحلات — وحالُ الدفع **مجموعٌ في الخلفية**.
 *
 * `payment_methods` قائمةٌ لا قيمة: الدفعُ المختلط صفّان على رحلةٍ واحدة
 * (محفظة + كاش)، فقناةٌ واحدة تخفي نصف الواقعة.
 */
export interface AdminRideRow {
  id: string;
  status: RideStatus;
  country_code: CountryCode;
  vehicle_category: VehicleCategory;
  currency: Currency;
  rider: Party;
  driver: DriverParty | null;
  pickup_address: string | null;
  dropoff_address: string | null;
  distance_km: string;
  actual_distance_km: string | null;
  estimated_fare: string;
  final_fare: string | null;
  cancellation_fee: string | null;
  payment_methods: PaymentMethod[];
  paid_amount: string;
  settlement: SettlementState;
  has_open_dispute: boolean;
  created_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
}

export interface RidePayment {
  id: string;
  method: PaymentMethod;
  status: PaymentStatus;
  amount: string;
  dispute_reason: string | null;
  resolution: DisputeResolution | null;
  created_at: string;
}

export type RatingRaterType = "rider" | "driver";

export interface RideRating {
  rater_type: RatingRaterType;
  stars: number;
  comment: string | null;
  created_at: string;
}

/** نقطةٌ من المسار الفعلي — و`created_at` هو زمنُها (لا عمود `recorded_at`). */
export interface RidePoint {
  lat: number;
  lng: number;
  created_at: string;
}

export type CancelReasonCode = "gender_mismatch" | "other";

/** محطةٌ وسيطة كما ينشرها بابُ اللوحة — **مرآةُ `RideStopOut` بحرفها**،
 *  ومصدرُها البانِي نفسُه الذي يقرؤه التطبيقان (`schemas/ride.stops_of`). */
export interface AdminRideStop {
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

export interface AdminRideDetail extends AdminRideRow {
  pickup_lat: number;
  pickup_lng: number;
  dropoff_lat: number;
  dropoff_lng: number;
  duration_min: string;
  commission_percent_at_ride: string;
  /** ما وقف الكبتنُ لأجله — ثالثُ ما يفسّر الفرقَ بين المقدَّر والنهائيّ. */
  stops_count: number;
  stop_fee: string;
  stops_charge: string;
  waiting_charge: string;
  pause_charge: string;
  /** صفوفُ المحطات — **لا عددُها وحدَه**. بغيرها يفصل المشرفُ في نزاع
   *  انتظارٍ وهو يرى المجموع ولا يرى عند أيِّ محطةٍ وقف ولا كم. */
  stops: AdminRideStop[];
  gender_preference: GenderPreference;
  cancelled_reason: string | null;
  cancel_reason_code: CancelReasonCode | null;
  accepted_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  payments: RidePayment[];
  ratings: RideRating[];
  route: RidePoint[];
  /** المسارُ الطويل يُقصّ — والقصُّ يُقال، فدليلٌ ناقصٌ يُقرأ كاملاً يكذب. */
  route_truncated: boolean;
}

// ------------------------------------------------------------ المحافظ

export type WalletOwnerType = "rider" | "driver";

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
  // **الثمانيةُ أُضيفت 2026-09-07** بعد أن قِيس أن **٢٣ صفّاً من ١١٥ (٢٠٪)
  // في دفتر التطوير تُرسم بمفتاحها الإنجليزيّ** على شاشة المشرف.
  //
  // **ولم يمسكها `check:enums`**: كان يسأل «أثمّة قيمةٌ مخترعة؟» — والعشرةُ
  // كلُّها في تعداد الخلفية — **ولا يسأل «أينقص عضو؟»**. وهو حدٌّ مكتوبٌ في
  // `GUARDS.md`، **وثمنُه ظهر على شاشةٍ يقرؤها إنسان**.
  | "tip"
  | "tip_payment"
  | "skin_purchase"
  | "referral_bonus"
  | "advance"
  | "advance_repayment"
  | "cancellation_fee"
  | "cancellation_compensation";

/** الرصيد **مجموعُ الدفتر** لا عمودٌ — لا كاش له في الواجهة كذلك. */
export interface Wallet {
  owner_id: string;
  owner_type: WalletOwnerType;
  balance: string;
  currency: Currency;
  frozen: boolean;
}

export interface WalletTransaction {
  id: string;
  type: WalletTransactionType;
  amount: string;
  balance_after: string;
  ride_id: string | null;
  reference: string | null;
  created_at: string;
}

// ------------------------------------------------------ الاشتراكات والباقات

export type SubscriptionDurationType = "daily" | "weekly" | "monthly";

/** حالتان لا ثالثة: لا `pending` — الصفُّ لا يُنشأ قبل وصول ماله. */
/** **و`cancelled` أُضيفت 2026-09-02** (البند ٢، §38) — ولا تُدمج في `expired`:
 *  تلك «انقضى وقتُه»، وهذه «أوقفناه ورددنا مالَه». */
export type SubscriptionStatus = "active" | "expired" | "cancelled";

/** صفٌّ سيُلغى، وما يُردّ عنه — **يُقرأ قبل الضغط** (§38). */
export interface CancellationLine {
  subscription_id: string;
  plan_name: string;
  starts_at: string;
  expires_at: string;
  amount_paid: string;
  refund: string;
  /** **أبدأ بعد؟** — الجاري يُردّ بالتناسب، والقادمُ كاملاً بلا تناسب. */
  started: boolean;
}

/** ما سيقع لو ضُغط زرُّ الإلغاء — **وبيتُ حسبته واحدٌ مع الفعل**، فلا رقمَ
 *  في ورقة التأكيد يخالف ما يقع. */
export interface CancellationPlan {
  cancelled_count: number;
  total_refund: string;
  currency: string;
  lines: CancellationLine[];
}

export interface SubscriptionPlan {
  id: string;
  country_code: CountryCode;
  name: string;
  duration_type: SubscriptionDurationType;
  price: string;
  currency: Currency;
  is_active: boolean;
  updated_at: string;
}

export interface Subscription {
  id: string;
  driver_id: string;
  plan_id: string;
  plan_name: string;
  duration_type: SubscriptionDurationType;
  country_code: CountryCode;
  currency: Currency;
  starts_at: string;
  expires_at: string;
  amount_paid: string;
  payment_method: PaymentMethod;
  status: SubscriptionStatus;
  transaction_id: string | null;
  reference: string | null;
  created_at: string;
}

// ------------------------------------------------------------ التسعيرة

export interface PricingRule {
  id: string;
  country_code: CountryCode;
  vehicle_category: VehicleCategory;
  base_fare: string;
  price_per_km: string;
  price_per_min: string;
  minimum_fare: string;
  cancellation_fee: string;
  /** حقولُ المحطات الوسيطة (المرحلة 12-ب) — صفرٌ يعني «بلا رسم»، وصفرُ
   * السقف يعني **لا سقف** لا «سقفٌ مقداره صفر». */
  stop_fee: string;
  stop_free_minutes: number;
  stop_price_per_min: string;
  stop_max_wait_minutes: number;
  /** الوقفةُ غير المخطَّطة وانتظارُ الوصول (§5.10-ب) — **قيمةُ الدقيقة واحدةٌ
   *  للحالتين**: دقيقةُ الكبتن الواقف تساوي دقيقتَه الواقفة. */
  pause_price_per_min: string;
  arrival_free_minutes: number;
  pause_max_minutes: number;
  updated_at: string;
}

// ------------------------------------------------------------ التقارير

export interface DayRevenue {
  day: string;
  revenue: string;
  rides: number;
}

export interface TopDriver {
  driver_id: string;
  name: string;
  completed_rides: number;
  revenue: string;
  rating_avg: string;
}

export interface PlanSales {
  plan_id: string;
  plan_name: string;
  sold: number;
  revenue: string;
}

/** النِسَبُ والمتوسطاتُ تصل **محسوبة** — قسمةُ رقمين مسقوفَين في الواجهة
 * تعطي متوسط الصفحة لا متوسط الفترة. */
export interface Reports {
  period: StatsPeriod;
  from_at: string;
  to_at: string;
  currency: Currency;
  revenue_by_day: DayRevenue[];
  avg_ride_fare: string;
  cancellation_rate: string;
  active_drivers: number;
  subscriptions_sold: number;
  subscription_revenue: string;
  sales_by_plan: PlanSales[];
  top_drivers: TopDriver[];
}

// ------------------------------------------------------------ سجل التدقيق

/** و`read` هي القراءةُ الوحيدة المسجَّلة في المشروع: فتحُ الخريطة الحيّة.
 *
 * والتعليقُ **فوق** الاتحاد لا بين أعضائه: `check:enums` يطابق اتحاداً من
 * سلاسلَ وأنابيبَ فقط، فتعليقٌ في وسطه يجعل النمط لا يطابق — فيمر الاتحادُ
 * بلا فحصٍ والبناءُ أخضر. حارسٌ يُتخطّى بصمتٍ أسوأ من حارسٍ يرفض.
 */
export type AuditAction =
  | "create"
  | "update"
  | "delete"
  | "activate"
  | "deactivate"
  | "read";

export interface AuditLog {
  id: string;
  actor_id: string | null;
  /** يذهب بحذف الحساب ويبقى `actor_id` — الأثرُ يبقى والاسمُ يضيع. */
  actor_name: string | null;
  action: AuditAction;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

/** طلبُ إلغاء تفعيل حساب كبتن (البند ١٣). */
export interface DeactivationRequestRow {
  id: string;
  /** **صاحبُ الحساب لا الكبتن** (الترحيلة `0075`): صار البابُ واحداً للدورين،
   *  **فالقائمةُ تشمل الركّابَ أيضاً** — ومسارٌ يقول «drivers» كان يُقرأ
   *  قائمةً لا تشملهم، فيُبتّ في نصفها ويُنسى نصفُها. */
  user_id: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reason: string | null;
  review_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

/** سلفةُ كبتنٍ كما تراها اللوحة (البند ١٥). */
export interface AdvanceRow {
  id: string;
  driver_id: string;
  /** **صاحبُها بالاسم والرقم لا بمعرِّفه** (أُضيفا 2026-09-02): كان العمودُ
   *  المعنونُ «الكبتن» يعرض ثماني خاناتٍ من UUID، **ومشرفٌ يقرأ `3f2a91b8`
   *  لا يعرف من هو** فيفتح قائمةً أخرى ليترجمه. وينشرهما `AdminDebtOut`
   *  أصلاً — وبابان ينشران الشيءَ نفسَه ويفترقان هو الشكلُ الثامن. */
  driver_name: string;
  driver_phone: string | null;
  amount: string;
  currency: string;
  status: "outstanding" | "repaid" | "written_off";
  due_at: string;
  settled_at: string | null;
  created_at: string;
  /** **مطروحٌ في الخلفية** لا في المتصفح: جمعُ صفحةٍ مسقوفةٍ رقمٌ يخالف القاعدة. */
  remaining: string;
  overdue: boolean;
}

/** سياسةُ السلف لدولة (البند ١٥) — **ولا حقلَ لقيمة السلفة**: أساسُ السقف
 *  سعرُ الخطة اليومية نفسُه، ورقمٌ ثانٍ له يتقادم يومَ تتغيّر الأسعار. */
export interface AdvanceSetting {
  country_code: CountryCode;
  deduction_percent: number;
  min_kept_amount: string;
  term_days: number;
  min_completed_rides: number;
  min_rating: string;
  growth_percent_per_repaid: number;
  max_multiplier_percent: number;
}

/** سياسةُ رسم الإلغاء لدولة (`design/CANCELLATION-FEE.md`) — **ولا حقلَ
 *  للمبلغ**: قيمةُ الرسم في `pricing_rules` لأنها **لكل فئةِ مركبة**، ونقلُها
 *  إلى هنا يجعلها رقماً واحداً لدولةٍ فيُفقد ما يميّزها. وما هنا سياسةٌ: متى
 *  يُستحقّ، ومتى يُعفى، وماذا يقع إن لم يُسدَّد. */
export interface CancellationSetting {
  country_code: CountryCode;
  exempt_within_meters: number;
  exempt_when_location_unknown: boolean;
  block_after_unpaid: number;
  carrier_grace_hours: number;
  unpaid_after_days: number;
  unpaid_outcome: UnpaidCancellationOutcome;
}

/** مآلُ دَينٍ لم يعد صاحبُه — **الإدارةُ تختار والكودُ لا يحسم** (قرارُ المالك).
 *  و`admin_decides` ليست فعلاً للدورة: تتركه معلّقاً ظاهراً ليشطبه إنسانٌ
 *  باسمه، وإلا صارت هي و`company_bears` خياراً واحداً. */
export type UnpaidCancellationOutcome =
  | "keep_pending"
  | "admin_decides"
  | "company_bears";

export type CancellationChargeStatus =
  | "pending"
  | "settled"
  | "waived"
  | "written_off";

/** رسمُ إلغاءٍ واحد بطرفَيه — **والاسمُ لا المُعرّف**: قرارُ الإعفاء قرارٌ في
 *  حقِّ إنسانَين، ومن يقرأ ثمانيةَ محارفَ من UUID لا يعرف عمّن يقرّر. */
export interface CancellationChargeRow {
  id: string;
  ride_id: string;
  country_code: CountryCode;
  amount: string;
  currency: string;
  status: CancellationChargeStatus;
  payer_name: string | null;
  payer_phone: string | null;
  beneficiary_driver_id: string;
  beneficiary_name: string | null;
  /** الحاملُ (§6-أ) — وحضورُه يعني أن الراكب سدَّد نقداً وأن المطلوبَ الآن
   *  تحويلٌ من يدِ كبتن، لا مطالبةُ راكب. */
  carrier_driver_id: string | null;
  carrier_name: string | null;
  carrier_due_at: string | null;
  collected_from_ride_id: string | null;
  settled_at: string | null;
  waive_reason: string | null;
  writeoff_reason: string | null;
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

/** حالُ جلسة بوابة واتساب الذاتية — **خمسٌ لا اثنتان**.
 *
 * `linked` مرتبطة · `awaiting_qr` تنتظر إنساناً يمسح رمزاً · `disconnected`
 * سقطت وتعود وحدها · `unreachable` البوابةُ نفسُها لا تُجيب · `off` العقدُ
 * ليس على القناة الذاتية.
 *
 * **ودمجُها في «متصل/غير متصل» هو ما يجعل جلسةً تسقط صامتة**: من يقرأ «غير
 * متصل» لا يعرف أينتظر فعلاً منه أم شبكةً تعود — وتسجيلُ المستخدمين واقفٌ
 * طوال ترددِه.
 */
export interface WhatsAppSession {
  state: "linked" | "awaiting_qr" | "disconnected" | "unreachable" | "off";
  phone: string | null;
  since: string | null;
  last_error: string | null;
  /** `true` يعني «لن تعود وحدها» — امسح رمزاً أو بدّل القناة. */
  needs_human: boolean;
  queue_depth: number;
  /** نصٌّ خامٌّ ترسمه اللوحةُ مربّعاً في المتصفح — لا صورةٌ من خدمةٍ خارجية. */
  qr: string | null;
  /** `false` يعني أن البوابة تعمل بشروطها المتشدّدة فترفض **كلَّ** قالبٍ محرَّر. */
  template_rules_loaded: boolean;
  template_rules_error: string | null;
  /** آخرُ رسالةٍ سقطت إلى النصِّ المدمج — **الأثرُ المرئيُّ للاحتياط**. */
  last_template_fallback: {
    purpose?: string;
    violations?: string[];
    at?: string;
  } | null;
}

/** سقوفُ طلب رمز التحقق لدولة (قرارُ المالك 2026-08-16).
 *
 * **ثلاثةُ سقوفٍ لا واحد**: نافذةٌ قصيرة (رشقٌ آليّ)، ويوميّ (من ينتظر الساعة
 * ثم يعود)، **وعمرُ التسجيل** — وهو الذي لا يُشترى بالصبر، لأن التسجيل حدثٌ
 * مرةً لا حدثٌ متكرر. **وصفرُ أيِّها يعني «لا سقف»** ويُكتب صراحةً: هذه حرّاسٌ
 * لا ميزات، فانفتاحُها قرارٌ مكتوبٌ لا سكوت.
 */
export interface OtpSetting {
  country_code: CountryCode;
  window_minutes: number;
  max_per_window: number;
  max_per_day: number;
  max_per_registration: number;
  lockout_minutes: number;
  resend_base_seconds: number;
  resend_max_seconds: number;
}

/** أرقامٌ بلغت سقفاً اليوم — **رؤيةٌ لا منع**: تكرارٌ مشبوهٌ يُرى قبل أن يحرق
 *  رقمَ الإرسال، لا بعده. */
export interface OtpExhausted {
  day: string;
  phones: string[];
}

// --------------------------------------------- المهامُّ والمستويات (البند ٥٣)

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

export interface LevelSetting {
  country_code: CountryCode;
  level: number;
  discount_meters: number;
}

/** **كم كبتناً في كل مستوى ومتى حُسب** — مجموعٌ في الخلفية (القسم 14). */
export interface LevelOverview {
  country_code: CountryCode;
  enabled: boolean;
  counts: Record<string, number>;
  settings: LevelSetting[];
  last_computed_at: string | null;
}

export interface Badge {
  id: string;
  key: string;
  label: string;
  description: string | null;
  icon: string | null;
  is_active: boolean;
}

// ------------------------------------------- النسخُ الاحتياطي (خطةُ النسخ)

export interface BackupSettings {
  enabled: boolean;
  frequency: string;
  weekday: number | null;
  hour_local: number;
  keep_count: number;
  alert_after_hours: number;
  alert_unpulled_count: number;
  max_bytes: number | null;
}

/** صفٌّ في الجدول — **ومصدرُه القرصُ لا جدولُ القاعدة**. */
export interface BackupRow {
  name: string;
  taken_at: string | null;
  alembic_revision: string | null;
  encrypted: boolean;
  size_bytes: number;
  /** يكتبها سكربتُ السحب على القرص — والسحبُ لا يمرّ بالتطبيق أصلاً. */
  pulled: boolean;
}

export interface BackupState {
  settings: BackupSettings;
  backups: BackupRow[];
  last_success_at: string | null;
  stale_hours: number | null;
  unpulled: number | null;
  disk_percent: number | null;
  total_bytes: number;
}

/** قوالبُ رسالة رمز التحقق (2026-08-19) — عالميةٌ لأن الرقمَ عالمي. */
export type OtpTemplateViolation = { code: string; message: string };

export type OtpTemplate = {
  purpose: "registration" | "password_reset";
  label: string;
  body: string;
  is_default: boolean;
  preview: string;
  /** الرمزُ في المعاينة عيّنةٌ وحدَه — لا رمزَ حقيقياً قبل الإرسال. */
  preview_sample_code: string;
  violations: OtpTemplateViolation[];
  rejected_at_send: boolean;
  updated_at: string | null;
};

export type OtpTemplates = {
  templates: OtpTemplate[];
  max_body_bytes: number;
  required_variables: string[];
  optional_variables: string[];
  applies_to_transport: string;
};

/** حسابُ المشرف نفسِه — اسمُ مستخدمٍ لا رقمَ هاتف (SPEC §25.9).
 *
 * `has_phone=false` يعني **لا استعادةَ ذاتية**: كلمةُ المرور تُعاد من الخادم
 * وحدَه، ومن يفقد الوصولَ إلى الخادم يفقد اللوحة. خطرٌ مقبولٌ مكتوب.
 */
export interface AdminAccount {
  username: string | null;
  /** حسابُ طوارئ — لا يُستعمل يومياً، ودخولُه يُكتب في التدقيق. */
  is_break_glass: boolean;
  has_phone: boolean;
}


/** بلاغُ صورةِ راكبٍ — **الصورةُ محجوبةٌ الآن**، والقرارُ يُعيد أو يحذف. */
export type PhotoReport = {
  id: string;
  subject_id: string;
  subject_name: string | null;
  subject_phone: string | null;
  reported_by: string;
  reporter_name: string | null;
  ride_id: string;
  created_at: string;
  resolution: string | null;
};


/** حدُّ خريطةِ الراكب لسوقٍ واحد — **لا حدُّ التوزيع** (`models/map_setting.py`). */
export type MapSetting = {
  country_code: CountryCode;
  nearby_radius_km: string;
  nearby_max_count: number;
  updated_at: string;
};


// ───────────────────────────────── مركباتُ الكراج والمتجر (2026-08-22)

/** درجاتُ الندرة — **نصٌّ في الخلفية لا تعدادُ Postgres**، فدرجةٌ خامسةٌ
 *  غداً كودٌ بلا ترحيلة (`models/vehicle_skin.py`). */
export type SkinRarity = "common" | "premium" | "rare" | "legendary";

/** سعرُ مركبةٍ في سوق — **والعملةُ تُشتقّ من الدولة ولا تُرسَل**. */
export type SkinPrice = {
  country_code: CountryCode;
  /** نصٌّ لا رقم: `NUMERIC(12,3)` يُسلسَل نصّاً، و§14 تمنع `Number`. */
  price: string;
};

/** صفُّ الكتالوج كما تراه اللوحة — **بحاله لا مصفّىً بسوق**. */
export type AdminSkin = {
  id: string;
  name: string;
  rarity: SkinRarity;
  /** مسارٌ نسبيٌّ يبنيه العميلُ على أصله — و`""` تعني «لا رسمةَ بعد». */
  store_image_url: string;
  map_image_url: string;
  map_scale_percent: number;
  map_rotates: boolean;
  visible_before_accept: boolean;
  max_supply: number | null;
  level_required: number | null;
  valid_from: string | null;
  valid_until: string | null;
  is_gift: boolean;
  is_public_default: boolean;
  is_feminine: boolean;
  feminine_drivers_only: boolean;
  is_active: boolean;
  prices: SkinPrice[];
  owners_count: number;
  sold_count: number;
  /** **مجموعٌ في الخلفية** (§14) — عملةٌ ← مبلغٌ نصّاً بثلاث خانات. */
  revenue: Record<string, string>;
};

/** صفٌّ في سجلِّ مشتريات المركبات — **مالٌ خرج من محفظة كبتن**. */
export type SkinPurchaseRow = {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_phone: string;
  skin_id: string;
  skin_name: string;
  rarity: SkinRarity;
  /** `purchase` · `gift` · `grant` — **يُقرأ ولا يُستنتج من غياب المبلغ**. */
  source: string;
  /** `null` للهديّة والمنحة — **ولا يُرسم صفراً**: صفرٌ يعني «دُفع لا شيء». */
  price_paid: string | null;
  currency: string | null;
  is_active_for_driver: boolean;
  created_at: string;
};

/** **المجاميعُ على الجدول كلِّه لا على الصفحة** (§14) — تصل مجموعةً. */
export type SkinPurchases = {
  rows: SkinPurchaseRow[];
  total: number;
  revenue_by_currency: Record<string, string>;
  gifted_count: number;
  granted_count: number;
  free_month_grants: number;
};

export type SkinStats = {
  top_selling: AdminSkin[];
  revenue_by_currency: Record<string, string>;
  total_owned: number;
};

/** رسمةٌ **مشحونةٌ مع الخلفية** — تُربط بمفتاحها بلا رفعِ ملفّ. */
export type BundledSkinAsset = {
  key: string;
  name: string;
  rarity: string;
  shell?: string;
  body?: string;
  note?: string;
  feminine?: string;
};

/** ناتجُ **التجربة الجافّة**: الرسمةُ بعد القصِّ والتصغير، بلا كتابةِ شيء.
 *
 * وهي ما تعرضه المعاينةُ — **لا الملفَّ الخام**: الهوامشُ الشفافةُ تُقصّ عند
 * الحفظ، فمعاينةُ الخام تُري المشرفَ حجماً غيرَ الذي سيُرسم، فيضبط النسبةَ
 * على ما لن يقع.
 */
export type SkinArtworkPreview = {
  store_image: string;
  map_image: string;
  media_type: string;
  source_size: number[] | null;
  trimmed: number[] | null;
  store_bytes: number;
  map_bytes: number;
};

/** مطالبةُ دفعٍ يدويّة — **ومصدرُها معها** فيُقرأ في التدقيق ولا يُخمَّن. */
export interface CliqClaim {
  /** **من دفع — بالاسم والرقم** (قرارُ المالك 2026-09-01).
   *
   *  وكانت القائمةُ تعرض مبلغاً ومرجعاً ووقتاً **ولا شيءَ يقول من**. */
  payer_name: string | null;
  payer_phone: string | null;
  /** **لحظةُ قوله «حوّلتُ»** — و`null` تعني «فتح الشاشةَ ولم يقل بعد». */
  declared_paid_at: string | null;
  id: string;
  cart_id: string;
  user_id: string;
  amount: string;
  currency: Currency;
  status: "created" | "paid" | "failed" | "cancelled";
  source: "manual" | "acquirer";
  purpose: "ride" | "wallet_topup" | "subscription";
  failure_reason: string | null;
  created_at: string;
}

// ═══════════ مستحقّاتُ الكباتن (الترحيلة `0061`) ═══════════
//
// **بيتُ دَينٍ ثالثٌ لا رصيدٌ سالب**: عمولةُ رحلةٍ قبض الكبتنُ أجرتها بيده.

export interface DriverDebtRow {
  id: string;
  driver_id: string;
  driver_name: string;
  driver_phone: string | null;
  amount: string;
  collected: string;
  currency: string;
  status: "outstanding" | "settled" | "written_off";
  source: "ride_commission";
  ride_id: string | null;
  created_at: string;
}

/** مطالبةُ سدادٍ يدويّةٍ بكليك — نفسُ شكل مطالبة الاشتراك، وهو مقصود. */
export interface DebtClaimRow {
  id: string;
  cart_id: string;
  amount: string;
  currency: string;
  status: "created" | "paid" | "failed" | "cancelled";
  failure_reason: string | null;
  created_at: string;
}

/** نمطُ عرض الطلب (SPEC §5.3، قرارُ المالك 2026-08-30). */
export type DispatchMode = "sequential" | "broadcast";

/** قواعدُ التوزيع لسوق — **صارت إعداداً بعد أن كانت ثابتاً في الشيفرة**. */
export interface DispatchSetting {
  country_code: CountryCode;
  mode: DispatchMode;
  offer_timeout_seconds: number;
  max_attempts: number;
  total_timeout_seconds: number;
  /** **تبريدٌ لا استبعادٌ دائم** — والصفرُ ممنوعٌ في القاعدة. */
  cooldown_seconds: number;
  broadcast_batch_size: number;
}

// ═══════ بلاطاتُ الخدمات واللافتات (الترحيلة `0063`) ═══════

export type ServiceTileStatus = "soon" | "active" | "hidden";
export type BannerLinkKind = "internal" | "external" | "none";

export interface ServiceTileRow {
  id: string;
  country_code: CountryCode;
  key: string;
  title: string;
  subtitle: string | null;
  icon: string;
  audience: CampaignAudience;
  sort_order: number;
  /** **فعّالةٌ بلا مقصدٍ مبنيٍّ لا تُقبل** — يمنعها البابُ بعلّته. */
  destination: string | null;
  status: ServiceTileStatus;
  /** **مدّةُ شارة «جديد»** — تختفي بانقضائها بلا نشر. */
  new_until: string | null;
  /** **أوّلُ ظهورٍ لأحد** — و`null` مسوّدةٌ لم يرَها إنسان، **وهي وحدَها ما
   *  يُحذف**. وما عُرض مرّةً يُخفى: حذفُه يمحو شاهداً على ما رآه الناس. */
  first_shown_at: string | null;
}

export interface PromoBannerRow {
  id: string;
  country_code: CountryCode;
  title: string;
  body: string | null;
  icon: string | null;
  audience: CampaignAudience;
  sort_order: number;
  starts_at: string;
  /** **إلزاميّة**: لافتةٌ بلا مدّةِ انتهاءٍ لا تُقبل. */
  ends_at: string;
  link_kind: BannerLinkKind;
  link: string | null;
  is_active: boolean;
  /** **أوّلُ إشعالٍ داخل نافذتها** — و`null` مسوّدةٌ تُحذف. */
  first_shown_at: string | null;
}


/** حملةُ تأكيد الأرقام (قرارُ المالك 2026-08-31). */
export type VerificationCampaignStatus =
  | "draft"
  | "running"
  | "paused"
  | "done"
  | "cancelled";

export interface VerificationCampaignRow {
  id: string;
  country_code: CountryCode;
  status: VerificationCampaignStatus;
  deadline_days: number;
  started_at: string | null;
  /** **لحظةُ التجمّد الآليّ** — و`null` تعني «تعمل». */
  paused_at: string | null;
  finished_at: string | null;
  /** **كم حساباً تشمله الآن** — يُقرأ **قبل** الضغط لا بعده. */
  scope_size: number;
  enrolled: number;
  suspended: number;
  resolved: number;
}

/** ما يملكه مشرفٌ — **ومن أين جاء** (البند ٥، §39٫٥).
 *
 * **و`explicit` ليس تفصيلاً**: مشرفٌ بلا صفوفٍ **ليس بلا صلاحيات** — يُقرأ
 * بافتراض دوره، **وبغير هذا الحقل يظنّ القارئُ أن الجدولَ الفارغَ منعٌ**.
 */
export interface AdminPermissions {
  user_id: string;
  name: string;
  roles: UserRole[];
  permissions: string[];
  explicit: boolean;
}

// ------------------------------------------------------- سجلُّ الإصدارات

/** التطبيقاتُ الثلاثة — **مرآةُ `ClientApp`**، ويحرسها `check:enums`. */
export type ClientApp = "rider" | "driver" | "panel";

/** إصدارٌ مسجَّل — **والرقمُ `versionCode` لا اسمُ نسخة**.
 *
 * `versionName` ثابتٌ في هذه الشجرة (قِيست حزمتان بـ`1.0` و`1.1` ورقمُهما
 * `392`)، **و`versionCode` هو ما يفرّق بناءً عن بناءٍ عند أندرويد نفسِه**.
 */
export interface AppRelease {
  id: string;
  app: ClientApp;
  build: number;
  min_supported_build: number;
  download_url: string;
  release_notes: string;
  reminder_hours: number;
  /** **أهذا هو الصفُّ الحاكم؟** — محسوبٌ في الخلفية لا بفرزِ صفحةٍ مقصوصة. */
  is_current: boolean;
  created_at: string;
  updated_at: string;
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

// ------------------------------------------------ السياساتُ والشروط (البند ١٠)

/** أيُّ وثيقة — **وثيقتان مستقلّتان لا واحدة** (§34). */
export type PolicyDocType = "privacy_policy" | "terms_of_use";

/** أيُّ تطبيقٍ تخصّه — **ولا عضوَ للمشرف** بقرارٍ مكتوب (§34). */
export type PolicyApp = "rider" | "driver";

/** نسخةٌ من وثيقة — **وكلُّ حفظٍ نسخةٌ جديدة، ولا تحريرَ فوق نفسه**. */
export interface PolicyVersion {
  id: string;
  country_code: CountryCode;
  doc_type: PolicyDocType;
  app: PolicyApp;
  version: number;
  /** **أدنى نسخةٍ تُبرئ** — يكتبها بابُ الحفظ وحدَه. */
  min_accepted_version: number;
  body_ar: string;
  body_en: string | null;
  requires_reconsent: boolean;
  is_published: boolean;
  published_at: string | null;
  /** **عددُ من وافق** — محسوبٌ في الخلفية، ومنه يُرسم زرُّ الحذف معطَّلاً. */
  consents: number;
  created_at: string;
}

/** صنفُ إصابةِ البحث العامّ — **وجهةٌ لا حال** (§39٫١٢٫٤).
 *
 * **ومعرّفُ الكبتن `drivers.id` ومعرّفُ الحساب `users.id`** — وأربعتُها UUID
 * لا تفترق بالنظر، **فالصنفُ هو ما يمنع فتحَ ملفِّ إنسانٍ آخر**.
 */
export type SearchKind = "user" | "driver" | "ride" | "claim";

/** إصابةٌ واحدة — **شكلُ `PickerOption` نفسُه بزيادة `kind`**، فالدرجُ يُرسم
 *  بمكوّن `Picker` القائم لا بمكوّنٍ ثانٍ بجانبه (§39٫١٢٫٨). */
export interface SearchHit {
  kind: SearchKind;
  id: string;
  label: string;
  hint: string | null;
}

export interface SearchHits {
  hits: SearchHit[];
}

/** بيانُ الجهة — **صفٌّ واحدٌ لا صفٌّ لكلِّ سوق**، وفراغُه حالٌ صحيحة. */
export interface OrgProfile {
  legal_name: string | null;
  address: string | null;
  privacy_email: string | null;
}

/** ما ينشره `GET /admin/site` — **الحقولُ نفسُها التي ينشرها البابُ العام**.
 *
 * **ولا حقلَ إداريٌّ زائد**: كلُّ ما في هذا الجدول عامٌّ بحكم بنائه، **فشاشةٌ
 * ترى أكثرَ ممّا يرى الزائرُ كانت ستوهم أن ثمّة سرّاً هنا** — وليس.
 */
export interface SiteSettings {
  hero_title: string;
  hero_subtitle: string;
  hero_note: string;
  announce_enabled: boolean;
  announce_text: string;
  announce_url: string;
  support_email: string;
  privacy_email: string;
  social_facebook: string;
  social_instagram: string;
  social_tiktok: string;
  social_x: string;
  social_whatsapp: string;
  hidden_sections: string[];
  hidden_cards: string[];
  faq: { q?: string; a?: string; order?: number }[];
  distribution_mode: string;
  play_url_rider: string;
  play_url_driver: string;
  ios_url: string;
  apk_page_enabled: boolean;
  policies_public: boolean;
  seo_description: string;
  /** **يُعرض ولا يُكتب من هذه الشاشة** — بيتُه `commission_settings`. */
  commission_percent: string;
  updated_at: string;
}

/** ما يُرسل — **وكلُّ حقلٍ اختياريّ**، و«لم يُرسَل» ليست «أُرسل فارغاً». */
export type SiteUpdate = Partial<Omit<SiteSettings, "commission_percent" | "updated_at">>;

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
  occurred_at: string;
  online: boolean;
  repeat: number;
  request_id?: string;
  note?: string;
};


// ------------------------------------------------ شاشةُ الأعطال (2026-09-20)

export type ErrorKind = "error" | "rejection" | "boundary" | "user_report";
export type ErrorStatus = "open" | "resolved" | "ignored";
export type ErrorPlatform = "android" | "ios" | "web";
/** **الافتراضُ «المتأثّرون»** — وهو الفرقُ الذي يجعل القائمةَ تُقرأ. */
export type ErrorSort = "users" | "last_seen" | "events";

export type ErrorGroupRow = {
  id: string;
  app: ClientApp;
  kind: ErrorKind;
  name: string;
  title: string;
  status: ErrorStatus;
  event_count: number;
  user_count: number;
  first_seen_at: string;
  last_seen_at: string;
  first_seen_release: string | null;
  last_seen_release: string | null;
};

export type ErrorEventRow = {
  id: string;
  platform: ErrorPlatform;
  os_version: string | null;
  release: string | null;
  channel: string | null;
  route: string | null;
  name: string;
  message: string;
  stack: string | null;
  component_stack: string | null;
  breadcrumbs: Record<string, unknown>[] | null;
  device_hash: string;
  online: boolean;
  repeat: number;
  request_id: string | null;
  user_reported: boolean;
  note: string | null;
  occurred_at: string;
  received_at: string;
};

export type ErrorGroupDetail = ErrorGroupRow & {
  latest: ErrorEventRow | null;
};
