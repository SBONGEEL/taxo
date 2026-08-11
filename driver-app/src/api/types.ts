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

export type RideStatus =
  | "requested"
  | "searching"
  | "accepted"
  | "arrived"
  | "in_progress"
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
  created_at: string;
  accepted_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
}

export interface Wallet {
  owner_id: string;
  owner_type: "driver" | "rider";
  balance: string;
  currency: Currency;
  frozen: boolean;
}

/** محفظة الكبتن: الرصيد **والمتاح منه** بعد حجز الطلبات القائمة (القسم 9). */
export interface DriverWallet extends Wallet {
  available_for_withdrawal: string;
  min_withdrawal_amount: string;
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
  | "adjustment";

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

export interface SubscriptionPlan {
  id: string;
  country_code: CountryCode;
  name: string;
  duration_type: "daily" | "weekly" | "monthly";
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

export type PaymentMethod = "cash" | "wallet" | "card" | "cliq" | "mixed";
export type PaymentStatus =
  | "pending"
  | "awaiting_confirmation"
  | "confirmed"
  | "failed"
  | "refunded"
  | "disputed";

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
  duration_type: "daily" | "weekly" | "monthly";
  starts_at: string;
  expires_at: string;
  amount_paid: string;
  currency: Currency;
  payment_method: PaymentMethod;
  status: "active" | "expired" | "cancelled";
}
