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
  | "completed"
  | "cancelled_by_rider"
  | "cancelled_by_driver"
  | "no_driver_found";

export type PaymentMethod = "cash" | "cliq" | "card" | "wallet";
export type PaymentStatus =
  | "pending"
  | "confirmed"
  | "failed"
  | "disputed"
  | "refunded";

export type VerificationMethod = "firebase" | "sms_otp" | "none";

export interface AuthMethod {
  login: "password";
  verification: VerificationMethod;
  otp_length: number | null;
}

export interface User {
  id: string;
  phone: string;
  name: string;
  role: UserRole;
  country_code: CountryCode;
  is_blocked: boolean;
  phone_verified: boolean;
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

export interface ChallengeResponse {
  sent: boolean;
  expires_in: number | null;
  resend_after: number | null;
}

export interface CountryConfig {
  country_code: CountryCode;
  currency: Currency;
  features: Record<string, boolean>;
  vehicle_categories: VehicleCategory[];
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
}

export interface RideVehicle {
  make: string;
  model: string;
  color: string;
  plate_number: string;
  category: VehicleCategory;
}

export interface RideDriver {
  id: string;
  name: string;
  rating_avg: string;
  vehicle: RideVehicle | null;
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
  driver: RideDriver | null;
  created_at: string;
  accepted_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
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

export interface NearbyDriver {
  ref: string;
  lat: number;
  lng: number;
  heading: number | null;
  vehicle_category: VehicleCategory;
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
