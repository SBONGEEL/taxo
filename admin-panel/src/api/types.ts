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

export type PaymentMethod = "cash" | "cliq" | "card" | "wallet";
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
  | "otp_verification_enabled";

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

export interface PaymentSetting {
  id: string;
  country_code: CountryCode;
  cliq_confirmation_hours: number;
  updated_at: string;
}

// ------------------------------------------------------------ العقود

export type ProviderKey =
  | "mapbox"
  | "telr"
  | "sms"
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
