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
