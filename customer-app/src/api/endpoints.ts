/** كل مسارات الخلفية التي يستعملها تطبيق الراكب — في ملف واحد.
 *
 * لا شاشة تكتب مساراً نصّاً: تغيّرُ مسارٍ في الخلفية يُصلَح هنا مرةً لا في
 * خمس شاشات. وما ليس للراكب ليس هنا (لا سحب، ولا اشتراكات، ولا لوحة إدارة).
 */

import { api, upload } from "@/api/client";
import type { UploadOptions } from "@/api/client";
import type {
  AppConfig,
  MyReferrals,
  AuthMethod,
  AuthResponse,
  Booking,
  ChallengeResponse,
  CliqTopup,
  Coordinates,
  CountryCode,
  Device,
  GenderPreference,
  LoginResponse,
  NearbyDriver,
  NotificationPreferences,
  OtpChannel,
  PaymentMethod,
  PlaceIcon,
  PromoPreview,
  Rating,
  Ride,
  RideEstimate,
  RideListItem,
  RidePayments,
  SavedCard,
  SavedPlace,
  Tip,
  TipOptions,
  TopupRequest,
  TransferRecipient,
  User,
  UserNotification,
  VehicleCategory,
  Wallet,
  WalletTransaction,
  Storefront,
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
}) => api.post<AuthResponse>("/auth/register", { ...payload, role: "rider", app: CLIENT_APP }, { anonymous: true });

/** **التطبيقُ يُعلن نفسَه في كل بابٍ يُصدر جلسة** (`core/app_scope.py`).
 *
 * قرارُ المالك 2026-08-15: كلُّ تطبيقٍ لدوره وحدَه، و`admin`/`support` لا
 * يدخلان تطبيقَي الراكب والكبتن. والرفضُ في الخلفية — وهذا الحقلُ هو ما
 * يجعلها تعرف من يسأل. **ودعوى تضييقٍ لا توسيع**: من ادّعى تطبيقاً ليس دورَه
 * مَنَع نفسَه ولم ينل شيئاً.
 */
export const CLIENT_APP = "rider";

export const login = (phone: string, password: string, countryCode: CountryCode) =>
  api.post<LoginResponse>(
    "/auth/login",
    { phone, password, country_code: countryCode, app: CLIENT_APP },
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

/** صورةُ صاحب الحساب — **تُنشر فور رفعها بلا مراجعة** (قرارُ المالك
 *  2026-08-22)، فليس فيها انتظارٌ يُعلَن ولا حالٌ تُتابَع.
 *
 *  **و`upload` لا `api.put`**: نسبةُ التقدّم تحتاج `XMLHttpRequest` (SPEC
 *  ١٧.٦)، ومعها زرُّ الإلغاء وكاشفُ الركود — ثلاثتُها شرطُ رفعٍ بلا مهلة.
 *
 *  **والردُّ `User` كاملاً** لا حقلاً: الجلسةُ تُحدَّث من نفس الجسم الذي
 *  يردّه كلُّ بابٍ يمسّ الحساب، فلا شكلَ ثانٍ يفترق عنه. */
export const setMyPhoto = (file: File, options: UploadOptions = {}) =>
  upload<User>("/auth/me/photo", file, options);

export const clearMyPhoto = () => api.del<User>("/auth/me/photo");

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
  /** المشاركة (12-ي) — و`share_gender_confirmed` **حقلٌ مستقلٌّ لا مدموج**:
   *  طلبٌ بتفضيلٍ نسائيٍّ لا يُشارَك إلا باختيارٍ صريحٍ من صاحبته، ودمجُه في
   *  `share` يجعل الموافقةَ ضمنيةً — والقبولُ الصامتُ لا يكفي أمناً. */
  share?: boolean;
  share_gender_confirmed?: boolean;
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

export const getActiveRide = () => api.get<Ride | null>("/rides/me/active?side=rider");

export const getRide = (rideId: string) => api.get<Ride>(`/rides/${rideId}`);

export const listMyRides = (limit = 20, offset = 0) =>
  api.get<RideListItem[]>("/rides/me", { query: { limit, offset, side: "rider" } });

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

// **وحُذف `confirmPayment` من تطبيق الراكب** (2026-08-23): البابُ في الخلفية
// `CurrentDriver` — **فراكبٌ يطرقه يُردّ ٤٠٣ دائماً**، ولا شاشةَ تطرقه.
// وتأكيدُ الكاش فعلُ من قبض المال، والراكبُ يقرأ حالَ الدفع ولا يقرّرها.
//
// **وبقاؤه مُصرَّحاً كان دعوةً** لمن يبني شاشةَ الدفع غداً أن يصله بزرّ،
// فيبني زرّاً يردّ ٤٠٣ — وهو أسوأُ من غيابه: **زرٌّ لا يعمل يُقرأ عطباً في
// الحساب لا في الصلاحية**.

// ------------------------------------------------------------ المحفظة

export const getWallet = () => api.get<Wallet>("/wallet/me?wallet=rider");

export const listTransactions = (limit = 20, offset = 0) =>
  api.get<WalletTransaction[]>("/wallet/me/transactions?wallet=rider", {
    query: { limit, offset, wallet: "rider" },
  });

export const listTopups = (limit = 20, offset = 0) =>
  api.get<TopupRequest[]>("/wallet/me/topups", { query: { limit, offset } });

/** كليك اليدوي: طلبٌ ينتظر موظفاً (SPEC القسم 7). */
export const createTopupRequest = (amount: string, reference: string) =>
  api.post<TopupRequest>("/wallet/me/topups?wallet=rider", {
    method: "cliq",
    amount,
    reference,
  });

/** **يُعلن محفظةَ الراكب** (SPEC §22): البابُ يخدمه التطبيقان، ومن حمل
 *  الدورين لا يقول دورُه أيَّ محفظةٍ يعني — فيرتدّ بلا إعلانٍ ولا يشحن أصلاً.
 *  وهذا التطبيقُ تطبيقُ الراكب، **فسياقُ الفعل معلومٌ هنا يقيناً** كما هو
 *  معلومٌ في `getWallet` أعلاه (`?wallet=rider`). */
export const createCardTopup = (amount: string, extras: { save_card?: boolean; saved_card_id?: string } = {}) =>
  api.post<import("@/api/types").CardOrder>("/wallet/me/topups/card?wallet=rider", {
    amount,
    ...extras,
  });

/** كليك الآلي: رمزٌ يُمسح وحسابُ التاجر يشهد (SPEC القسم 7 — المرحلة 8). */
export const createCliqTopup = (amount: string) =>
  api.post<CliqTopup>("/wallet/me/topups/cliq?wallet=rider", { amount });

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

// --------------------------------------------- الرحلات المجدولة (12-ط)

export const listBookings = () => api.get<Booking[]>("/me/bookings");

/** حجزٌ جديد — **والموعدُ يُرسل بمنطقته الزمنية**: `datetime-local` يعطي وقتاً
 *  بلا منطقة، وإرسالُه كما هو يجعل الخلفيةَ ترفضه (وهي تفعل ذلك صراحةً بدل أن
 *  تخمّن منطقةً فتحجز موعداً غير الذي رآه صاحبُه). */
export const createBooking = (body: {
  pickup: Coordinates;
  dropoff: Coordinates;
  scheduled_at: string;
  vehicle_category: VehicleCategory;
  pickup_address?: string | null;
  dropoff_address?: string | null;
  gender_preference?: GenderPreference;
}) => api.post<Booking>("/me/bookings", body);

export const cancelBooking = (bookingId: string) =>
  api.del<Booking>(`/me/bookings/${bookingId}`);

// ------------------------------------------------ صندوق الإشعارات (9-ب)

/** **صندوقُ وارد لا سجلُّ إرسال**: الصفُّ أثرُ الحدث لا أثرُ المزود — يوجد بلا
 *  عقد FCM، ويوجد حين كان المقبسُ مفتوحاً فلم يُرسل Push أصلاً. */
export const listNotifications = (limit = 30, offset = 0) =>
  api.get<UserNotification[]>(
    `/me/notifications?limit=${limit}&offset=${offset}`,
  );

export const unreadCount = () =>
  api.get<{ unread: number }>("/me/notifications/unread-count");

/** بلا `ids` = الكلُّ مقروء — وهو ما يفعله زرُّ «تحديد الكل كمقروء». */
export const markNotificationsRead = (ids?: string[]) =>
  api.post<{ unread: number }>("/me/notifications/read", ids ? { ids } : {});

/** شكلُ مسار الرحلة على الطرق — للطرفين بعد القبول (البند ٨).
 *
 * **يُقرأ مرةً لكل رحلة**: الخلفيةُ تجمّده على الرحلة لحظةَ القبول، فقراءتُه
 * ثانيةً تعيد الشيءَ نفسَه — والتتبّعُ بعد البدء قصٌّ في المتصفح لا نداءٌ جديد.
 * وقائمةٌ فارغةٌ جوابٌ صحيح: تُرسم الدبابيسُ وحدها.
 */
export const getRouteLine = (rideId: string) =>
  api.get<{ points: number[][] }>(`/rides/${rideId}/route-line`);

/** رمزُ الإحالة ومن سجّل به — **منفذٌ واحدٌ للتطبيقين** (`/me/` لا `/drivers/me/`):
 *  الرمزُ صار لكل حساب، ومسارٌ تحت `/drivers` بابٌ لا يفتح للراكب أصلاً. */
export const getMyReferrals = () => api.get<MyReferrals>("/me/referrals");

/** رمزُ تسليمٍ إلى التطبيق الآخر — **قصيرُ العمر، أحاديُّ الاستعمال** (§23).
 *
 * ولا ينقل رمزَ التجديد: تدويرُه أحاديٌّ فحاملان يُبطل أحدُهما الآخر.
 */
export const startHandoff = () =>
  api.post<{ token: string; expires_in: number }>("/auth/handoff", {
    target: "driver",
  });

/** يبادل الرمزَ بجلسةٍ في هذا التطبيق — بلا كلمةِ مرورٍ ولا رمزِ تحقق. */
export const exchangeHandoff = (token: string) =>
  api.post<AuthResponse>(
    "/auth/handoff/exchange",
    { token, app: CLIENT_APP },
    { anonymous: true },
  );


/** بلاطاتُ الشاشة الرئيسة ولافتاتُها — **نداءٌ واحدٌ لشاشةٍ واحدة**.
 *
 * **وندءان يعنيان شاشةً تُرسم على مرحلتين**: البلاطاتُ تظهر ثم تقفز اللافتةُ
 * فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.
 *
 * **و`surface` سياقُ الفعل لا دورُ الفاعل**: من يحمل الدورين يرى ما يخصّ
 * التطبيقَ الذي هو فيه.
 */
export const getStorefront = () =>
  api.get<Storefront>("/storefront", { query: { surface: "rider" } });
