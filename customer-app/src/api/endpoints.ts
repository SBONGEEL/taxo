/** كل مسارات الخلفية التي يستعملها تطبيق الراكب — في ملف واحد.
 *
 * لا شاشة تكتب مساراً نصّاً: تغيّرُ مسارٍ في الخلفية يُصلَح هنا مرةً لا في
 * خمس شاشات. وما ليس للراكب ليس هنا (لا سحب، ولا اشتراكاتُ الكباتن، ولا لوحة إدارة) —
 * **واشتراكُ المشوار الثابت له** (§٦٣-ج/٦)، **وحجزُ مقاعد «بين المدن»** (§٦٣-ج/٧)، **وسلسلةُ الاسترداد الأسبوعي** (§٦٣-ج/٨).
 */

import { API_URL, ApiError, api, tokens, upload } from "@/api/client";
import type { UploadOptions } from "@/api/client";
import type {
  Airport,
  MapPlaceSpot,
  AppConfig,
  AppVersion,
  AuthMethod,
  AuthResponse,
  Booking,
  CallAnswer,
  CallStart,
  ChallengeResponse,
  ChatMessage,
  ChatReport,
  ChatReportReason,
  ChatThread,
  CliqTopup,
  Commute,
  CommutePlan,
  CommuteQuote,
  Coordinates,
  CountryCode,
  DeletionState,
  Device,
  ErrorReportBody,
  GenderPreference,
  HourlyPrepay,
  IntercityBooking,
  IntercityTrip,
  LoginResponse,
  MyReferrals,
  NearbyDriver,
  NotificationPreferences,
  OtpChannel,
  PaymentMethod,
  PlaceIcon,
  PromoPreview,
  PublicTrack,
  Rating,
  RatingTag,
  RecordedRoute,
  RequiredPolicy,
  Ride,
  RideDriverStats,
  RideEstimate,
  RideForOther,
  RideGroup,
  RideHourly,
  RideCall,
  RideListItem,
  RideParcel,
  RidePayments,
  RiderSummary,
  RiderUnconfirmed,
  SavedCard,
  SavedPlace,
  SiteHelp,
  Storefront,
  Tip,
  TipOptions,
  TopupRequest,
  TransferRecipient,
  User,
  UserNotification,
  VehicleCategory,
  Wallet,
  WalletTransaction,
  WeeklyCashback,
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

/** **ما يلزم قبولُه** لهذا التطبيق وهذا السوق (البند ١٠، §34).
 *
 * **وبلا مصادقة**: يُقرأ قبل أن يوجد حساب. **ولا يمرّ بمفتاح الموقع**
 * `policies_public` — ذاك «أتُعرض على الويب؟»، وهذا «ما الذي يوافق عليه
 * من يسجّل؟». */
export const requiredPolicies = (country_code: CountryCode) =>
  api.get<RequiredPolicy[]>(
    `/public/policies/required?country_code=${country_code}&app=rider`,
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
  /** **ما وافق عليه بعينه** — والخلفيةُ ترفض التسجيل إن نقص منها واحدة. */
  accepted_policy_ids?: string[];
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

/** **إنهاءُ كلِّ الجلسات** (SPEC §60-ب/١) — كلُّ أجهزة الحساب، وهذا منها. */
export const revokeAllSessions = () => api.post<void>("/auth/sessions/revoke-all");

// ------------------------------------------------------------ الرحلات

export const estimateRide = (payload: {
  pickup: Coordinates;
  dropoff: Coordinates;
  vehicle_category: VehicleCategory;
  /** محطاتٌ **وسيطة** بترتيبها — والوجهةُ الأخيرة تبقى `dropoff`. */
  stops?: { lat: number; lng: number; address?: string | null }[];
  /** **تقديرُ طرد** (§٦٣-ج/٤) — يضيف رسمَه إلى السعر ويعيد شروطَه (`parcel_fee` · `parcel_terms`). **ولا يُسمّى `parcel`**:
   *  حمولةُ الطلب ترث هذا المخطّطَ في الخلفية، و`parcel` فيها تفاصيلُ الطرد. */
  is_parcel?: boolean;
  /** **«أحضر غرضي»** (§٧٢-ج/١) — مع `is_parcel`: رسمُه هو ومفتاحُه هو. */
  parcel_fetch?: boolean;
  /** **تقديرُ ساعات** (§٦٣-ج/٥) — السعرُ «الساعات × سعرها» بلا نداء مسار، والوجهةُ نقطةُ الانطلاق إن لم تُختر. وغيابُه رحلةٌ
   *  عاديّة — **وسعرُ الساعة وكيلومتراتُها وسقفُها يصلان في كلِّ تقديرٍ على أيِّ حال**. */
  hourly_hours?: number;
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
  /** **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — غيابُه رحلةٌ يركبها صاحبُها. والخلفيةُ تفحص المفتاحَ **عند الإنشاء**، فرفضُه
   *  (`ride_for_other_unavailable`) يصل برسالته ولو أخفت الواجهةُ الخيار. */
  for_other?: RideForOther;
  /** **الطرد** (§٦٣-ج/٤) — غيابُه رحلةٌ عاديّة. **والخلفيةُ هي الحارس**: مفتاحٌ مطفأٌ أو رسمٌ صفرٌ ⇒ `parcel_unavailable` (٤٠٣)،
   *  وبلا إقرارٍ بالشروط أو بغير فئة الاقتصادي أو برقمٍ وعنوانٍ لا يصحّان ⇒ `invalid_input` — ويُقال نصُّها تحت الزرّ. */
  parcel?: RideParcel;
  /** **بالساعة** (§٦٣-ج/٥) — غيابُه رحلةٌ عاديّة. **والوجهةُ اختياريّة**: بلاها تُرسل نقطةُ الانطلاق نفسُها `dropoff`. ولا يُجمع
   *  مع «لشخص آخر» ولا الطرد ولا المحطات ولا المشاركة — والخلفيةُ ترفض الجمعَ `invalid_input` برسالته. */
  hourly?: RideHourly;
  /** **«انتظري، نوسّع البحث»** (§٦٤-ج/٤-٣) — للطلب النسائيّ وحدَه (وغيرُه ٤٢٢ بنصّه): دائرةٌ أوسع بين الكبتنات لدقائق أخرى، **وشرطُ
   *  الجنس هو هو**. وغيابُه بحثٌ عاديٌّ كما كان. */
  widen_search?: boolean;
  /** **طريقةُ الدفع المختارة في ورقة الطلب** (`design/PAYMENTS-UNCONFIRMED.md` §٢-١، SPEC §٦٤-ز) — كاش · كليك · محفظة · بطاقة،
   *  **تُرسل حيث `unconfirmed_payments_enabled` مشتعلٌ وحدَه** فلا يتغيّر طلبُ سوقٍ مطفأ. ورفضُها يصل برسالته: قناةٌ مطفأة
   *  (`feature_disabled`) · دافعٌ لا يطابقها (`payer_method_mismatch`) · **كاشٌ موقوفٌ لحسابه** (`cash_channel_off`). */
  payment_method?: PaymentMethod;
}) => api.post<Ride>("/rides", payload);

/** **«ادفع الساعاتِ نقداً بدل المحفظة» وعكسُه** (§٦٣-ج/٥) — قبل البدء وحدَه؛ وبعده ٤٠٩ برسالته. **والبابُ للراكب صاحب الرحلة**
 *  (غيرُه ٤٠٤)، ويعيد الرحلةَ بقيمتها الجديدة. */
export const changeHourlyPrepay = (rideId: string, prepay: HourlyPrepay) =>
  api.patch<Ride>(`/rides/${rideId}/hourly-prepay`, { prepay });

/** **رمزُ رابط التتبّع** لرحلةٍ يطلبها لغيره (§٦٣-ج/١) — **الرمزُ نفسُه في كلِّ ضغطة**، والتطبيقُ يبني الرابطَ من عنوانه هو
 *  (`lib/for-other.ts::trackUrl`)، فلا نطاقَ مكتوبٌ في الخلفية يفترق عن مكان التطبيق. */
export const createTrackLink = (rideId: string) =>
  api.post<{ token: string }>(`/rides/${rideId}/track-link`);

/** **ما يراه من يفتح الرابط** — بابٌ عامٌّ **بلا توكن** (`anonymous`): الرمزُ العشوائيُّ هو الإذنُ كلُّه، وزائرُ الصفحة
 *  لا حسابَ له أصلاً. ورمزٌ لا يُعرف ⇒ ٤٠٤. */
export const getPublicTrack = (token: string, signal?: AbortSignal) =>
  api.get<PublicTrack>(`/public/track/${encodeURIComponent(token)}`, { anonymous: true, signal });

// ------------------------------------------------------- الأماكن المحفوظة

/** **أماكنُ الخريطة لسوق الراكب** (SPEC §٧١-د) — فارغةٌ حين مفتاحُها مطفأ. */
export const mapPlaces = () => api.get<MapPlaceSpot[]>("/map-places");

/** **رأسُ نتائج البحث**: ما طابق من أماكن السوق، الأقربُ أوّلاً — ونتائجُ المزوّد تحتها. */
export const searchMapPlaces = (q: string, near?: { lat: number; lng: number }, signal?: AbortSignal) =>
  api.get<MapPlaceSpot[]>("/map-places/search", { query: { q, ...(near ?? {}) }, signal });

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

export const listMyRides = (limit = 20, offset = 0, group?: RideGroup) =>
  api.get<RideListItem[]>("/rides/me", { query: { limit, offset, side: "rider", group } });

/** بطاقةُ «حسابي» (R15) — **للراكب وحدَه**، والمتوسّطُ يُحسب في الخلفية (§٦١-ط/٢). */
export const getRiderSummary = () => api.get<RiderSummary>("/rides/me/summary");

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

export const rateRide = (rideId: string, stars: number, comment?: string, tags: RatingTag[] = []) =>
  api.post<Rating>(`/rides/${rideId}/ratings`, { stars, comment: comment || null, tags });

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

// --------------------------- المدفوعاتُ غيرُ المؤكَّدة (`design/PAYMENTS-UNCONFIRMED.md`، SPEC §٦٤-ز)

/** **«رحلةٌ لم يكتمل دفعها»** — ما يُعرض بعد الترحيب وقبل الرئيسية (§٦)، **الأقدمُ أوّلاً**. ومطفأً تعود فارغةً بلا منع. */
export const getMyUnconfirmed = () => api.get<RiderUnconfirmed>("/payments/me/unconfirmed");

/** **«سلّمتُ المبلغ للكبتن»** — إقرارُ الراكب على دفعة كاش، **بلا قيد** (المستلمُ هو الحَكَم في النقد). والضغطةُ الثانيةُ تعيد
 *  الحالَ نفسَها، **ويُقبل على النزاع** («سلّمتُه» — روايتُه للمشرف). */
export const declareHandover = (paymentId: string) =>
  api.post<RidePayments>(`/payments/${paymentId}/declare`);

/** **«غيّر طريقة الدفع» و«سأدفع الآن»** (§٢-١ و§٦) — **حملُ `POST /rides/{id}/payments` حرفاً**: يُلغى المعلَّقُ ويُفتح الجديدُ في
 *  معاملةٍ واحدة، **وسقوطُ الجديد يُبقي القديمَ كما كان**. والردُّ حالُ الرحلة كلِّها كردِّ الدفع (ومنه `card_order` برابطه). */
export const changePaymentMethod = (
  paymentId: string,
  method: PaymentMethod,
  idempotencyKey: string,
  extras: { save_card?: boolean; saved_card_id?: string } = {},
) =>
  api.post<RidePayments>(`/payments/${paymentId}/change-method`, {
    method,
    idempotency_key: idempotencyKey,
    ...extras,
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
  /** **مجموعةُ القنوات التي على الجهاز فعلاً** (§٦١-ل) — وغيابُها حزمةٌ أقدم. */
  push_channels?: number;
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
  /** **حجزٌ مضمون** (§٦٣-ج/٣) — رسمُه من المحفظة لحظةَ الحجز، **ويُرفض الحجزُ كلُّه** إن لم يكفِ الرصيد أو كان أقربَ
   *  من ساعتين. وغيابُه حجزٌ عاديٌّ كما كان. */
  guaranteed?: boolean;
}) => api.post<Booking>("/me/bookings", body);

export const cancelBooking = (bookingId: string) =>
  api.del<Booking>(`/me/bookings/${bookingId}`);

/** **«اطلبيها بأي كبتن»** (§٦٤-ج/٤-١) — لحجزٍ نسائيٍّ ينتظر اختيارَها (`awaiting_choice`). **يبدّل التفضيلَ تحت قفل الحجز ولا يُنشئ
 *  رحلة**: الدورةُ تطلبه خلال دقيقة (لا «نفّذ الآن» — رأسُ `routers/bookings.py`). ويعيد الحجزَ بحاله الجديدة. */
export const chooseAnyCaptain = (bookingId: string) =>
  api.post<Booking>(`/me/bookings/${bookingId}/any-captain`);

// --------------------------------------------- المشوارُ الثابت (§٦٣-ج/٦)

/** **التسعير** — السعرُ المجمَّدُ للرحلة وعددُها والمجموعُ ونسبةُ الخصم، **كلُّها من الخلفية**. ومطفأً أو بخصمٍ صفرٍ ٤٠٣
 *  `rider_subscription_unavailable`، وبلا يومٍ أو ببدءٍ ليس بعد اليوم ٤٢٢ بنصّه. */
export const quoteCommute = (plan: CommutePlan) => api.post<CommuteQuote>("/me/commutes/quote", plan);

/** **الشراء من المحفظة مقدّماً** — الحمولةُ نفسُها، والسعرُ يُعاد حسابُه هناك لا يُرسل. ورصيدٌ لا يغطّي ٤٠٩ `insufficient_balance`. */
export const buyCommute = (plan: CommutePlan) => api.post<Commute>("/me/commutes", plan);

/** **اشتراكاتي** — كلُّها بأحوالها، الأحدثُ بدءاً أوّلاً. **ويُقرأ ولو أُطفئت الخدمة**: مالُ القائم مدفوع. */
export const listMyCommutes = () => api.get<Commute[]>("/me/commutes");

/** **تعليقُ يومٍ قادمٍ من أيامه** — لا تُولَّد رحلتاه، **ويُرحَّل إلى ما بعد آخر يوم** (`ends_on` يمتدّ). وفوق الحدّ ٤٠٩ برسالته،
 *  ويومٌ ليس من أيامه ٤٢٢ برسالته. */
export const suspendCommuteDay = (commuteId: string, day: string) =>
  api.post<Commute>(`/me/commutes/${commuteId}/suspend`, { day });

/** **الإلغاء** — الحجوزُ القادمةُ تُلغى، **وكلُّ رحلةٍ لم تكتمل تعود بسعرها رصيداً في المحفظة لا نقداً**. */
export const cancelCommute = (commuteId: string) =>
  api.post<Commute>(`/me/commutes/${commuteId}/cancel`);

/** **«استبدل الكبتن»** — يُفكّ المعتمد فيعود المشوارُ مفتوحاً لغيره. */
export const releaseCommuteCaptain = (commuteId: string) =>
  api.del<Commute>(`/me/commutes/${commuteId}/captain`);

// --------------------------------------------- بين المدن (§٦٣-ج/٧)

/** **الرحلاتُ المفتوحةُ في سوقه** — القادمةُ وحدَها، الأقربُ انطلاقاً أوّلاً. **ومطفأً ٤٠٣ `intercity_unavailable`** بنصّه: الخدمةُ
 *  تنتظر قرارَ المالك بعد مراجعة القانون، فالشاشةُ لا تُفتح أصلاً حيث المفتاحُ مطفأ. */
export const listIntercityTrips = () => api.get<IntercityTrip[]>("/intercity/trips");

/** **الحجز** — المقاعدُ تُخصم من المحفظة لحظتَها (رصيدٌ لا يغطّي ٤٠٩ `insufficient_balance`)، **أو السيارةُ كاملةً نقداً للكبتن**
 *  حين لا مقعدَ محجوزٌ بعد. **والمبلغُ يُحسب هناك** ويعود في `amount` — لا يُرسل ولا يُضرب هنا. */
export const bookIntercity = (body: { trip_id: string; seats: number; whole_car: boolean }) =>
  api.post<IntercityBooking>("/intercity/bookings", body);

/** **حجوزاتي** — كلُّها بأحوالها، الأحدثُ أوّلاً. **ويُقرأ ولو أُطفئت الخدمة**: مالُ القائم محفوظ. */
export const listIntercityBookings = () => api.get<IntercityBooking[]>("/intercity/bookings");

/** **الإلغاءُ قبل الانطلاق يعيد المالَ كاملاً** إلى المحفظة (`intercity_refund`)؛ وبعده ٤٠٩ برسالته. */
export const cancelIntercityBooking = (bookingId: string) =>
  api.post<IntercityBooking>(`/intercity/bookings/${bookingId}/cancel`);

// --------------------------------------------- الاسترداد الأسبوعي (§٦٣-ج/٨)

/** **ما يُرسم بجانب النار** — الأيامُ الباقيةُ والمبلغُ المنتظَر وهل رُكب اليوم، **كلُّها من الخلفية بيوم السوق**. ومطفأً أو بمبلغٍ صفرٍ
 *  `{enabled: false}` لا خطأ — فلا نارَ تُرسم بلا وعد. */
export const getWeeklyCashback = () => api.get<WeeklyCashback>("/me/cashback");

/** **مطاراتُ سوق الراكب** (§٦٣-ج/٢) — اسمٌ ونقطةٌ داخل مضلّع كلٍّ منها، ومطفأُ المفتاح يعيد قائمةً فارغة. */
export const getAirports = () => api.get<Airport[]>("/airports");

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

/** **المسارُ الذي سارته الرحلة** — لتفاصيلها بعد أن تنتهي (R18، §٦٢-ج/١١). **لطرفَيها وحدهما**، وغيرُهما ٤٠٤.
 *  **وغيرُ `getRouteLine`**: ذاك ما قاله Mapbox قبل السير، وهذا ما سجّله بثُّ الكبتن أثناءه. */
export const getRecordedRoute = (rideId: string) =>
  api.get<RecordedRoute>(`/rides/${rideId}/route`);

/** **عددُ رحلات الكبتن المكتملة** لبطاقته في R08 (§٦٢-ج/٢٧) — **مفتاحُه الرحلةُ لا الكبتن**، ويُجيب ما دامت جارية. */
export const getRideDriverStats = (rideId: string) =>
  api.get<RideDriverStats>(`/rides/${rideId}/driver/stats`);

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

/** **«المساعدة والدعم»** (R30، §٦٢-ج/١٦): الأسئلةُ الشائعةُ وبريدُ الدعم **من إعدادات الموقع التي يديرها المشرف** —
 *  البابُ العامُّ نفسُه الذي تقرؤه الصفحةُ التعريفية (`GET /public/site`)، **فلا نسخةَ ثانيةً للمحتوى تفترق عنها**.
 *  و`anonymous` بقصد: البابُ بلا جلسة، ولا شيءَ فيه يخصّ شخصاً. */
export const getSiteHelp = () =>
  api.get<SiteHelp>("/public/site", { anonymous: true });

// ------------------------------------------- إغلاقُ الحساب (٢٠٢٦-٠٩-٠٧)
//
// **بابُ الكبتن نفسُه** — `‎/account/deactivation` — ولم يُبنَ ثانٍ بجانبه:
// **بابان يفعلان الشيءَ نفسَه يفترقان أوّلَ تعديل**، فيُصلَح مانعٌ في أحدهما
// ويُنسى في أخيه، **ويخرج راكبٌ من بابٍ لا يسأل ما يسأله بابُ الكبتن**.

/** حالُ الطلب وموانعُه — سؤالٌ واحدٌ بجوابٍ واحد. */

// **حذفُ الحساب بعد مهلة** (SPEC §59، قرارُ المالك ٢٠٢٦-٠٩-٢٩) — حلّ محلَّ
// «إغلاق الحساب» الذي كان طلباً يراجعه مشرف. **وبابٌ واحدٌ للدورين**.
export const getDeletionState = () => api.get<DeletionState>("/account/deletion");

/** `forfeitAmount` المبلغُ كما هو إن كان في محفظة الراكب رصيد — وإلا لا شيء. */
export const requestDeletion = (forfeitAmount?: string) =>
  api.post<DeletionState>(
    "/account/deletion",
    forfeitAmount ? { forfeit_amount: forfeitAmount } : {},
  );

/** **الاستعادةُ في المهلة** — فعلٌ صريحٌ بعد الدخول. */
export const restoreAccount = () => api.del<DeletionState>("/account/deletion");



// ------------------------------------------------- تقاريرُ الأعطال (2026-09-20)

/** **بلا جلسة بقصد**: الشاشةُ التي تسقط أكثرَ من غيرها هي شاشةُ الدخول. */
export const postErrorReport = (body: ErrorReportBody) =>
  api.post<{ accepted: boolean }>("/telemetry/errors", body, {
    anonymous: true,
  });

/** «تصل خلال 3 د» لكلِّ فئةٍ قبل الطلب (§٦٢-ج/١٠) — **`enabled: false` حيث المفتاحُ مطفأ** فلا يُرسم شيء، وفئةٌ بلا كبتنٍ متاحٍ غائبة. */
export interface NearestEta {
  enabled: boolean;
  categories: { vehicle_category: VehicleCategory; minutes: number }[];
}

export const getNearestEta = (point: Coordinates) =>
  api.get<NearestEta>("/rides/eta", { query: { lat: point.lat, lng: point.lng } });

/** مسارُ الاقتراب (§٦٢-ج/١٠) — لطرفَي الرحلة، `[[lng, lat]…]` ومدّتُه ومسافتُه؛ **والوقتُ المتبقّي يُحسب في الهاتف** (`lib/arrival`). */
export interface ApproachRoute {
  points: number[][];
  duration_min: number;
  distance_km: number;
}

export const getApproach = (rideId: string) => api.get<ApproachRoute>(`/rides/${rideId}/approach`);

/** **رمزُ الرحلة لصاحبتها** (§٦٢-ج/٥، RW4) — تطلبه منها الكبتنةُ قبل أن تركب؛ و٤٠٤ لرحلةٍ بلا رمزٍ أو بدأت. */
export const getStartCode = (rideId: string) => api.get<{ code: string }>(`/rides/${rideId}/start-code`);

// ------------------------------------------------- محادثةُ الرحلة ومكالمتُها (SPEC §٦٦)
//
// **المساراتُ نفسُها للراكب وللكبتن** — الخلفيةُ تقرأ أيَّ طرفٍ أنا من الرحلة لا من الدور. **والنسخةُ نفسُها في تطبيق الكبتن**.

/** **فتحُ المحادثة** — ويعلّم رسائلَ الطرف الآخر مقروءةً ويُخبره («قُرئت»)، **فلا يُطلب إلا والورقةُ مفتوحة**: طلبُه لرسم زرٍّ
 *  كان سيُري الطرفَ الآخر «قُرئت» عن رسالةٍ لم يرها أحد. */
export const getTripChat = (rideId: string) => api.get<ChatThread>(`/rides/${rideId}/chat`);

/** رسالةٌ — ورفضُها (`chat_closed` · `chat_phone_number` · `chat_link`) بنصّ الخادم العربيّ. */
export const sendTripChat = (rideId: string, body: string) =>
  api.post<ChatMessage>(`/rides/${rideId}/chat`, { body });

/** «أبلغ» على رسالة الطرف الآخر — والضغطةُ الثانيةُ تعيد البلاغَ نفسَه. */
export const reportTripChat = (rideId: string, messageId: string, reason: ChatReportReason, note: string | null) =>
  api.post<ChatReport>(`/rides/${rideId}/chat/${messageId}/report`, { reason, note });

/** **اتصل** — في نافذة الرحلة وحدَها؛ وبياناتُ المُرحِّل لي أنا، مؤقّتة. */
export const startRideCall = (rideId: string) => api.post<CallStart>(`/rides/${rideId}/calls`);

/** حالُ مكالمةٍ — **لنقرةِ إشعارٍ**: أترنّ بعدُ أم فاتت؟ */
export const getRideCall = (callId: string) => api.get<RideCall>(`/calls/${callId}`);

/** «ردّ» — **وفي المسجَّلة بإقرارٍ بالتنبيه** الذي رآه على شاشة الوارد. */
export const answerRideCall = (callId: string, recordingNoticeAck: boolean) =>
  api.post<CallAnswer>(`/calls/${callId}/answer`, { recording_notice_ack: recordingNoticeAck });

export const declineRideCall = (callId: string) => api.post<RideCall>(`/calls/${callId}/decline`);

export const endRideCall = (callId: string) => api.post<RideCall>(`/calls/${callId}/end`);

/** **إشارةُ WebRTC إلى الطرف الآخر** — عرضٌ أو جوابٌ أو مرشّح؛ والخادمُ يمرّرها ولا يقرؤها. */
export const signalRideCall = (callId: string, kind: "offer" | "answer" | "ice", payload: Record<string, unknown>) =>
  api.post<void>(`/calls/${callId}/signal`, { kind, payload });

/** **المتصلُ أقرّ بأن المكالمةَ مسجَّلة** — وبغيره لا يمرّر الخادمُ عرضَه. */
export const ackRecordingNotice = (callId: string) => api.post<RideCall>(`/calls/${callId}/recording-notice`);

/** **التسجيلُ يُرفع من جهاز المتصل بعد المكالمة** (webm أو ogg) — لمكالمةٍ أُعلنت مسجَّلةً وحدَها، ومرّةً واحدة.
 *
 *  **و`fetch` بـ`POST` لا `upload`**: عميلُ الرفع يفتح بـ`PUT` (رفعُ الوثائق والصور)، والبابُ هنا `POST` — **وفعلٌ خاطئٌ على
 *  مسارٍ صحيح هو بعينه ما أنشأ `check:contract`**. والملفُّ يُبنى في الذاكرة بعد المكالمة، فلا نسبةَ تقدّمٍ يحتاجها أحد. */
export async function uploadCallRecording(callId: string, recording: Blob): Promise<RideCall> {
  const form = new FormData();
  form.append("file", recording, recording.type.includes("ogg") ? "call.ogg" : "call.webm");
  const answer = await fetch(`${API_URL}/calls/${callId}/recording`, {
    method: "POST",
    headers: { Authorization: `Bearer ${tokens.access() ?? ""}` },
    body: form,
  });
  const body = (await answer.json().catch(() => ({}))) as Record<string, unknown>;
  if (!answer.ok) {
    throw new ApiError(
      answer.status,
      String(body.code ?? "http_error"),
      String(body.message ?? "تعذّر رفع التسجيل"),
      undefined,
      body,
    );
  }
  return body as unknown as RideCall;
}
