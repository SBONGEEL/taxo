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
  phone: string;
  name: string;
  role: UserRole;
  country_code: CountryCode;
  is_blocked: boolean;
  phone_verified: boolean;
  marketing_push_enabled: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
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
  verification: string;
  verification_channels: string[];
}

export interface AppConfig {
  app: string;
  auth: { verification: string; otp_length: number | null };
  countries: CountryConfig[];
  providers: Record<string, Record<string, string | undefined>>;
  default_country_code: CountryCode;
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

export type DriverStatus = "pending" | "approved" | "rejected" | "suspended";

export type DocumentType =
  "driving_license" | "national_id" | "vehicle_registration" | "vehicle_photo";

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

export interface DriverDocuments {
  documents: DriverDocument[];
  missing_required: DocumentType[];
}

// ------------------------------------------------------------ المالية

export type TopupMethod = "cliq" | "cash";
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
  | "tips_enabled"
  | "promo_codes_enabled"
  | "driver_referrals_enabled"
  | "scheduled_rides_enabled"
  | "ride_sharing_enabled";

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
  updated_at: string;
}

/** حافزُ الإحالة per-country (12-ح) — **صفرُ المبلغ «لم يُحدَّد»** فلا يُدفع. */
export interface ReferralSetting {
  country_code: CountryCode;
  reward_amount: string;
  required_rides: number;
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

export interface PaymentSetting {
  id: string;
  country_code: CountryCode;
  cliq_confirmation_hours: number;
  /** مبالغُ البقشيش (12-و) — **صفرٌ يعني «لم يُضبط»** فتُخفى الميزةُ في التطبيق. */
  tip_preset_small: string;
  tip_preset_medium: string;
  tip_max: string;
  updated_at: string;
}

/** رمزُ خصمٍ كما تراه اللوحة (12-ز) — وثلاثةُ أرقامٍ **محسوبة** لا مراكمة. */
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
  | "payout";

export interface ProviderField {
  key: string;
  label: string;
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

// ------------------------------------------------------------ سجل الرحلات

export interface RideParty {
  user_id: string;
  name: string;
  phone: string;
}

export interface RideDriverParty extends RideParty {
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
  rider: RideParty;
  driver: RideDriverParty | null;
  pickup_address: string | null;
  dropoff_address: string | null;
  distance_km: string;
  actual_distance_km: string | null;
  estimated_fare: string;
  final_fare: string | null;
  cancellation_fee: string | null;
  payment_methods: PaymentMethod[];
  paid_amount: string;
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

export interface AdminRideDetail extends AdminRideRow {
  pickup_lat: number;
  pickup_lng: number;
  dropoff_lat: number;
  dropoff_lng: number;
  duration_min: string;
  commission_percent_at_ride: string;
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
  | "adjustment";

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
export type SubscriptionStatus = "active" | "expired";

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
