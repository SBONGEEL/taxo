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
  CardOrder,
  ChallengeResponse,
  CountryCode,
  DocumentType,
  DocumentUpload,
  Driver,
  DriverDocuments,
  DriverProfile,
  DriverStatus,
  DriverSubscription,
  DriverWallet,
  Earnings,
  GenderPreference,
  LoginResponse,
  MyReferrals,
  MySubscription,
  NotificationPreferences,
  OtpChannel,
  Payment,
  Rating,
  Ride,
  RideListItem,
  RidePayments,
  SavedCard,
  User,
  UserNotification,
  Vehicle,
  VehicleCategory,
  WalletTransaction,
  Withdrawal,
  WithdrawalMethod,
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
  api.post<LoginResponse>(
    "/auth/login",
    { phone, password, country_code },
    { anonymous: true },
  );

export const getMe = () => api.get<User>("/auth/me");

/** تحدّي إثبات الرقم عند **التسجيل** — مسارٌ غير مسار الاستعادة. */
export const startSignupChallenge = (
  phone: string,
  country_code: CountryCode,
  channel?: OtpChannel,
) =>
  api.post<ChallengeResponse>(
    "/auth/challenge",
    { phone, country_code, channel },
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
  channel?: OtpChannel,
) =>
  api.post<ChallengeResponse>(
    "/auth/password-reset/challenge",
    { phone, country_code, channel },
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
export const updateDriver = (payload: {
  cliq_alias?: string;
  gender_preference?: GenderPreference;
  /** إذنُ التجديد التلقائي (البند ١٤) — بيد الكبتن وحدَه. */
  auto_renew?: boolean;
}) => api.patch<Driver>("/drivers/me", payload);

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

/** تعديلُ بيانات المركبة (`FUTURE-FEATURES` بند 43).
 *
 * **والجوابُ يقول ما وقع للاعتماد** (`approval_reverted`): تغييرُ ما تشهد
 * عليه رخصةُ المركبة يعيد الكبتن إلى المراجعة — نفس سياسة استبدال المستند.
 */
export const updateVehicle = (
  vehicleId: string,
  payload: Partial<{
    make: string;
    model: string;
    year: number;
    color: string;
    plate_number: string;
  }>,
) =>
  api.patch<{
    vehicle: Vehicle;
    approval_reverted: boolean;
    driver_status: DriverStatus;
  }>(`/drivers/me/vehicles/${vehicleId}`, payload);

/** ملخّصُ الأرباح — **مجموعٌ في الخلفية** بنافذة يوم الدولة (القسم 9 و12/7). */
export const getEarnings = (period: "today" | "week" | "month") =>
  api.get<Earnings>("/drivers/me/earnings", { query: { period } });

/** سجل الرحلات — «للكبتن ما أُسند إليه»، ومعه ملخّصُ دفع كل صف (البند 19). */
export const listMyRides = (limit = 20, offset = 0) =>
  api.get<RideListItem[]>("/rides/me", { query: { limit, offset } });

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

/** وصل الكبتنُ محطةً وسيطة — **من هنا يبدأ ختمُ الانتظار في الخلفية**. */
export const arriveAtStop = (rideId: string, stopId: string) =>
  api.post<Ride>(`/rides/${rideId}/stops/${stopId}/arrive`, {});

/** استئنافٌ — يُقفل العدّاد وتبدأ الساقُ التالية. */
export const resumeFromStop = (rideId: string, stopId: string) =>
  api.post<Ride>(`/rides/${rideId}/stops/${stopId}/resume`, {});

export const completeRide = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/complete`);

/** `reason_code` سببٌ **مصنَّف**: `gender_mismatch` وحدها تُسقط الرسوم وتُدخل
 *  بلاغاً على الطرف الآخر، فلا تُترك لنصٍّ حر (المرحلة 10-ج). */
export const cancelRide = (
  rideId: string,
  reason: string,
  reasonCode?: "gender_mismatch" | "other",
) =>
  api.post<Ride>(`/rides/${rideId}/cancel`, {
    reason,
    reason_code: reasonCode ?? null,
  });

// ------------------------------------------------------------ الدفع

/** **`/rides/…` لا `/payments/rides/…`**: راوترُ الدفع بلا بادئة، فالمسارُ
 *  المكرَّرُ يردّ 404 — وشاشةُ التحصيل تُرسم فارغةً بلا رسالة. قِيس في تشغيل
 *  المرحلة 13: الكبتنُ يُنهي الرحلة فيجد شاشةً بيضاء في اللحظة التي يقبض فيها. */
export const getRidePayments = (rideId: string) =>
  api.get<RidePayments>(`/rides/${rideId}/payments`);

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
export const getDriverWallet = () => api.get<DriverWallet>("/wallet/me/driver");

/** دفتر المحفظة — قيودٌ لا تُعدَّل، فالتصحيح قيدٌ مضاد لا تحرير. */
export const listWalletTransactions = (limit = 20, offset = 0) =>
  api.get<WalletTransaction[]>("/wallet/me/transactions", {
    query: { limit, offset },
  });

export const listWithdrawals = (limit = 20, offset = 0) =>
  api.get<Withdrawal[]>("/wallet/me/withdrawals", { query: { limit, offset } });

/** طلب سحب — للكباتن وحدهم (القسم 7)، ولا قيد في الدفتر قبل `paid`. */
export const requestWithdrawal = (amount: string, method: WithdrawalMethod) =>
  api.post<Withdrawal>("/wallet/me/withdrawals", { amount, method });

export const getMySubscription = () =>
  api.get<MySubscription>("/subscriptions/me");

export const getSubscriptionHistory = () =>
  api.get<DriverSubscription[]>("/subscriptions/me/history");

/** الشراء بالبطاقة — يفتح عمليةً عند المزود ولا يُنشئ اشتراكاً قبل جوابه. */
export const buySubscriptionWithCard = (
  planId: string,
  options: { saveCard?: boolean; savedCardId?: string } = {},
) =>
  api.post<CardOrder>("/subscriptions/card", {
    plan_id: planId,
    save_card: options.saveCard ?? false,
    saved_card_id: options.savedCardId ?? null,
  });

/** حالُ الطلب بعد عودة المتصفح — تسأل الخلفيةُ المزودَ ثم تسوّي إن حُسم. */
export const getCardOrder = (cartId: string) =>
  api.get<CardOrder>(`/payments/card/orders/${cartId}`);

/** الشراء من المحفظة — القناة الفورية الوحيدة من التطبيق مع البطاقة. */
export const buySubscription = (planId: string, idempotencyKey: string) =>
  api.post<DriverSubscription>("/subscriptions", {
    plan_id: planId,
    idempotency_key: idempotencyKey,
  });

// ------------------------------------------------------------ الحساب

/** صندوق الوارد — أثرُ الحدث الدائم، يوجد ولو لم يُرسل Push (المرحلة 9-ب). */
export const listNotifications = (limit = 30, offset = 0) =>
  api.get<UserNotification[]>("/me/notifications", {
    query: { limit, offset },
  });

export const getUnreadCount = () =>
  api.get<{ unread: number }>("/me/notifications/unread-count");

/** `ids` غائبةً تعني «الكل» — وقائمةٌ فارغة صريحة تعني لا شيء. */
export const markNotificationsRead = (ids?: string[]) =>
  api.post<{ unread: number }>("/me/notifications/read", ids ? { ids } : {});

/** تفضيلاتُ الإشعارات — مفتاحٌ واحد: إشعارات العروض (SPEC القسم 11/8). */
export const getNotificationPreferences = () =>
  api.get<NotificationPreferences>("/me/notification-preferences");

export const setNotificationPreferences = (marketing: boolean) =>
  api.put<NotificationPreferences>("/me/notification-preferences", {
    marketing_push_enabled: marketing,
  });

/** البطاقات المحفوظة — تُقرأ وتُحذف وتُجعل افتراضية، ولا تُضاف من هنا. */
export const listSavedCards = () => api.get<SavedCard[]>("/payments/cards");

export const makeCardDefault = (cardId: string) =>
  api.post<SavedCard>(`/payments/cards/${cardId}/default`);

export const deleteSavedCard = (cardId: string) =>
  api.del<void>(`/payments/cards/${cardId}`);

export const listDocuments = () =>
  api.get<DriverDocuments>("/drivers/me/documents");

/** رفعُ مستند — `multipart` لا JSON، فيمر خارج `api.*` بعميلٍ يعرف الملفات. */
export const uploadDocument = (docType: DocumentType, file: File) =>
  upload<DocumentUpload>(`/drivers/me/documents/${docType}`, file);

// ------------------------------------------------- إحالةُ السائقات (12-ح)

/** رمزي ومن سجّل به. **قراءةٌ وحدها**: الرمزُ يُولَّد مع الحساب، والإسنادُ في
 *  التسجيل، والدفعُ مهمةٌ دورية — فلا زرَّ «اطلب مكافأتي» يصير باباً ثانياً. */
export const getMyReferrals = () =>
  api.get<MyReferrals>("/drivers/me/referrals");

/** شكلُ مسار الرحلة على الطرق — نفسُ الخطِّ الذي يراه الراكب (البند ٨).
 *
 * **مجمَّدٌ على الرحلة منذ القبول**، فقراءتُه ثانيةً تعيد الشيءَ نفسَه — ولا
 * يُطلب مسارٌ جديدٌ لحركة الكبتن: التقدّمُ قصٌّ في التطبيق لا نداءٌ لكل بثّة.
 */
export const getRouteLine = (rideId: string) =>
  api.get<{ points: number[][] }>(`/rides/${rideId}/route-line`);
