/** كل مسارات الخلفية التي يستعملها تطبيق الراكب — في ملف واحد.
 *
 * لا شاشة تكتب مساراً نصّاً: تغيّرُ مسارٍ في الخلفية يُصلَح هنا مرةً لا في
 * خمس شاشات. وما ليس للراكب ليس هنا (لا سحب، ولا اشتراكات، ولا لوحة إدارة).
 */

import { api } from "@/api/client";
import type {
  AppConfig,
  AuthMethod,
  AuthResponse,
  ChallengeResponse,
  OtpChannel,
  CliqTopup,
  Coordinates,
  CountryCode,
  Device,
  GenderPreference,
  NearbyDriver,
  NotificationPreferences,
  Payment,
  PaymentMethod,
  PlaceIcon,
  Rating,
  Ride,
  RideListItem,
  RideEstimate,
  RidePayments,
  SavedCard,
  PromoPreview,
  SavedPlace,
  Tip,
  TipOptions,
  TopupRequest,
  TransferRecipient,
  User,
  VehicleCategory,
  Wallet,
  WalletTransaction,
} from "@/api/types";

// ------------------------------------------------------------ الإعدادات

export const getConfig = (countryCode?: CountryCode) =>
  api.get<AppConfig>("/config", {
    anonymous: true,
    query: { country_code: countryCode },
  });

// ------------------------------------------------------------ المصادقة

export const getAuthMethod = () =>
  api.get<AuthMethod>("/auth/method", { anonymous: true });

export const startChallenge = (
  phone: string,
  countryCode: CountryCode,
  channel?: OtpChannel,
) =>
  api.post<ChallengeResponse>(
    "/auth/challenge",
    { phone, country_code: countryCode, channel },
    { anonymous: true },
  );

export const register = (payload: {
  phone: string;
  name: string;
  password: string;
  country_code: CountryCode;
  verification_token?: string;
  /** إقرارٌ ذاتيّ اختياري (المرحلة 10-ج) — ولا يُخمَّن عمّن تركه. */
  gender?: "male" | "female";
}) => api.post<AuthResponse>("/auth/register", { ...payload, role: "rider" }, { anonymous: true });

export const login = (phone: string, password: string, countryCode: CountryCode) =>
  api.post<AuthResponse>(
    "/auth/login",
    { phone, password, country_code: countryCode },
    { anonymous: true },
  );

export const startPasswordReset = (
  phone: string,
  countryCode: CountryCode,
  channel?: OtpChannel,
) =>
  api.post<ChallengeResponse>(
    "/auth/password-reset/challenge",
    { phone, country_code: countryCode, channel },
    { anonymous: true },
  );

export const resetPassword = (payload: {
  phone: string;
  country_code: CountryCode;
  verification_token: string;
  new_password: string;
}) => api.post<AuthResponse>("/auth/password-reset", payload, { anonymous: true });

export const verifyMyPhone = (verificationToken: string) =>
  api.post<User>("/auth/me/verify-phone", { verification_token: verificationToken });

export const getMe = () => api.get<User>("/auth/me");

/** ما تغيّره الراكبة في نفسها — الإعلان والتفضيل الافتراضي (المرحلة 10-ج). */
export const updateMe = (payload: {
  gender?: "male" | "female";
  ride_gender_preference?: GenderPreference;
}) => api.patch<User>("/auth/me", payload);

export const logout = (refreshToken: string) =>
  api.post<void>("/auth/logout", { refresh_token: refreshToken });

// ------------------------------------------------------------ الرحلات

export const estimateRide = (payload: {
  pickup: Coordinates;
  dropoff: Coordinates;
  vehicle_category: VehicleCategory;
  /** محطاتٌ **وسيطة** بترتيبها — والوجهةُ الأخيرة تبقى `dropoff`. */
  stops?: { lat: number; lng: number; address?: string | null }[];
}) => api.post<RideEstimate>("/rides/estimate", payload);

export const requestRide = (payload: {
  pickup: Coordinates;
  dropoff: Coordinates;
  vehicle_category: VehicleCategory;
  pickup_address?: string | null;
  dropoff_address?: string | null;
  /** غيابُه يعني «خذ افتراضي ملفي» لا `any` — القرار في الخلفية. */
  gender_preference?: GenderPreference;
  stops?: { lat: number; lng: number; address?: string | null }[];
  /** رمزُ الكوبون كما قبلته الخلفيةُ في التحقق (12-ز) — ورمزٌ خاطئ يرفض الطلب. */
  promo_code?: string;
}) => api.post<Ride>("/rides", payload);

// ------------------------------------------------------- الأماكن المحفوظة

export const listPlaces = () => api.get<SavedPlace[]>("/me/places");

export const createPlace = (payload: {
  label: string;
  lat: number;
  lng: number;
  address?: string | null;
  icon?: PlaceIcon;
}) => api.post<SavedPlace>("/me/places", payload);

export const updatePlace = (
  id: string,
  payload: Partial<{
    label: string;
    lat: number;
    lng: number;
    address: string | null;
    icon: PlaceIcon;
  }>,
) => api.patch<SavedPlace>(`/me/places/${id}`, payload);

export const deletePlace = (id: string) => api.del<void>(`/me/places/${id}`);

export const getActiveRide = () => api.get<Ride | null>("/rides/me/active");

export const getRide = (rideId: string) => api.get<Ride>(`/rides/${rideId}`);

export const listMyRides = (limit = 20, offset = 0) =>
  api.get<RideListItem[]>("/rides/me", { query: { limit, offset } });

/** `reason_code` سببٌ **مصنَّف** بجانب النص: `gender_mismatch` وحدها تُسقط
 *  رسوم الإلغاء وتُدخل بلاغاً، فلا تُترك لنصٍّ حر (المرحلة 10-ج). */
export const cancelRide = (
  rideId: string,
  reason?: string,
  reasonCode?: "gender_mismatch" | "other",
) =>
  api.post<Ride>(`/rides/${rideId}/cancel`, {
    reason: reason ?? null,
    reason_code: reasonCode ?? null,
  });

export const nearbyDrivers = (lat: number, lng: number) =>
  api.get<NearbyDriver[]>("/drivers/nearby", { query: { lat, lng } });

// ------------------------------------------------------------ التقييم

export const listRideRatings = (rideId: string) =>
  api.get<Rating[]>(`/rides/${rideId}/ratings`);

/** تحقّقٌ من كوبونٍ **لا يستهلكه** (12-ز): الخصمُ يُحسب في الخلفية على التقدير،
 *  والرمزُ يُرسل بعدها مع الطلب فتُجمَّد قاعدتُه على الرحلة. */
export const validatePromo = (
  code: string,
  fare: string,
  countryCode: CountryCode,
) =>
  api.post<PromoPreview>("/rides/promo/validate", {
    code,
    country_code: countryCode,
    fare,
  });

/** خيارا البقشيش وسقفُه — أو `offered=false` فلا تُرسم الأزرار (12-و). */
export const getTipOptions = (rideId: string) =>
  api.get<TipOptions>(`/rides/${rideId}/tip`);

export const addTip = (rideId: string, amount: string) =>
  api.post<Tip>(`/rides/${rideId}/tip`, { amount });

export const rateRide = (rideId: string, stars: number, comment?: string) =>
  api.post<Rating>(`/rides/${rideId}/ratings`, { stars, comment: comment || null });

// ------------------------------------------------------------ الدفع

export const getRidePayments = (rideId: string) =>
  api.get<RidePayments>(`/rides/${rideId}/payments`);

export const payRide = (
  rideId: string,
  method: PaymentMethod,
  idempotencyKey: string,
  extras: { save_card?: boolean; saved_card_id?: string } = {},
) =>
  api.post<RidePayments>(`/rides/${rideId}/payments`, {
    method,
    idempotency_key: idempotencyKey,
    ...extras,
  });

/** مرجع حوالة كليك — **يُكتب مرةً واحدة** (SPEC القسم 6.3). */
export const submitCliqReference = (paymentId: string, transferReference: string) =>
  api.post<RidePayments>(`/payments/${paymentId}/cliq-reference`, {
    transfer_reference: transferReference,
  });

export const getCardOrder = (cartId: string) =>
  api.get<import("@/api/types").CardOrder>(`/payments/card/orders/${cartId}`);

export const simulateMockCard = (cartId: string, outcome: "paid" | "declined") =>
  api.post<import("@/api/types").CardOrder>(`/payments/card/mock/${cartId}`, { outcome });

export const listSavedCards = () => api.get<SavedCard[]>("/payments/cards");

export const setDefaultCard = (cardId: string) =>
  api.post<SavedCard>(`/payments/cards/${cardId}/default`);

export const deleteSavedCard = (cardId: string) =>
  api.del<void>(`/payments/cards/${cardId}`);

export const confirmPayment = (paymentId: string) =>
  api.post<Payment>(`/payments/${paymentId}/confirm`);

// ------------------------------------------------------------ المحفظة

export const getWallet = () => api.get<Wallet>("/wallet/me");

export const listTransactions = (limit = 20, offset = 0) =>
  api.get<WalletTransaction[]>("/wallet/me/transactions", { query: { limit, offset } });

export const listTopups = (limit = 20, offset = 0) =>
  api.get<TopupRequest[]>("/wallet/me/topups", { query: { limit, offset } });

/** كليك اليدوي: طلبٌ ينتظر موظفاً (SPEC القسم 7). */
export const createTopupRequest = (amount: string, reference: string) =>
  api.post<TopupRequest>("/wallet/me/topups", {
    method: "cliq",
    amount,
    reference,
  });

export const createCardTopup = (amount: string, extras: { save_card?: boolean; saved_card_id?: string } = {}) =>
  api.post<import("@/api/types").CardOrder>("/wallet/me/topups/card", {
    amount,
    ...extras,
  });

/** كليك الآلي: رمزٌ يُمسح وحسابُ التاجر يشهد (SPEC القسم 7 — المرحلة 8). */
export const createCliqTopup = (amount: string) =>
  api.post<CliqTopup>("/wallet/me/topups/cliq", { amount });

export const checkCliqTopup = (cartId: string) =>
  api.get<CliqTopup>(`/wallet/me/topups/cliq/${cartId}`);

export const lookupRecipient = (phone: string) =>
  api.get<TransferRecipient>("/wallet/transfer/recipient", { query: { phone } });

export const transfer = (recipientPhone: string, amount: string, idempotencyKey: string) =>
  api.post<WalletTransaction>("/wallet/me/transfers", {
    recipient_phone: recipientPhone,
    amount,
    idempotency_key: idempotencyKey,
  });

// ------------------------------------------------------------ الأجهزة

export const registerDevice = (payload: {
  device_id: string;
  token: string;
  platform: "ios" | "android" | "web";
}) => api.put<Device>("/me/devices", payload);

export const unregisterDevice = (deviceId: string) =>
  api.del<void>(`/me/devices/${deviceId}`);

export const getNotificationPreferences = () =>
  api.get<NotificationPreferences>("/me/notification-preferences");

export const setNotificationPreferences = (marketingPushEnabled: boolean) =>
  api.put<NotificationPreferences>("/me/notification-preferences", {
    marketing_push_enabled: marketingPushEnabled,
  });
