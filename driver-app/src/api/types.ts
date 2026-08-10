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

export type DocumentType =
  "driving_license" | "national_id" | "vehicle_registration" | "vehicle_photo";

export type DocumentReviewStatus = "pending" | "approved" | "rejected";

/** أيُّ مُحقِّقٍ فعّالٌ الآن — تقرؤه الواجهة ولا تختاره (SPEC القسم 15/أ). */
export type VerificationMethod = "firebase" | "sms_otp" | "none";

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

export interface AuthMethod {
  /** الدخول كلمةُ مرورٍ دائماً؛ هذا يقول أيُّ مُحقِّقٍ يثبت الرقم. */
  verification: VerificationMethod;
  otp_length: number | null;
  otp_ttl_seconds: number | null;
}

export interface ChallengeResponse {
  sent: boolean;
  resend_after: number | null;
}

export interface CountryConfig {
  country_code: CountryCode;
  currency: Currency;
  features: Record<string, boolean>;
  vehicle_categories: VehicleCategory[];
  /** بادئةُ الدولة وطولُ رقمها الوطني — من `core/phone.py` عبر `/config`. */
  dial_code: string;
  national_number_length: number;
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
  missing_required: DocumentType[];
}

/** جوابُ الرفع — ومعه أثرُه على حالة الكبتن (سياسة 9-ب). */
export interface DocumentUpload {
  document: DriverDocument;
  driver_status: DriverStatus;
  approval_reverted: boolean;
}
