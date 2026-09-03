/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import type { RouteStep } from "@/lib/next-instruction";
import type { UploadOptions } from "@/api/client";
import { API_URL, api, upload } from "@/api/client";
import type {
  CliqDeclare,
  CliqSubscriptionClaim,
  MyProgress,
  Advance,
  AdvanceState,
  DeactivationRequest,
  DeactivationState,
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
  NearbyDriver,
  NotificationPreferences,
  OtpChannel,
  Payment,
  Rating,
  Ride,
  Garage,
  SkinStore,
  BuySkinResult,
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
  DebtClaim,
  DriverDebtState,
  Storefront,
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
/** **التطبيقُ يُعلن نفسَه في كل بابٍ يُصدر جلسة** (`core/app_scope.py`).
 *
 * قرارُ المالك 2026-08-15: كلُّ تطبيقٍ لدوره وحدَه، و`admin`/`support` لا
 * يدخلان تطبيقَي الراكب والكبتن. والرفضُ في الخلفية — وهذا الحقلُ هو ما
 * يجعلها تعرف من يسأل. **ودعوى تضييقٍ لا توسيع**: من ادّعى تطبيقاً ليس دورَه
 * مَنَع نفسَه ولم ينل شيئاً.
 */
export const CLIENT_APP = "driver";

export const login = (
  phone: string,
  password: string,
  country_code?: CountryCode,
) =>
  api.post<LoginResponse>(
    "/auth/login",
    { phone, password, country_code, app: CLIENT_APP },
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
    { ...payload, role: "driver", app: CLIENT_APP },
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

export const getActiveRide = () => api.get<Ride | null>("/rides/me/active?side=driver");

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
  api.get<RideListItem[]>("/rides/me", { query: { limit, offset, side: "driver" } });

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
  api.get<WalletTransaction[]>("/wallet/me/transactions?wallet=driver", {
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
export const uploadDocument = (
  docType: DocumentType,
  file: File,
  options?: UploadOptions,
) => upload<DocumentUpload>(`/drivers/me/documents/${docType}`, file, options);

// ------------------------------------------------- إحالةُ السائقات (12-ح)

/** رمزي ومن سجّل به. **قراءةٌ وحدها**: الرمزُ يُولَّد مع الحساب، والإسنادُ في
 *  التسجيل، والدفعُ مهمةٌ دورية — فلا زرَّ «اطلب مكافأتي» يصير باباً ثانياً. */
export const getMyReferrals = () =>
  api.get<MyReferrals>("/me/referrals");

/** شكلُ مسار الرحلة على الطرق — نفسُ الخطِّ الذي يراه الراكب (البند ٨).
 *
 * **مجمَّدٌ على الرحلة منذ القبول**، فقراءتُه ثانيةً تعيد الشيءَ نفسَه — ولا
 * يُطلب مسارٌ جديدٌ لحركة الكبتن: التقدّمُ قصٌّ في التطبيق لا نداءٌ لكل بثّة.
 */
export const getRouteLine = (rideId: string) =>
  api.get<{
    points: number[][];
    /** خطواتُ الملاحة — للكبتن وحدَه، وفارغةٌ حين المفتاحُ مطفأ (البند ٧). */
    steps: RouteStep[];
    /** عتبةُ الانحراف بالأمتار — **تأتي من الخلفية** ولا تُكتب هنا (§17.3). */
    deviation_threshold_m: number;
  }>(`/rides/${rideId}/route-line`);

/** حالُ إلغاء التفعيل: طلبُه إن وُجد، وموانعُه، والمحتجَزُ برقمه (البند ١٣). */
export const getDeactivationState = () =>
  api.get<DeactivationState>("/drivers/me/deactivation");

export const requestDeactivation = (reason?: string) =>
  api.post<DeactivationRequest>("/drivers/me/deactivation", { reason });

export const cancelDeactivation = () =>
  api.del<DeactivationRequest>("/drivers/me/deactivation");

/** حالُ السلف: الأهليةُ بشروطها والسقفُ والدَّين (البند ١٥). */
export const getAdvanceState = () => api.get<AdvanceState>("/drivers/me/advances");

export const requestAdvance = (amount: string) =>
  api.post<Advance>("/drivers/me/advances", { amount });

/** سدادٌ كاملٌ من المحفظة — ويرفع الإيقافَ في المسار نفسِه لا بدورةٍ تالية. */
export const repayAdvance = () => api.post<Advance>("/drivers/me/advances/repay", {});

/** مهامُّ الشهر ومستواي وشاراتي — **قراءةٌ فقط**: للعمود كاتبٌ واحدٌ هو
 *  المهمّةُ الدورية، وزرٌّ يقول «حدّث مستواي» يجعل له كاتباً ثانياً. */
export const getMyProgress = () => api.get<MyProgress>("/drivers/me/progress");

/** يعيد رسمَ المسار من موضعه — **بسقفٍ تحرسه الخلفية** (البند ١٧-٤).
 *  و`reroutes_left` يقرؤها التطبيقُ فيكفّ عن الطلب: **راحةٌ لا حراسة**. */
export const rerouteRide = (rideId: string) =>
  api.post<{ points: number[][]; reroutes_left: number | null }>(
    `/rides/${rideId}/reroute`,
    {},
  );

/** «نقطة توقف» و«استئناف» — **بيد الكبتن وحدَه** (§5.10-ب، الفرع ب).
 *  وعدّادٌ توقفه الحركةُ يخطئ في الزحام، وعدّادٌ لا يُصدَّق لا يُحتجّ به. */
export const beginPause = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/pause`, {});

export const resumePause = (rideId: string) =>
  api.post<Ride>(`/rides/${rideId}/resume`, {});

/** رمزُ تسليمٍ إلى التطبيق الآخر — **قصيرُ العمر، أحاديُّ الاستعمال** (§23).
 *
 * ولا ينقل رمزَ التجديد: تدويرُه أحاديٌّ فحاملان يُبطل أحدُهما الآخر.
 */
export const startHandoff = () =>
  api.post<{ token: string; expires_in: number }>("/auth/handoff", {
    target: "rider",
  });

/** يبادل الرمزَ بجلسةٍ في هذا التطبيق — بلا كلمةِ مرورٍ ولا رمزِ تحقق. */
export const exchangeHandoff = (token: string) =>
  api.post<AuthResponse>(
    "/auth/handoff/exchange",
    { token, app: CLIENT_APP },
    { anonymous: true },
  );

// ------------------------------------- بدائلُ REST حين يسقط المقبس (SPEC §10)

/** **مسارُ الطوارئ حين لا مقبس** — يبقيه مرئياً للتوزيع.
 *
 * فتحُ المقبس هو مفتاحُ Online في الحال الطبيعية؛ وهذه الثلاثةُ لمن **فقد**
 * مقبسَه: كبتنٌ غيرُ مرئيٍّ لا تصله رحلة، فيخسر دخلَه، والراكبُ يخسر سيارة.
 * وكانت مبنيّةً في الخلفية ومختبَرةً **ولا ينادِيها أحد** — بابٌ بلا زرّ في
 * أخطر موضع.
 */
export const goOnlineOverRest = () =>
  api.post<Driver>("/drivers/me/online", {});

export const goOfflineOverRest = () =>
  api.post<Driver>("/drivers/me/offline", {});

/** بثُّ الموقع بلا مقبس — نفسُ ما يحمله إطارُ `location` حرفاً بحرف. */
/** رمزُ حضورٍ للخدمة الأمامية — **بابٌ واحدٌ لا جلسة** (§23.4).
 *
 * **ولا يُخزَّن في `localStorage`**: عمرُه عمرُ الاتصال، وتخزينُه يجعله يعيش
 * بعد فصلٍ أُلغي فيه — **قيمةٌ ميتةٌ تُقرأ حيّةً**.
 */
export const issuePresenceToken = () =>
  api.post<{ token: string; expires_in: number }>(
    "/drivers/me/presence-token",
    {},
  );

export const reportLocationOverRest = (payload: {
  lat: number;
  lng: number;
  heading: number | null;
}) => api.post<void>("/drivers/me/location", payload);

// ------------------------------------- مركباتُ الكراج والمتجر (2026-08-22)

/** المتجر — **مع الرصيد والعملة والمستوى في نداءٍ واحد**، فالبطاقةُ تعرف
 *  «رصيدك لا يكفي» بلا نداءٍ ثانٍ يفترق عنه. **والترتيبُ من الخلفية** ولا
 *  يُعاد ترتيبُه هنا. */
/** المتجرُ **صفحةً صفحة** — الكتالوجُ ثلاثُ مئةٍ وزيادة، وبطاقةٌ لكلٍّ تعني
 *  مئاتِ الصور في شاشةِ هاتف. و`total` في الرد يقول متى تنتهي. */
export const getSkinStore = (limit = 48, offset = 0) =>
  api.get<SkinStore>(`/vehicle-skins/store?limit=${limit}&offset=${offset}`);

/** الكراج — ومعه المفعَّلةُ والهديّةُ التي لم تُعرض بعدُ وحالُ الاشتراك. */
export const getGarage = () => api.get<Garage>("/vehicle-skins/garage");

/** الشراء — **والرصيدُ بعده يأتي من الدفتر** لا مطروحاً في الشاشة (§14). */
export const buySkin = (skinId: string) =>
  api.post<BuySkinResult>(`/vehicle-skins/${skinId}/buy`, {});

/** تبديلُ المركبة النشطة.
 *
 * **ولا يُقرأ ردُّه**: العقدُ يعلن مدخلَه (`ActivateSkinIn`) ولا يعلن مخرجَه،
 * فبناءُ الشاشة على شكلٍ لم يُجمَّد هو **الشكلُ الثامن قبل أن يُكتب سطر**.
 * فالكراجُ يُعاد قراءتُه بعده من بابه الواحد، والتبديلُ يظهر في الحال بتحديثٍ
 * متفائلٍ يعود عند الرفض.
 */
export const setActiveSkin = (skinId: string) =>
  api.put<void>("/vehicle-skins/active", { skin_id: skinId });

/** خَتْمُ ورقة الاحتفال — **مرةً واحدة**، فلا تُعرض الهديّةُ في كل فتحة. */
export const markSkinSeen = (skinId: string) =>
  api.post<void>(`/vehicle-skins/${skinId}/seen`, {});

/** زملاءُ الكبتن حوله — **مجهَّلين كما يراهم الراكب**.
 *
 * **ومطفأً يردّ ٤٠٣ بخطأٍ مسمّى لا قائمةً فارغة** (الخلفيةُ تفرّق: «البابُ
 * مغلق» ليست «الشارعُ خالٍ»). **والشاشةُ تصمت في الحالتين**: الميزةُ خلف
 * مفتاحها فلا تُرسم أصلاً، ولا يُعرض للكبتن خطأٌ عن بابٍ لم يطرقه.
 */
export const listNearbyColleagues = (lat: number, lng: number) =>
  api.get<NearbyDriver[]>("/drivers/me/nearby", { query: { lat, lng } });

/** بلاغُ الكبتن عن صورةِ راكبِ رحلته — **تُحجب فوراً وتُعرض على المشرف**.
 *
 * **ولا يبلّغ إلا كبتنُ الرحلة**: الرحلةُ هي التي أعطته حقَّ رؤيتها، فهي
 * التي تعطيه حقَّ البلاغ عنها — والخلفيةُ هي من يتحقّق.
 */
export const reportRiderPhoto = (rideId: string) =>
  api.post<void>(`/rides/${rideId}/rider/photo/report`, {});

/** عنوانُ بثِّ الموقع كما تطرقه **الخدمةُ الأمامية** — لا هذا التطبيق.
 *
 * الخدمةُ الأصليةُ تفتح الطلبَ بنفسها (خارج جافاسكربت)، فلا تمرّ بـ`api`.
 * **لكنّ المسارَ يبقى مُعلَناً هنا** كي يراه `check:contract`: كان يُبنى في
 * `lib/online-service.ts` بيده، **فيقفز فوق الحارس** — ولو تغيّر المسارُ في
 * الخلفية لَظلّت الخدمةُ تطرق عنواناً ميتاً **وكلُّ حارسٍ أخضر**.
 *
 * **وهو أخطرُ من مسارٍ في شاشة**: الشاشةُ تُفتح فيُرى عطبُها، **والخدمةُ تعمل
 * والشاشةُ مقفلة** — فيُقرأ صمتُها «لا طلبات اليوم».
 */
export const locationBroadcastUrl = () => `${API_URL}/drivers/me/location`;

// ------------------------------------------- دفعُ الاشتراك بكليك (يدويّ)
//
// **ولا يمرّ بالمحفظة**: مالُ الاشتراك لو مرّ بها لحمل رصيدُه لحظةً مالاً ليس
// أجراً فصار قابلاً للسحب. والبيتُ `provider_orders` بغرضٍ مُصرَّح.

/** يفتح مطالبةً بسعر العرض — **ولا اشتراكَ قبل تأكيد الدفع**. */
export const payySubscriptionWithCliq = (plan_id: string) =>
  api.post<CliqSubscriptionClaim>("/subscriptions/cliq", { plan_id });

/** مطالباتي وحالُها — **بانتظار التأكيد · مؤكَّد · مرفوض**. */
export const listMyCliqClaims = () =>
  api.get<CliqSubscriptionClaim[]>("/subscriptions/cliq");

// ── دَينُ الكبتن (الترحيلة `0061`) ──
export const getDebtState = () => api.get<DriverDebtState>("/drivers/me/debt");

export const payDebtWithCliq = (amount: string) =>
  api.post<DebtClaim>("/drivers/me/debt/cliq", { amount });

export const listMyDebtClaims = () =>
  api.get<DebtClaim[]>("/drivers/me/debt/cliq");


/** بلاطاتُ الشاشة الرئيسة ولافتاتُها — **نداءٌ واحدٌ لشاشةٍ واحدة**.
 *
 * **وندءان يعنيان شاشةً تُرسم على مرحلتين**: البلاطاتُ تظهر ثم تقفز اللافتةُ
 * فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.
 *
 * **و`surface` سياقُ الفعل لا دورُ الفاعل**: من يحمل الدورين يرى ما يخصّ
 * التطبيقَ الذي هو فيه.
 */
export const getStorefront = () =>
  api.get<Storefront>("/storefront", { query: { surface: "driver" } });


/** **«حوّلتُ»** — بابٌ واحدٌ للمطالبات اليدويّة كلِّها (قرارُ المالك 2026-09-01).
 *
 * **وضغطةٌ ثانيةٌ تُعيد الوقتَ الأوّل ولا تُنشئ طلباً ثانياً ولا تصيح**: من
 * ضغط ثانيةً لم يخطئ — الشبكةُ بطيئةٌ أو الشاشةُ لم تتحدّث.
 */
export const declareCliqPaid = (cartId: string) =>
  api.post<CliqDeclare>(`/payments/cliq/${cartId}/declare`);

// ------------------------------------------------- بوّابةُ التحديث (البند ٨)

/** ماذا يفعل التطبيقُ عند الإقلاع — **بابٌ عامٌّ بلا جلسة** (§43).
 *
 * **و`anonymous`ٌ بقصد**: يُسأل **قبل الدخول**، ومن حزمتُه دون الحدِّ لا يصل
 * شاشةَ الدخول أصلاً. **ولا يقرأ شيئاً عن شخص**: تطبيقٌ ورقمُ حزمة.
 *
 * **و`build` تُحذف حين لا تُعرف** — ولا يُقفل من لا نعرف نسختَه.
 */
export const getAppVersion = (
  app: "rider" | "driver" | "panel",
  build: number | null,
) =>
  api.get<AppVersion>("/public/app-version", {
    anonymous: true,
    query: build === null ? { app } : { app, build },
  });
