/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import { api, upload } from "@/api/client";
import type {
  AppConfig,
  AuthMethod,
  AuthResponse,
  ChallengeResponse,
  CountryCode,
  DocumentType,
  DocumentUpload,
  Driver,
  DriverDocuments,
  DriverProfile,
  DriverSubscription,
  MySubscription,
  Payment,
  Rating,
  Ride,
  RidePayments,
  User,
  Vehicle,
  VehicleCategory,
  Wallet,
} from "@/api/types";

// ------------------------------------------------------------ الإعدادات

export const getConfig = () =>
  api.get<AppConfig>("/config", { anonymous: true });

export const getAuthMethod = () =>
  api.get<AuthMethod>("/auth/method", { anonymous: true });

// ------------------------------------------------------------ المصادقة

/** `country_code` اختياري: شاشةُ الدخول في التصميم بلا منتقي دولة، والخلفية
 * تستنتجها من الصيغة الدولية (`core/phone.py::resolve_phone`) وترفض بعبارةٍ
 * صريحة ما ليس دولياً — فلا تخترع الواجهة استنتاجاً من عندها. */
export const login = (
  phone: string,
  password: string,
  country_code?: CountryCode,
) =>
  api.post<AuthResponse>(
    "/auth/login",
    { phone, password, country_code },
    { anonymous: true },
  );

export const getMe = () => api.get<User>("/auth/me");

/** تحدّي إثبات الرقم عند **التسجيل** — مسارٌ غير مسار الاستعادة. */
export const startSignupChallenge = (
  phone: string,
  country_code: CountryCode,
) =>
  api.post<ChallengeResponse>(
    "/auth/challenge",
    { phone, country_code },
    { anonymous: true },
  );

/** التسجيل: الإثبات وكلمةُ المرور في **طلبٍ واحد** — فلا حساب بلا كلمة مرور
 * ولا إثباتٌ يفتح جلسةً وحده (SPEC القسم 11/1). */
export const registerAccount = (payload: {
  phone: string;
  name: string;
  password: string;
  country_code: CountryCode;
  verification_token?: string;
}) =>
  api.post<AuthResponse>(
    "/auth/register",
    { ...payload, role: "driver" },
    { anonymous: true },
  );

export const logout = (refresh_token: string) =>
  api.post<void>("/auth/logout", { refresh_token });

/** تحدّي إثبات الرقم عند **استعادة كلمة المرور** — مسارٌ غير مسار التسجيل. */
export const startPasswordResetChallenge = (
  phone: string,
  country_code?: CountryCode,
) =>
  api.post<ChallengeResponse>(
    "/auth/password-reset/challenge",
    { phone, country_code },
    { anonymous: true },
  );

/** لا جلسةَ تُفتح بمجرد الإثبات: التوكن يُصدر بعد كتابة الكلمة الجديدة. */
export const resetPassword = (payload: {
  phone: string;
  country_code?: CountryCode;
  verification_token: string;
  new_password: string;
}) =>
  api.post<AuthResponse>("/auth/password-reset", payload, { anonymous: true });

// ------------------------------------------------------------ الأجهزة

export const registerDevice = (payload: {
  device_id: string;
  token: string;
  platform: string;
}) => api.put<void>("/me/devices", payload);

export const unregisterDevice = (deviceId: string) =>
  api.del<void>(`/me/devices/${encodeURIComponent(deviceId)}`);

// ------------------------------------------------------------ الكبتن

export const getDriverProfile = () => api.get<DriverProfile>("/drivers/me");

/** ما يملك الكبتن تغييره من ملفه — `cliq_alias` اليوم (SPEC القسم 9). */
export const updateDriver = (payload: { cliq_alias?: string }) =>
  api.patch<Driver>("/drivers/me", payload);

export const addVehicle = (payload: {
  make: string;
  model: string;
  year: number;
  color: string;
  plate_number: string;
  category: VehicleCategory;
}) => api.post<Vehicle>("/drivers/me/vehicles", payload);

// ------------------------------------------------------------ الرحلة

export const getActiveRide = () => api.get<Ride | null>("/rides/me/active");

/** سجل الرحلات — «للكبتن ما أُسند إليه» (`rides.list_rides_for_user`). */
export const listMyRides = (limit = 20, offset = 0) =>
  api.get<Ride[]>("/rides/me", { query: { limit, offset } });

export const getRide = (rideId: string) => api.get<Ride>(`/rides/${rideId}`);

export const listRideRatings = (rideId: string) =>
  api.get<Rating[]>(`/rides/${rideId}/ratings`);

export const acceptRide = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/accept`);

export const declineRide = (rideId: string) =>
  api.post<void>(`/rides/${rideId}/decline`);

export const arriveRide = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/arrive`);

export const startRide = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/start`);

export const completeRide = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/complete`);

export const cancelRide = (rideId: string, reason: string) =>
  api.post<Ride>(`/rides/${rideId}/cancel`, { reason });

// ------------------------------------------------------------ الدفع

export const getRidePayments = (rideId: string) =>
  api.get<RidePayments>(`/payments/rides/${rideId}/payments`);

/** «استلمت المبلغ» — تأكيدُ الكبتن هو ما يُثبّت دفعة الكاش (SPEC القسم 6.1). */
export const confirmPayment = (paymentId: string) =>
  api.post<Payment>(`/payments/${paymentId}/confirm`);

/** «لم يصلني» على دفعة كليك → تنتقل للوحة الإدارة (القسم 6.2). */
export const disputePayment = (paymentId: string, reason: string) =>
  api.post<Payment>(`/payments/${paymentId}/dispute`, { reason });

export const rateRide = (rideId: string, stars: number, comment?: string) =>
  api.post<Rating>(`/rides/${rideId}/ratings`, { stars, comment });

// ------------------------------------------------------------ المال

/** محفظة الكبتن — مفتاحها `users.id` لا `drivers.id` (SPEC القسم 9). */
export const getDriverWallet = () => api.get<Wallet>("/wallet/me/driver");

export const getMySubscription = () =>
  api.get<MySubscription>("/subscriptions/me");

export const getSubscriptionHistory = () =>
  api.get<DriverSubscription[]>("/subscriptions/me/history");

/** الشراء من المحفظة — القناة الفورية الوحيدة من التطبيق مع البطاقة. */
export const buySubscription = (planId: string, idempotencyKey: string) =>
  api.post<DriverSubscription>("/subscriptions", {
    plan_id: planId,
    idempotency_key: idempotencyKey,
  });

export const listDocuments = () =>
  api.get<DriverDocuments>("/drivers/me/documents");

/** رفعُ مستند — `multipart` لا JSON، فيمر خارج `api.*` بعميلٍ يعرف الملفات. */
export const uploadDocument = (docType: DocumentType, file: File) =>
  upload<DocumentUpload>(`/drivers/me/documents/${docType}`, file);
