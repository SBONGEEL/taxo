/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import { API_URL, api, tokens, upload } from "@/api/client";
import type { UploadOptions } from "@/api/client";
import type {
  AdminSkin,
  BundledSkinAsset,
  SkinArtworkPreview,
  SkinPurchases,
  WalletOwnerType,
  SkinStats,
  MapSetting,
  PhotoReport,
  AdminAccount,
  AdminDriverRow,
  AdminPermissions,
  AdminReferralRow,
  AdminRideDetail,
  AdminRideRow,
  AdvanceRow,
  AdvanceSetting,
  AppConfig,
  AppRelease,
  AppVersion,
  ClientApp,
  OrgProfile,
  PolicyApp,
  PolicyDocType,
  PolicyVersion,
  AuditAction,
  AuditLog,
  AuthResponse,
  BackupRow,
  BackupSettings,
  BackupState,
  Badge,
  CancellationPlan,
  Campaign,
  CampaignAudience,
  CancellationChargeRow,
  CancellationChargeStatus,
  CancellationSetting,
  CommissionAppliesTo,
  CommissionSetting,
  CountryCode,
  CountryFeatureFlags,
  CountryRow,
  DeactivationRequestRow,
  Delivery,
  DisputeResolution,
  DriverDocument,
  DriverDocuments,
  DriverLiveRide,
  DriverStatus,
  FeatureKey,
  Gender,
  LevelOverview,
  LevelSetting,
  LiveMap,
  LoginResponse,
  Mission,
  NotificationSetting,
  OfferGrant,
  OtpExhausted,
  OtpSetting,
  OtpTemplate,
  OtpTemplates,
  Overview,
  Payment,
  PaymentMethod,
  PaymentSetting,
  PaymentStatus,
  PricingRule,
  PromoCode,
  ProviderCatalog,
  ProviderCredential,
  ProviderKey,
  ProviderTestResult,
  ReferralSetting,
  ReferralSummary,
  Reports,
  RideSharingSetting,
  RideStatus,
  SearchHits,
  SecurityPolicy,
  StatsPeriod,
  Subscription,
  SubscriptionDurationType,
  SubscriptionOffer,
  SubscriptionPlan,
  SubscriptionStatus,
  TopupRequest,
  TopupStatus,
  TotpConfirmation,
  TotpEnrollment,
  TotpStatus,
  User,
  UserRole,
  Vehicle,
  VehicleCategory,
  Wallet,
  WalletSetting,
  WalletTransaction,
  WhatsAppSession,
  Withdrawal,
  WithdrawalStatus,
  CliqClaim,
  DebtClaimRow,
  DispatchSetting,
  DriverDebtRow,
  PromoBannerRow,
  ServiceTileRow,
  VerificationCampaignRow,
  SiteSettings,
  SiteUpdate,
} from "@/api/types";

// ------------------------------------------------------ الكوبونات (12-ز)

// ------------------------------------------- عروضُ الاشتراكات (البند ٥٤)

export const listSubscriptionOffers = (country: CountryCode) =>
  api.get<SubscriptionOffer[]>("/admin/subscription-offers", {
    query: { country_code: country },
  });

export const createSubscriptionOffer = (
  country: CountryCode,
  payload: {
    name: string;
    discount_value: string;
    max_discount?: string | null;
    audience: SubscriptionOffer["audience"];
    lapsed_days?: number | null;
    max_uses_per_driver: number;
    commission_percent?: string | null;
    total_budget?: string | null;
    ends_at?: string | null;
    /** الخطّةُ التي يغطّيها — **وهي مدّةُ العرض**. و`null` تعني كلَّ الخطط. */
    plan_id?: string | null;
  },
) =>
  api.post<SubscriptionOffer>("/admin/subscription-offers", payload, {
    query: { country_code: country },
  });

/** تعديلٌ جزئي — **والإطفاءُ منه** (`is_active: false`) لا حذف. */
export const updateSubscriptionOffer = (
  offerId: string,
  payload: Partial<{
    name: string;
    discount_value: string;
    max_discount: string | null;
    max_uses_per_driver: number;
    commission_percent?: string | null;
    total_budget: string | null;
    ends_at: string | null;
    /** **مدّةُ العرض تُبدَّل** — كانت في الإنشاء وحدَها فلا تتغيّر أبداً. */
    plan_id: string | null;
    is_active: boolean;
  }>,
) =>
  api.patch<SubscriptionOffer>(
    `/admin/subscription-offers/${offerId}`,
    payload,
  );

export const listOfferGrants = (offerId: string) =>
  api.get<OfferGrant[]>(`/admin/subscription-offers/${offerId}/grants`);

/** حذفُ عرضٍ **لم يُستعمل** (§39٫٤) — و`RESTRICT` في القاعدة يمنعه أصلاً،
 *  لكنّ الخادمَ يجيب بالعربية ويقول كم اشتراكاً استعمله. */
export const deleteOffer = (offerId: string) =>
  api.del<void>(`/admin/subscription-offers/${offerId}`);

export const grantSubscriptionOffer = (
  offerId: string,
  payload: { driver_id: string; note?: string | null },
) =>
  api.post<OfferGrant>(
    `/admin/subscription-offers/${offerId}/grants`,
    payload,
  );

export const listPromoCodes = (country?: CountryCode) =>
  api.get<PromoCode[]>("/admin/promo-codes", { query: { country_code: country } });

export const createPromoCode = (payload: {
  code: string;
  country_code: CountryCode;
  discount_type: "percent" | "fixed";
  discount_value: string;
  max_discount?: string | null;
  budget_total: string;
  per_user_limit?: number;
  total_usage_limit?: number | null;
  valid_from?: string | null;
  valid_until?: string | null;
}) => api.post<PromoCode>("/admin/promo-codes", payload);

/** **ولا `code` فيه**: رحلاتٌ تشير إليه بمعرّفه، وتغييرُ نصِّه يجعل ملصقاً في
 *  الشارع يشير إلى عرضٍ آخر. والرمزُ الخاطئ يُطفأ ويُنشأ غيرُه. */
export const updatePromoCode = (
  id: string,
  payload: { is_active?: boolean; budget_total?: string },
) => api.patch<PromoCode>(`/admin/promo-codes/${id}`, payload);

export const deletePromoCode = (id: string) =>
  api.del<void>(`/admin/promo-codes/${id}`);

// ------------------------------------------------------------ الإعدادات

export const getConfig = () =>
  api.get<AppConfig>("/config", { anonymous: true });

// ------------------------------------------------------------ المصادقة

/** الدخول برقم الهاتف وكلمة المرور — **لا بريد**.
 *
 * النموذج يكتب «استخدم بريد العمل الخاص بك»، والهوية في هذا النظام رقمُ
 * هاتفٍ بصيغة E.164 لكل الأدوار (`DESIGN-DECISIONS.md` بند 3).
 */
/** **التطبيقُ يُعلن نفسَه في كل بابٍ يُصدر جلسة** (`core/app_scope.py`).
 *
 * قرارُ المالك 2026-08-15: كلُّ تطبيقٍ لدوره وحدَه، و`admin`/`support` لا
 * يدخلان تطبيقَي الراكب والكبتن. والرفضُ في الخلفية — وهذا الحقلُ هو ما
 * يجعلها تعرف من يسأل. **ودعوى تضييقٍ لا توسيع**: من ادّعى تطبيقاً ليس دورَه
 * مَنَع نفسَه ولم ينل شيئاً.
 */
export const CLIENT_APP = "panel";

/** دخولُ اللوحة — **باسمِ مستخدمٍ أو برقم**، وأحدُهما لا كلاهما.
 *
 * **والخلفيةُ تقبل الاثنين منذ `e2cbd7b`** (`bool(phone) == bool(username)` —
 * أحدُهما مطلوب)، **واللوحةُ كانت ترسل الرقمَ وحدَه**. وثمنُ ذلك مقيسٌ لا
 * مفترض: `scripts/bootstrap_admins.py` يُنشئ حسابَي الإنتاج بـ`phone=None`،
 * فالحسابان اللذان يُدار بهما النظامُ **لم يكن لهما حقلٌ يُكتبان فيه**.
 * بابٌ في الخلفية بلا زرٍّ في الشاشة — وهو شكلُ هذا المشروع المتكرّر، مقلوباً.
 */
export const login = (
  identity: { username: string } | { phone: string },
  password: string,
  country?: CountryCode,
) =>
  api.post<LoginResponse>(
    "/auth/login",
    { ...identity, password, country_code: country, app: CLIENT_APP },
    { anonymous: true },
  );

/** الخطوةُ الثانية — وهنا وحدها تُصدر التوكنات (SPEC §14.1، المرحلة 12-د).
 *
 * `code` رمزُ اللحظة و`recovery_code` رمزُ الاسترداد، وأحدُهما لا كلاهما: من
 * فقد هاتفه لا يملك الأول، والرموزُ وُجدت لهذه اللحظة بعينها.
 */
export const loginWithTotp = (
  challenge_token: string,
  proof: { code?: string; recovery_code?: string },
) =>
  api.post<AuthResponse>(
    "/auth/login/totp",
    { challenge_token, ...proof, app: CLIENT_APP },
    { anonymous: true },
  );

export const getMe = () => api.get<User>("/auth/me");

// ------------------------------------------------------------ الأجهزة
//
// **بابان قائمان منذ المرحلة 9-ب** — لا جديدَ في الخلفية: `PUT /me/devices`
// و`DELETE /me/devices/{id}` يخدمان أيَّ صاحبِ جلسة، والمشرفُ صاحبُ جلسة.
// **وغلافُ المشرف هو ما كان ناقصاً** — والباب بلا زرٍّ منذ ذلك اليوم.

export const registerDevice = (payload: {
  device_id: string;
  token: string;
  platform: string;
}) => api.put<void>("/me/devices", payload);

export const unregisterDevice = (deviceId: string) =>
  api.del<void>(`/me/devices/${encodeURIComponent(deviceId)}`);

// ------------------------------------------- التحقق الثنائي (المرحلة 12-د)

export const getMyTotp = () => api.get<TotpStatus>("/auth/me/totp");

export const enrollTotp = () => api.post<TotpEnrollment>("/auth/me/totp/enroll");

export const confirmTotp = (code: string) =>
  api.post<TotpConfirmation>("/auth/me/totp/confirm", { code });

export const verifyRecoveryCode = (recovery_code: string) =>
  api.post<TotpStatus>("/auth/me/totp/recovery/verify", { recovery_code });

export const disableTotp = (proof: { password: string; code?: string; recovery_code?: string }) =>
  api.del<void>("/auth/me/totp", { body: proof });

export const getSecurityPolicy = () => api.get<SecurityPolicy>("/admin/security");

export const updateSecurityPolicy = (body: {
  admin_totp_required?: boolean;
  admin_idle_timeout_minutes?: number;
}) => api.put<SecurityPolicy>("/admin/security", body);

export const logout = (refreshToken: string) =>
  api.post<void>("/auth/logout", { refresh_token: refreshToken });

// ------------------------------------------------------------ الحملات

export const listCampaigns = (status?: string, q?: string) =>
  api.get<Campaign[]>("/admin/campaigns", { query: { status, q } });

export const createCampaign = (payload: {
  title: string;
  body: string;
  audience: CampaignAudience;
  country_code?: CountryCode | null;
  scheduled_at?: string | null;
}) => api.post<Campaign>("/admin/campaigns", payload);

export const updateCampaign = (
  id: string,
  payload: Partial<{
    title: string;
    body: string;
    audience: CampaignAudience;
    country_code: CountryCode | null;
    scheduled_at: string | null;
  }>,
) => api.patch<Campaign>(`/admin/campaigns/${id}`, payload);

export const cancelCampaign = (id: string) =>
  api.post<Campaign>(`/admin/campaigns/${id}/cancel`);

/** سجلُّ من وصله ومن تُخطّي — **وهو ما يجعل احترام الإطفاء مُثبَتاً**. */
export const listDeliveries = (id: string, limit = 50, offset = 0) =>
  api.get<Delivery[]>(`/admin/campaigns/${id}/deliveries`, {
    query: { limit, offset },
  });

// ------------------------------------------------------ ساعات الهدوء

export const getQuietHours = (country: CountryCode) =>
  api.get<NotificationSetting>(`/admin/campaigns/settings/${country}`);

export const setQuietHours = (
  country: CountryCode,
  payload: {
    quiet_hours_start: string;
    quiet_hours_end: string;
    timezone: string;
  },
) =>
  api.put<NotificationSetting>(`/admin/campaigns/settings/${country}`, payload);

// -------------------------------------------------- البحثُ العامُّ في الرأس

/** بحثٌ واحدٌ يجمع أربعةَ أصناف — **ويقفز، ولا يفتح صفحةَ نتائج** (§39٫١٢٫٤).
 *
 * **والحدُّ خمسةٌ لكلِّ صنفٍ في الخلفية لا هنا**: قصُّ القائمة في المتصفح
 * يعني أنها حُمِّلت كلُّها أوّلاً.
 */
export const globalSearch = (q: string) =>
  api.get<SearchHits>("/admin/search", { query: { q } });

// ------------------------------------------------------------ الكباتن

export const listDrivers = (
  params: {
    status?: DriverStatus;
    country_code?: CountryCode;
    /** `false` هو **قائمةُ عملٍ** لا فلترةَ عرض: من يعمل بلا جنسٍ مثبت. */
    gender_verified?: boolean;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
) => api.get<AdminDriverRow[]>("/admin/drivers", { query: params });

/** مركباتُ الكبتن — **قسمُ المركبة في الملفِّ الشخصيّ** (§37).
 *
 * **ولم يكن للوحة بابٌ يقرأ مركبةَ كبتنٍ قبل اليوم**: `AdminDriverRow` لا
 * يحملها، **فكان المشرفُ يبتّ في «رخصة المركبة» ولا يرى لوحتَها ولا سنتَها**.
 */
export const listDriverVehicles = (driverId: string) =>
  api.get<Vehicle[]>(`/admin/drivers/${driverId}/vehicles`);

export const getDriverDocuments = (driverId: string) =>
  api.get<DriverDocuments>(`/admin/drivers/${driverId}/documents`);

/** قبولٌ أو رفضٌ **بسبب** — والسببُ يصل صاحبَه في الإشعار (القسم 13/2). */
export const reviewDocument = (
  driverId: string,
  documentId: string,
  approved: boolean,
  note?: string,
  /** تصحيحُ تاريخ الانتهاء — **يُرسَل حين يُعطى وحدَه** (البند ب): غيابُ الحقل
   *  يعني «لا تُغيّره»، وإرسالُه فارغاً يعني «امْحُه». */
  expiresOn?: string,
) =>
  api.post<DriverDocument>(
    `/admin/drivers/${driverId}/documents/${documentId}/review`,
    {
      approved,
      note: note ?? null,
      ...(expiresOn === undefined ? {} : { expires_on: expiresOn || null }),
    },
  );

export const approveDriver = (driverId: string) =>
  api.post<{ id: string; status: DriverStatus }>(
    `/admin/drivers/${driverId}/approve`,
  );

export const rejectDriver = (driverId: string) =>
  api.post<{ id: string; status: DriverStatus }>(
    `/admin/drivers/${driverId}/reject`,
  );

export const suspendDriver = (driverId: string, reason: string) =>
  api.post<{ id: string; status: DriverStatus }>(
    `/admin/drivers/${driverId}/suspend`,
    { reason },
  );

export const activateDriver = (driverId: string) =>
  api.post<{ id: string; status: DriverStatus }>(
    `/admin/drivers/${driverId}/activate`,
    {},
  );

/** يثبّت المشرفُ جنسَ الكبتن من هويته المرفوعة — `admin` حصراً، بقيدِ تدقيق.
 *
 * **والردُّ `DriverOut` لا يحمل الجنس** لأنه عمودٌ على `users` لا على
 * `drivers`؛ فالشاشة تعيد قراءة القائمة بعد الحفظ ولا تخمّن الحالة الجديدة
 * من ردٍّ لا تحملها. ولا يعيد هذا المسارُ دورةَ اعتماد: الهوية مراجَعةٌ
 * أصلاً، وإرجاعُ معتمدٍ إلى الطابور لأجل حقلٍ واحد يجعل تفريغ المتراكم
 * مستحيلاً — وهو المتراكم الذي يبقى `women_service_enabled` مطفأً حتى يُفرَّغ.
 */
export const setDriverGender = (driverId: string, gender: Gender) =>
  api.put<{ id: string; status: DriverStatus }>(
    `/admin/drivers/${driverId}/gender`,
    { gender },
  );

// ------------------------------------------------------------ المالية

export const listTopups = (status?: TopupStatus, q?: string) =>
  api.get<TopupRequest[]>("/admin/topups", { query: { status, q } });

/** **المبلغُ مبلغُ المشرف** — ما وصل الحسابَ فعلاً، لا ما ادّعاه المستخدم.
 *  و`undefined` تعني «بمبلغه كما هو» لمن طابق ما وصل. */
export const confirmTopup = (id: string, amount?: string) =>
  api.post<TopupRequest>(`/admin/topups/${id}/confirm`, {
    amount: amount ?? null,
  });

export const rejectTopup = (id: string, note?: string) =>
  api.post<TopupRequest>(`/admin/topups/${id}/reject`, { note: note ?? null });

export const listWithdrawals = (status?: WithdrawalStatus, q?: string) =>
  api.get<Withdrawal[]>("/admin/withdrawals", { query: { status, q } });

export const approveWithdrawal = (id: string) =>
  api.post<Withdrawal>(`/admin/withdrawals/${id}/approve`, {});

export const rejectWithdrawal = (id: string, note?: string) =>
  api.post<Withdrawal>(`/admin/withdrawals/${id}/reject`, {
    note: note ?? null,
  });

/** «حوّلتُ يدوياً» — يكتب المرجع ويقيّد السحب في الدفتر (`paid`). */
export const markWithdrawalPaid = (id: string, reference: string) =>
  api.post<Withdrawal>(`/admin/withdrawals/${id}/paid`, { reference });

// ------------------------------------------------------------ النزاعات

export const listPayments = (
  status?: PaymentStatus,
  country?: CountryCode,
  q?: string,
) =>
  api.get<Payment[]>("/admin/payments", {
    query: { status, country_code: country, q },
  });

/** فصلُ النزاع: `paid` وصل المال فتصير `confirmed`، و`unpaid` فتصير `failed`. */
export const resolveDispute = (
  paymentId: string,
  resolution: DisputeResolution,
  note?: string,
) =>
  api.post<Payment>(`/admin/payments/${paymentId}/resolve`, {
    resolution,
    note: note ?? null,
  });

// ------------------------------------------------------------ الإعدادات

export const listFeatureFlags = () =>
  api.get<CountryFeatureFlags[]>("/admin/settings/feature-flags");

/** `reason` إلزاميٌّ لإطفاء مفتاحٍ حارس — والخلفية ترفض بدونه. */
export const setFeatureFlag = (payload: {
  country_code: CountryCode;
  feature_key: FeatureKey;
  enabled: boolean;
  reason?: string;
}) => api.put<CountryFeatureFlags>("/admin/settings/feature-flags", payload);

export const listCommission = () =>
  api.get<CommissionSetting[]>("/admin/settings/commission");

export const updateCommission = (
  country: CountryCode,
  payload: Partial<{
    commission_enabled: boolean;
    commission_percent: string;
    applies_to: CommissionAppliesTo;
  }>,
) =>
  api.patch<CommissionSetting>(
    `/admin/settings/commission/${country}`,
    payload,
  );

export const listWalletSettings = () =>
  api.get<WalletSetting[]>("/admin/settings/wallet");

export const updateWalletSettings = (
  country: CountryCode,
  payload: Partial<{
    transfer_daily_limit: string;
    transfer_monthly_limit: string;
    min_withdrawal_amount: string;
    withdrawal_reserve_amount: string;
  }>,
) => api.patch<WalletSetting>(`/admin/settings/wallet/${country}`, payload);

export const listPaymentSettings = () =>
  api.get<PaymentSetting[]>("/admin/settings/payments");

/** سياساتُ الدفع — والحقولُ اختياريةٌ كلُّها فيُرسل ما تغيّر وحده (12-و). */
export const updatePaymentSettings = (
  country: CountryCode,
  payload: {
    cliq_confirmation_hours?: number;
    /** **الحساب المستقبِل** — وسلسلةٌ فارغةٌ تعني «انزعه» فتُخفى القناة. */
    cliq_alias?: string;
    /** **المدّة الموعودة** — تُحقن في جملة «خلال {min} إلى {max} دقائق». */
    cliq_review_min_minutes?: number;
    cliq_review_max_minutes?: number;
    driver_debt_ceiling?: string | null;
    tip_preset_small?: string;
    tip_preset_medium?: string;
    tip_max?: string;
  },
) => api.patch<PaymentSetting>(`/admin/settings/payments/${country}`, payload);

/** **صورةُ الباركود تُرفع ولا تُولَّد** — معيارُ كليك يحمل حقولاً لا تُشتقّ
 *  من الحساب، **وباركودٌ لا يعمل أسوأُ من غيابه**. */
export const uploadCliqQr = (country: CountryCode, file: File) =>
  // **و`upload` تُرسل `PUT` دائماً** — لا خيارَ `method` فيها (صُحِّح
  // 2026-08-30: كان مُمرَّراً ولا يقبله العقد، فسقط `tsc`)
  upload<PaymentSetting>(`/admin/settings/payments/${country}/cliq-qr`, file);

// ------------------------------------------------- إحالةُ السائقات (12-ح)

export const getReferralSettings = (country: CountryCode, type: string) =>
  api.get<ReferralSetting>(
    `/admin/referrals/settings?country_code=${country}&referral_type=${type}`,
  );

export const updateReferralSettings = (
  country: CountryCode,
  type: string,
  payload: {
    reward_amount?: string;
    required_rides?: number;
    female_bonus_amount?: string;
    monthly_cap?: number;
    clear_monthly_cap?: boolean;
  },
) =>
  api.put<ReferralSetting>(
    `/admin/referrals/settings?country_code=${country}&referral_type=${type}`,
    payload,
  );

// ------------------------------------------- مشاركةُ الرحلة (12-ي)

export const getSharingSettings = (country: CountryCode) =>
  api.get<RideSharingSetting>(`/admin/sharing/settings?country_code=${country}`);

export const updateSharingSettings = (
  country: CountryCode,
  payload: {
    discount_percent?: string;
    corridor_km?: string;
    max_detour_minutes?: number;
    partner_wait_seconds?: number;
  },
) =>
  api.put<RideSharingSetting>(
    `/admin/sharing/settings?country_code=${country}`,
    payload,
  );

export const getReferralSummary = (country: CountryCode) =>
  api.get<ReferralSummary>(`/admin/referrals/summary?country_code=${country}`);

/** جدولُ الإحالات — و**دولةُ المُحيلة** هي مقياسُ الفرز: مالُ المكافأة يخرج
 *  من ميزانية سوقه ويدخل محفظته بعملته. */
export const listReferrals = (
  country: CountryCode,
  rewarded?: boolean,
  q?: string,
) =>
  api.get<AdminReferralRow[]>("/admin/referrals", {
    query: { country_code: country, rewarded, q },
  });

// ------------------------------------------------------------ العقود

export const getProviderCatalog = () =>
  api.get<ProviderCatalog>("/admin/providers");

/** الحقلُ السرّي يعود مقنّعاً (`****`)؛ إعادتُه كما هو تُبقي المخزَّن. */
export const saveProviderCredential = (
  providerKey: ProviderKey,
  payload: {
    country_code?: CountryCode | null;
    values: Record<string, string | boolean | null>;
    is_active?: boolean;
  },
) => api.put<ProviderCredential>(`/admin/providers/${providerKey}`, payload);

/** اختبارٌ لا يترك أثراً — ويعود 200 حتى عند الفشل، فالسبب هو الفائدة. */
export const testProviderCredential = (id: string, testPhone?: string) =>
  api.post<ProviderTestResult>(`/admin/providers/${id}/test`, {
    test_phone: testPhone ?? null,
  });

export const activateProvider = (id: string) =>
  api.post<ProviderCredential>(`/admin/providers/${id}/activate`, {});

export const deactivateProvider = (id: string) =>
  api.post<ProviderCredential>(`/admin/providers/${id}/deactivate`, {});

// ------------------------------------------------------------ الإحصاءات

export const getOverview = (country: CountryCode, period: StatsPeriod) =>
  api.get<Overview>("/admin/stats/overview", {
    query: { country_code: country, period },
  });

// ------------------------------------------------------------ الخريطة الحيّة

/** لـ`admin` وحده، ويُسجَّل من فتحها (القسم 13/1) — والخلفية هي من يفرض ذلك. */
export const getLiveMap = (country: CountryCode) =>
  api.get<LiveMap>("/admin/live/map", { query: { country_code: country } });

/** رحلةُ الكبتن الجارية ومسارُها وموضعُه الحيّ — البند ٦ (§39٫٦).
 *
 * **`null` تعني لا رحلةَ جارية**، فيصمت القسمُ في ملفّه بدل خريطةٍ فارغة.
 * **والبابُ لـ`admin` وحدَه** كالخريطة الحيّة: كلاهما يقرن هويةً بموقع.
 */
export const getDriverLiveRide = (driverId: string) =>
  api.get<DriverLiveRide | null>(`/admin/live/drivers/${driverId}/ride`);

/** تقاريرُ الفترة (القسم 13/5) — نِسَبٌ ومتوسطاتٌ محسوبةٌ في الخلفية. */
export const getReports = (country: CountryCode, period: StatsPeriod) =>
  api.get<Reports>("/admin/stats/reports", {
    query: { country_code: country, period },
  });

// ------------------------------------------------------------ سجل الرحلات

export const listRides = (
  params: {
    country_code?: CountryCode;
    ride_status?: RideStatus;
    driver_id?: string;
    rider_id?: string;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
) => api.get<AdminRideRow[]>("/admin/rides", { query: params });

/** التفاصيلُ ومعها **المسار الفعلي** — دليلُ النزاع (القسم 5.7/13.4). */
export const getRide = (rideId: string) =>
  api.get<AdminRideDetail>(`/admin/rides/${rideId}`);

// ------------------------------------------------------------ الحسابات

export const listUsers = (
  params: {
    role?: UserRole;
    country_code?: CountryCode;
    phone_verified?: boolean;
    is_blocked?: boolean;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
) => api.get<User[]>("/admin/users", { query: params });

/** حسابٌ واحدٌ بحاله — **قسمُ «الحساب» في الملفِّ الشخصيّ** (§37).
 *
 * **وصفُّ الكبتن لا يحمله**: `AdminDriverRow` بلا `is_blocked` ولا بريدٍ ولا
 * أدوار، **فكان درجُ كبتنٍ موقوفِ الحساب لا يقول ذلك** — يُقرأ «معتمد»
 * ويُسأل لماذا لا تصله رحلات.
 */
export const getUser = (userId: string) =>
  api.get<User>(`/admin/users/${userId}`);

/** مصفوفةُ الصلاحيات — **تُقرأ من الحارس نفسِه** (§39٫٥). */
export const listAdminPermissions = () =>
  api.get<AdminPermissions[]>("/admin/permissions");

/** **استبدالٌ لا إضافة** — فالنزعُ ممكن، وثلاثةُ حرّاسٍ في الخلفية. */
export const setAdminPermissions = (userId: string, permissions: string[]) =>
  api.put<AdminPermissions>(`/admin/permissions/${userId}`, { permissions });

/** الحظرُ **بسببٍ إلزامي** يدخل سجل التدقيق ولا يصل صاحب الحساب. */
/** تعديلُ اسمِ حسابٍ وبريدِه من ملفّه — **البند ١١**.
 *
 * **وحقلان لا أكثر**: الهاتفُ مُعرِّفُ دخول، والسوقُ يُختم على كلِّ رحلة،
 * والأدوارُ والحظرُ والجنسُ لكلٍّ بابُه. **وكتابةُ بريدٍ تُسقط إثباتَه** —
 * فبريدٌ يكتبه مشرفٌ ويبقى مُثبَتاً بابُ استيلاءٍ على حساب.
 */
export const updateUserProfile = (
  userId: string,
  body: { name?: string; email?: string | null },
) => api.patch<User>(`/admin/users/${userId}`, body);

/** رسالةٌ فرديةٌ إلى صاحب حساب — **بمسار FCM القائم**، ونصُّها في التدقيق. */
export const notifyUser = (
  userId: string,
  body: { title: string; body: string },
) => api.post<void>(`/admin/users/${userId}/notify`, body);

export const blockUser = (userId: string, reason: string) =>
  api.post<User>(`/admin/users/${userId}/block`, { reason });

export const unblockUser = (userId: string, reason?: string) =>
  api.post<User>(`/admin/users/${userId}/unblock`, { reason: reason ?? null });

// ---------------------------------------------------- محفظةُ حسابٍ بعينه

/** **والجانبُ يُعلَن** (§46٫٦): حسابٌ يحمل الدورين يرتدّ
 *  `409 wallet_owner_undecided` بلا إعلان، **وتبقى البطاقةُ على دوّارةٍ
 *  أبداً**. و`undefined` تعني «لا إعلان» — وهو النداءُ القديمُ حرفاً. */
export const getWallet = (userId: string, wallet?: WalletOwnerType) =>
  api.get<Wallet>(`/admin/wallets/${userId}`, { query: { wallet } });

export const listWalletTransactions = (
  userId: string,
  limit = 20,
  wallet?: WalletOwnerType,
) =>
  api.get<WalletTransaction[]>(`/admin/wallets/${userId}/transactions`, {
    query: { limit, wallet },
  });

/** تجميدٌ يوقف حركة المحفظة **ويبقي صاحبها راكباً يدفع نقداً** (القسم 13/3).
 *
 * والسببُ اختياريٌّ في الخلفية، ويُرسل حين يكتبه المشرف: قيدُ تدقيقٍ يقول
 * «جُمّدت» بلا «لماذا» نصفُ قيد.
 *
 * **و`wallet` يقول أيَّ محفظةٍ تُجمَّد** (1-أ/6): التجميدُ صار صفةَ محفظةٍ لا
 * صفةَ حساب، فحاملُ الدورين تُجمَّد محفظتُه المشبوهةُ وحدَها. **وبلا هذا
 * المُعامِل يرتدّ البابُ ٤٠٩ لحاملِ الدورين** — فلا يستطيع مشرفُ المال تجميدَ
 * شيءٍ أصلاً، وهو بابٌ بلا زرّ. والسكوتُ كما كان لصاحب الدور الواحد.
 */
export const freezeWallet = (
  userId: string,
  reason?: string,
  wallet?: WalletOwnerType,
) =>
  api.post<Wallet>(
    `/admin/wallets/${userId}/freeze`,
    { reason: reason ?? null },
    { query: { wallet } },
  );

export const unfreezeWallet = (
  userId: string,
  reason?: string,
  wallet?: WalletOwnerType,
) =>
  api.post<Wallet>(
    `/admin/wallets/${userId}/unfreeze`,
    { reason: reason ?? null },
    { query: { wallet } },
  );

// ------------------------------------------------------ الاشتراكات والباقات

export const listSubscriptions = (
  params: {
    subscription_status?: SubscriptionStatus;
    driver_id?: string;
    country_code?: CountryCode;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
) => api.get<Subscription[]>("/admin/subscriptions", { query: params });

/** تسجيلُ اشتراكٍ **قُبض** كاشاً أو كليكاً — بعد وصول المال لا قبله. */
export const recordSubscription = (payload: {
  driver_id: string;
  plan_id: string;
  method: PaymentMethod;
  amount_paid?: string | null;
  reference?: string | null;
}) => api.post<Subscription>("/admin/subscriptions", payload);

/** **ما سيقع قبل أن يقع** (§38): عددُ ما سيُلغى وقيمةُ الردّ الكلّية.
 *
 * **يُقرأ قبل الضغط لا بعده** (شرطُ المالك) — والخلفيةُ تحسبه بالدالّة التي
 * ينفّذ بها الإلغاءُ نفسُه، فلا رقمَ معروضٌ يخالف ما يقع.
 */
export const previewSubscriptionCancellation = (subscriptionId: string) =>
  api.get<CancellationPlan>(
    `/admin/subscriptions/${subscriptionId}/cancellation-preview`,
  );

/** إلغاءُ تغطية الكبتن كلِّها وردُّ ما لم يُستعمل — **بسببٍ إلزاميّ** (§38).
 *
 * **ويُلغى كلُّ ما لم ينقضِ لا الصفُّ المضغوط وحدَه**: التجديدُ المبكر يكدّس
 * صفّاً يبدأ بعد الحالي، **وزرٌّ يُبقي اشتراكاً قادماً بعد الإلغاء يكذب**.
 */
export const cancelSubscription = (subscriptionId: string, reason: string) =>
  api.post<CancellationPlan>(
    `/admin/subscriptions/${subscriptionId}/cancel`,
    { reason },
  );

export const listPlans = () =>
  api.get<SubscriptionPlan[]>("/admin/settings/subscription-plans");

export const createPlan = (payload: {
  country_code: CountryCode;
  name: string;
  duration_type: SubscriptionDurationType;
  price: string;
  is_active: boolean;
}) =>
  api.post<SubscriptionPlan>("/admin/settings/subscription-plans", payload);

export const updatePlan = (
  id: string,
  payload: Partial<{
    name: string;
    duration_type: SubscriptionDurationType;
    price: string;
    is_active: boolean;
  }>,
) =>
  api.patch<SubscriptionPlan>(
    `/admin/settings/subscription-plans/${id}`,
    payload,
  );

export const deletePlan = (id: string) =>
  api.del<void>(`/admin/settings/subscription-plans/${id}`);

// ------------------------------------------------------------ التسعيرة

export const listPricing = (country?: CountryCode) =>
  api.get<PricingRule[]>("/admin/settings/pricing", {
    query: { country_code: country },
  });

export const createPricing = (payload: {
  country_code: CountryCode;
  vehicle_category: VehicleCategory;
  base_fare: string;
  price_per_km: string;
  price_per_min: string;
  minimum_fare: string;
  cancellation_fee: string;
  stop_fee: string;
  stop_free_minutes: number;
  stop_price_per_min: string;
  stop_max_wait_minutes: number;
}) => api.post<PricingRule>("/admin/settings/pricing", payload);

export const updatePricing = (
  id: string,
  payload: Partial<{
    base_fare: string;
    price_per_km: string;
    price_per_min: string;
    minimum_fare: string;
    cancellation_fee: string;
    stop_fee: string;
    stop_free_minutes: number;
    stop_price_per_min: string;
    stop_max_wait_minutes: number;
  }>,
) => api.patch<PricingRule>(`/admin/settings/pricing/${id}`, payload);

export const deletePricing = (id: string) =>
  api.del<void>(`/admin/settings/pricing/${id}`);

// ------------------------------------------------------------ سجل التدقيق

export const listAuditLogs = (
  params: {
    entity_type?: string;
    action?: AuditAction;
    actor_id?: string;
    entity_id?: string;
    q?: string;
    limit?: number;
    offset?: number;
  } = {},
) => api.get<AuditLog[]>("/admin/settings/audit-logs", { query: params });

/** طلباتُ إلغاء التفعيل — والمعلّقةُ أولاً بحكم ترتيب الخلفية (البند ١٣). */
export const listDeactivations = (status?: string) =>
  api.get<DeactivationRequestRow[]>(
    "/admin/deactivations" + (status ? `?status=${status}` : ""),
  );

export const decideDeactivation = (
  id: string,
  payload: { approved: boolean; note?: string },
) => api.patch<DeactivationRequestRow>(`/admin/deactivations/${id}`, payload);

// ------------------------------------------------------ السلف (البند ١٥)

/** سياسةُ السلف لكل دولة — والقائمةُ لأن الجدولَ صغيرٌ ودولتان لا أكثر. */
export const listAdvanceSettings = () =>
  api.get<AdvanceSetting[]>("/admin/settings/advances");

export const updateAdvanceSettings = (
  country: CountryCode,
  payload: Partial<Omit<AdvanceSetting, "country_code">>,
) => api.patch<AdvanceSetting>(`/admin/settings/advances/${country}`, payload);

/** جلسةُ بوابة واتساب الذاتية — الحالُ ورمزُ الربط في نداءٍ واحد. */
export const getWhatsAppSession = () =>
  api.get<WhatsAppSession>("/admin/providers/whatsapp/session");

/** فصلٌ ومحوٌ لربط رقمٍ آخر — **يوقف الإرسالَ حتى يُمسح رمزٌ جديد**. */
export const logoutWhatsAppSession = () =>
  api.post<WhatsAppSession>("/admin/providers/whatsapp/session/logout");

/** سقوفُ طلب رمز التحقق — **لكل القنوات لا لواتساب وحدها**. */
export const listOtpSettings = () =>
  api.get<OtpSetting[]>("/admin/settings/otp");

export const updateOtpSettings = (
  country: CountryCode,
  payload: Partial<Omit<OtpSetting, "country_code">>,
) => api.patch<OtpSetting>(`/admin/settings/otp/${country}`, payload);

/** من استنفد اليوم — قائمةٌ تُقرأ ولا يُبنى عليها منع. */
export const listOtpExhausted = () =>
  api.get<OtpExhausted>("/admin/settings/otp/exhausted");

/** سياسةُ رسم الإلغاء (`design/CANCELLATION-FEE.md`). */
export const listCancellationSettings = () =>
  api.get<CancellationSetting[]>("/admin/settings/cancellation");

export const updateCancellationSettings = (
  country: CountryCode,
  payload: Partial<Omit<CancellationSetting, "country_code">>,
) =>
  api.patch<CancellationSetting>(
    `/admin/settings/cancellation/${country}`,
    payload,
  );

/** رسومُ الإلغاء بطرفَيها — والدولةُ تُقرأ من الرحلة لا من عمودٍ على الصف. */
export const listCancellationCharges = (
  country: CountryCode,
  status?: CancellationChargeStatus,
  q?: string,
  /** **رسومُ شخصٍ بعينه** — راكباً كان أو كبتناً (§37). والكبتنُ يُبلَغ عبر
   *  `drivers.user_id` في الخلفية، **لا بمقارنة معرِّف مستخدمٍ بـ`rides.driver_id`**
   *  الذي هو `drivers.id`. */
  userId?: string,
) =>
  api.get<CancellationChargeRow[]>("/admin/cancellation-charges", {
    query: { country_code: country, status, q, user_id: userId },
  });

/** الإعفاء — **بابُ الاعتراض بعد الحدث**، وسببُه مطلوبٌ لا اختياري. */
export const waiveCancellationCharge = (id: string, reason: string) =>
  api.post<CancellationChargeRow>(
    `/admin/cancellation-charges/${id}/waive`,
    { reason },
  );

/** الشطب (§10) — اعترافٌ بالخسارة باسم من قرّرها، ولا قيدَ له في الدفتر. */
export const writeOffCancellationCharge = (id: string, reason: string) =>
  api.post<CancellationChargeRow>(
    `/admin/cancellation-charges/${id}/write-off`,
    { reason },
  );

/** السلفُ بمتبقّيها — **مطروحاً في الخلفية** لا في المتصفح.
 *
 * **و`driver_id` مرشِّحٌ يقرأ به الملفُّ الشخصيُّ سلفَ صاحبه** (§37) — من
 * البابِ نفسِه لا من بابٍ يُبنى له، و**بمعرِّفٍ لا باسم** كي لا يخلط ملفٌّ
 * صفوفَ متشابهَي الاسم.
 */
export const listAdvances = (
  status?: string,
  q?: string,
  driverId?: string,
) =>
  api.get<AdvanceRow[]>("/admin/drivers/advances", {
    query: { status, q, driver_id: driverId },
  });

/** صرفٌ بموافقة مشرف — البابُ الوحيد لما يتجاوز سقفَ الكبتن. */
export const disburseAdvance = (payload: { driver_id: string; amount: string }) =>
  api.post<AdvanceRow>("/admin/drivers/advances", payload);

/** شطبُ دَينٍ بقرارٍ مسجَّل — والسببُ مطلوبٌ لا اختياري. */
export const writeOffAdvance = (id: string, reason: string) =>
  api.patch<AdvanceRow>(`/admin/drivers/advances/${id}/writeoff`, { reason });

/** سقفُ كبتنٍ بعينه — `null` لا تخصيص، وصفرٌ منعٌ من السلف. */
export const setAdvanceCap = (
  driverId: string,
  payload: { cap: string | null; reason: string },
) => api.put(`/admin/drivers/${driverId}/advance-cap`, payload);

// ------------------------------------------- المهامُّ والمستويات (البند ٥٣)

export const listMissions = (country: CountryCode, month?: string) =>
  api.get<Mission[]>(
    `/admin/missions?country_code=${country}${month ? `&month=${month}` : ""}`,
  );

export const createMission = (
  country: CountryCode,
  payload: {
    month: string;
    title: string;
    description?: string | null;
    metric: string;
    target: string;
  },
) => api.post<Mission>(`/admin/missions?country_code=${country}`, payload);

export const updateMission = (
  id: string,
  payload: { title?: string; target?: string; is_active?: boolean },
) => api.patch<Mission>(`/admin/missions/${id}`, payload);

export const getLevelOverview = (country: CountryCode) =>
  api.get<LevelOverview>(`/admin/levels?country_code=${country}`);

/** **والحدُّ ١٠٠م يحرسه ثلاثةٌ**: هذا النموذج، والخدمة، والقاعدة. */
export const setLevelEffect = (
  country: CountryCode,
  level: number,
  meters: number,
) =>
  api.put<LevelSetting>(`/admin/levels/${level}?country_code=${country}`, {
    discount_meters: meters,
  });

export const listBadges = () => api.get<Badge[]>("/admin/badges");

/** حذفُ شارةٍ **لم تُمنح لأحد** (§39٫٤) — والخادمُ يرفض ويقول العدد. */
export const deleteBadge = (badgeId: string) =>
  api.del<void>(`/admin/badges/${badgeId}`);

/** حذفُ مهمّةٍ **لم يبدأ شهرُها** (§39٫٤). */
export const deleteMission = (missionId: string) =>
  api.del<void>(`/admin/missions/${missionId}`);

export const createBadge = (payload: {
  key: string;
  label: string;
  description?: string | null;
}) => api.post<Badge>("/admin/badges", payload);

// ------------------------------------------- النسخُ الاحتياطي (خطةُ النسخ)

export const getBackupState = () => api.get<BackupState>("/admin/backups");

export const runBackupNow = () => api.post<BackupRow>("/admin/backups/run", {});

export const updateBackupSettings = (payload: Partial<BackupSettings>) =>
  api.put<BackupSettings>("/admin/backups/settings", payload);

/** **كلمةُ المرور تُعاد قبل توليد الرابط** — ملفٌ واحدٌ فيه كلُّ شيء. */
export const backupDownloadToken = (
  name: string,
  password: string,
  file: string,
) =>
  api.post<{ token: string; expires_in: number }>(
    `/admin/backups/${name}/download-token`,
    { password, file },
  );

/** قوالبُ رسالة الرمز — **بابٌ لكل غرض، فحفظُ أحدهما لا يمسّ الآخر**. */
export const listOtpTemplates = () =>
  api.get<OtpTemplates>("/admin/otp-templates");

export const saveOtpTemplate = (purpose: string, body: string) =>
  api.put<OtpTemplate>(`/admin/otp-templates/${purpose}`, { body });

/** الأسواقُ كلُّها بحالها — **ولا تُقرأ من `/config`** (SPEC §24).
 *
 * `/config` مصفّىً بمفتاح الظهور، فقراءةُ اللوحة منه تُخفي عنها ما جاءت
 * لتشعله. وهذا البابُ يعيد الظاهرَ والمخفيَّ ومعهما وصفُهما كاملاً.
 */
export const getCountries = () =>
  api.get<{ countries: CountryRow[] }>("/admin/countries");

/** **ردُّ دفعةٍ مرَّ مالُها بالمنصّة** — والكاشُ وكليك خارجَه: قبضهما الكبتنُ بيده.
 *
 * والسببُ إلزاميٌّ في الخلفية (٣ أحرف على الأقل) لأن الردَّ حركةُ مالٍ يقرّرها
 * إنسان: صفُّ تدقيقٍ يقول «رُدَّت» بلا «لماذا» نصفُ صفّ.
 */
export const refundPayment = (paymentId: string, reason: string) =>
  api.post<Payment>(`/admin/payments/${paymentId}/refund`, { reason });

/** **قيدُ تصحيحٍ في دفترٍ لا يُعدَّل ولا يُحذف منه** — موجبٌ أو سالب.
 *
 * وهو المخرجُ الوحيد: `wallet_transactions` عليها مُطلِقٌ يرفض التعديلَ والحذف
 * (هجرة `0006`)، فتصحيحُ خطأٍ سابقٍ **قيدٌ مضادٌّ لا محوٌ للتاريخ**.
 */
export const createWalletAdjustment = (
  userId: string,
  payload: { amount: string; reason: string; wallet?: WalletOwnerType },
) => api.post<WalletTransaction>(`/admin/wallets/${userId}/adjustments`, payload);

/** شحنٌ إداريٌّ من نقطةٍ معتمدة — يُنشأ ويُؤكَّد معاً، فالمالُ قُبض بيدٍ سلفاً. */
export const createStaffTopup = (
  userId: string,
  payload: { amount: string; reference: string },
) =>
  api.post<TopupRequest>(`/admin/wallets/${userId}/topups`, {
    method: "cash",
    ...payload,
  });

/** **صورةُ الوثيقة** — والمشرفُ كان يعتمد رخصةً لا يراها (قرارُ المالك 2026-08-19).
 *
 * ولا تُوضع في `<img src>` مباشرةً: المسارُ يتحقق من الدور بترويسة `Authorization`،
 * و`<img>` لا يحمل ترويسة. فتُجلب بالمفتاح ثم تُعرض من `blob:` — **ومن يفتحها
 * يغلقها** (`URL.revokeObjectURL`)، وإلا بقيت الوثائقُ في ذاكرة التبويب.
 *
 * والخلفيةُ ترد `private, no-store` و`nosniff`، فلا تُخزَّن في وسيطٍ ولا تُفسَّر
 * صفحةً — وهذا ما يجعل العرضَ مقبولاً أصلاً.
 */
export async function driverDocumentBlob(
  driverId: string,
  documentId: string,
): Promise<string> {
  const answer = await fetch(
    `${API_URL}/admin/drivers/${driverId}/documents/${documentId}/file`,
    { headers: { Authorization: `Bearer ${tokens.access() ?? ""}` } },
  );
  if (!answer.ok) throw new Error("تعذّر فتح الوثيقة");
  return URL.createObjectURL(await answer.blob());
}

// ------------------------------------------- حسابُ المشرف نفسِه (SPEC §25.9)

/** **بابُ صاحبِ الحساب لا بابُ إدارةٍ لغيره** — كلُّه يعمل على الجلسة الحالية. */
export const getAdminAccount = () =>
  api.get<AdminAccount>("/admin/account");

/** تغييرُ الاسم — **يُسجَّل في التدقيق بالقديم والجديد**. */
export const changeAdminUsername = (username: string) =>
  api.put<AdminAccount>("/admin/account/username", { username });

/** تغييرُ الكلمة — **بالحالية**، ويُبطل بقيةَ الجلسات لا هذه. */
export const changeAdminPassword = (payload: {
  current_password: string;
  new_password: string;
}) => api.put<void>("/admin/account/password", payload);


// ---------------------------------------------- بلاغاتُ صور الركاب (2026-08-22)

export const listPhotoReports = () =>
  api.get<PhotoReport[]>("/admin/photo-reports");

export const resolvePhotoReport = (reportId: string, remove: boolean) =>
  api.post<void>(`/admin/photo-reports/${reportId}/resolve`, undefined, {
    query: { remove },
  });


// ---------------------------------------------- حدودُ خريطة الراكب (2026-08-22)

export const listMapSettings = () =>
  api.get<MapSetting[]>("/admin/settings/map");

export const updateMapSettings = (
  country: CountryCode,
  payload: { nearby_radius_km?: number; nearby_max_count?: number },
) => api.patch<MapSetting>(`/admin/settings/map/${country}`, payload);


// ───────────────────────────────── مركباتُ الكراج والمتجر (2026-08-22)

/** حذفُ مركبةٍ **لا يملكها أحد** (§39٫٤) — ومنهم من دفع ثمنَها. */
export const deleteVehicleSkin = (skinId: string) =>
  api.del<void>(`/admin/vehicle-skins/${skinId}`);

export const listVehicleSkins = () =>
  api.get<AdminSkin[]>("/admin/vehicle-skins");

/** الرسوماتُ المشحونةُ مع الخلفية — **منتقٍ بدل رفعٍ يدويّ**. */
export const listSkinAssets = () =>
  api.get<BundledSkinAsset[]>("/admin/vehicle-skins/assets");

/** **مجموعٌ في الخلفية** (§14): جمعُ صفحةٍ مقصوصةٍ في المتصفح يُخرج رقماً
 *  عنوانُه «الإيرادُ الكلي» وقيمتُه «إيرادُ ما ظهر». */
export const getSkinStats = () =>
  api.get<SkinStats>("/admin/vehicle-skins/stats");

/** سجلُّ مشتريات المركبات — **مجاميعُه محسوبةٌ في الخلفية** ولا تُجمع هنا. */
export const listSkinPurchases = (params: {
  limit?: number;
  offset?: number;
  skin_id?: string;
  q?: string;
}) =>
  api.get<SkinPurchases>(
    `/admin/vehicle-skins/purchases?${new URLSearchParams(
      Object.entries(params).flatMap(([key, value]) =>
        value === undefined ? [] : [[key, String(value)]],
      ),
    ).toString()}`,
  );

export const createVehicleSkin = (payload: Record<string, unknown>) =>
  api.post<AdminSkin>("/admin/vehicle-skins", payload);

export const updateVehicleSkin = (
  skinId: string,
  payload: Record<string, unknown>,
) => api.patch<AdminSkin>(`/admin/vehicle-skins/${skinId}`, payload);

/** **تجربةٌ جافّةٌ بنفس السلسلة** — تُعالَج الرسمةُ ولا يُكتب صفٌّ ولا ملفّ.
 *
 * ولا تحتاج مُعرَّفَ مركبة، فتُعاين **قبل** أن تُنشأ.
 */
export const previewSkinArtwork = (file: File, options?: UploadOptions) =>
  upload<SkinArtworkPreview>(
    "/admin/vehicle-skins/artwork/preview",
    file,
    options,
  );

/** `PUT` لأن العمليةَ **إحلال** — والخانةُ صريحةٌ لأن للمركبة **شكلين**.
 *
 * **وهذا السطرُ كان يقول عكسَ ما يقول اليوم** (صُحّح 2026-08-23): كان مكتوباً
 * «للمركبة رسمةٌ واحدة لا رسمتان»، **وكان صحيحاً ثم صار خطأً** — قرارُ §28
 * جعل لكلِّ مركبةٍ مجسّماً للمتجر وعلويّةً للخريطة، والخلفيةُ نقلت البابَ إلى
 * `…/artwork/{slot}`. **وظلَّ النداءُ على المسار القديم فكان يردّ ٤٠٤** —
 * أمسكه `check:contract` وأوقف بناءَ اللوحة.
 *
 * **ونصفُ قرار المالك (أ) وحدَه هو المبنيُّ هنا**: النداءُ صار صحيحاً.
 * **ولم تُبنَ حالةُ «خانةٌ فارغة» صريحةً** — فمن رفع للمتجر تبقى علويّتُه
 * فارغةً بلا سطرٍ يقولها، وهو بندٌ مسجَّلٌ لا منجَز. */
export const uploadSkinArtwork = (
  skinId: string,
  slot: "store" | "map",
  file: File,
  options?: UploadOptions,
) =>
  upload<AdminSkin>(
    `/admin/vehicle-skins/${skinId}/artwork/${slot}`,
    file,
    options,
  );

export const attachSkinAsset = (skinId: string, assetKey: string) =>
  api.put<AdminSkin>(`/admin/vehicle-skins/${skinId}/asset/${assetKey}`);

/** رسمةُ المركبة — **بمفتاح الجلسة ثم `blob:`**، كصورةِ الوثيقة بالضبط.
 *
 * و`<img src>` لا يحمل ترويسةَ `Authorization`، والبابُ إداريٌّ يتحقّق من
 * الدور. **ومن يفتحها يغلقها** (`URL.revokeObjectURL`).
 */
export async function skinArtworkBlob(
  skinId: string,
  slot: "store" | "map",
): Promise<string> {
  const answer = await fetch(
    `${API_URL}/admin/vehicle-skins/${skinId}/artwork/${slot}`,
    { headers: { Authorization: `Bearer ${tokens.access() ?? ""}` } },
  );
  if (!answer.ok) throw new Error("تعذّر فتح رسمة المركبة");
  return URL.createObjectURL(await answer.blob());
}

/** صورةُ بلاغٍ عن راكب — **بابٌ مُعلَنٌ لا مسارٌ تكتبه شاشة** (2026-08-23).
 *
 * كان `PhotoReports.tsx` يبني `${API_URL}/admin/photo-reports/…` بيده ويطرقه
 * بـ`fetch` — **فيقفز فوق `check:contract`**: الحارسُ يقرأ `api.*` و`upload`،
 * ومن كتب مسارَه بيده لا يراه. **والحارسُ يحرس البابَ ولا يرى من قفز السور.**
 *
 * و`<img src>` لا يحمل `Authorization` والبابُ إداريّ، فالجلبُ إلى `blob`
 * ضرورةٌ لا اختيار — **وموضعُها هنا لا في شاشة**. **ومن يفتحها يغلقها.**
 */
export async function photoReportBlob(reportId: string): Promise<string> {
  const answer = await fetch(`${API_URL}/admin/photo-reports/${reportId}/photo`, {
    headers: { Authorization: `Bearer ${tokens.access() ?? ""}` },
  });
  if (!answer.ok) throw new Error("تعذّر فتح الصورة المُبلَّغ عنها");
  return URL.createObjectURL(await answer.blob());
}

/** عنوانُ تنزيل نسخةٍ احتياطية — **يُبنى هنا ويُفتح هناك**.
 *
 * التنزيلُ ملاحةُ متصفّحٍ لا نداءُ `api` (المتصفّحُ هو من يحفظ الملفّ)، فلا
 * سبيلَ إلى `api.get`. **لكنّ المسارَ يبقى مُعلَناً في هذه الطبقة** كي يراه
 * `check:contract` — فالفرقُ بين «لا يمرّ بـ`api`» و«لا يُعرَف أنه موجود».
 */
export const backupDownloadUrl = (token: string) =>
  `${API_URL}/admin/backups/download/${token}`;

// ------------------------------- مطالباتُ كليك اليدوية (اشتراكات الكباتن)
//
// **التحصيلُ خطوةٌ واحدةٌ يقرأها الاشتراك**: «تأكيد الدفع» يملؤها المشرفُ اليوم
// بيده، ويملؤها القابضُ غداً بإشعاره — **وما بعدها لا يعرف مَن ملأها**.

export const listCliqClaims = (country?: CountryCode) =>
  api.get<CliqClaim[]>("/admin/cliq-claims", { query: { country } });

/** **المبلغُ مبلغُ المشرف** — ودونَ الثمن **لا تفعيل**، والمطالبةُ تبقى بفرقها. */
export const confirmCliqClaim = (id: string, amount: string) =>
  api.post<CliqClaim>(`/admin/cliq-claims/${id}/confirm`, { amount });

/** **من ضغط «تمّ الدفع» وينتظر** — صفحةُ المدفوعات تقرأ هذا الباب.
 *
 * **وهي غيرُ `listCliqClaims`**: تلك تعرض **كلَّ من فتح الشاشة**، وهذه **من
 * قال إنه حوّل**. ومن فتح ونسي لا ينتظر شيئاً.
 */
export const listDeclaredClaims = (country?: CountryCode) =>
  api.get<CliqClaim[]>("/admin/cliq-claims/declared", { query: { country } });

/** **رفضٌ بسببٍ مكتوبٍ يُعرض على صاحبه** — و«مرفوض» وحدَها تُنتج مكالمةَ دعم. */
export const rejectCliqClaim = (id: string, reason: string) =>
  api.post<CliqClaim>(`/admin/cliq-claims/${id}/reject`, { reason });

/** مستحقّاتُ الكباتن — **والمتبقّي `amount - collected` يُقرأ من العمودين**.
 *
 * **و`driver_id` للملفِّ الشخصيّ** (§37) — كالسلف.
 */
export const listDriverDebts = (
  status?: string,
  q?: string,
  driverId?: string,
) =>
  api.get<DriverDebtRow[]>("/admin/drivers/debts", {
    query: { status, q, driver_id: driverId },
  });

/** مطالباتُ السداد المعلّقة — ما ينتظر عينَ مشرف. */
export const listDebtClaims = () =>
  api.get<DebtClaimRow[]>("/admin/drivers/debts/claims");

/** **ما وصل فعلاً** لا ما فُتحت به المطالبة — والناقصُ يُقبل ويُنقص. */
export const confirmDebtClaim = (id: string, credited: string) =>
  api.post<DebtClaimRow>(`/admin/drivers/debts/claims/${id}/confirm`, {
    credited,
  });

/** شطبُ مستحقٍّ بقرارٍ مسجَّل — والسببُ مطلوبٌ لا اختياري. */
export const writeOffDebt = (id: string, reason: string) =>
  api.post<DriverDebtRow>(`/admin/drivers/debts/${id}/writeoff`, { reason });

/** قواعدُ التوزيع لكل سوق — **والغائبُ يعمل بالافتراضيّ ولا صفَّ له**. */
export const listDispatchSettings = () =>
  api.get<DispatchSetting[]>("/admin/settings/dispatch");

/** **ولا تمسّ رحلةً جارية**: القواعدُ تُقرأ مرّةً عند بدء توزيعها. */
export const updateDispatchSettings = (
  country: CountryCode,
  payload: Partial<Omit<DispatchSetting, "country_code">>,
) => api.patch<DispatchSetting>(`/admin/settings/dispatch/${country}`, payload);

// ── بلاطاتُ الخدمات واللافتات — **تُدار من هنا بلا نشر** (الترحيلة `0063`)

export const listServiceTiles = (country?: CountryCode) =>
  api.get<ServiceTileRow[]>("/admin/settings/service-tiles", {
    query: { country },
  });

export const createServiceTile = (payload: Partial<ServiceTileRow>) =>
  api.post<ServiceTileRow>("/admin/settings/service-tiles", payload);

export const updateServiceTile = (
  id: string,
  payload: Partial<ServiceTileRow>,
) => api.patch<ServiceTileRow>(`/admin/settings/service-tiles/${id}`, payload);

export const listPromoBanners = (country?: CountryCode) =>
  api.get<PromoBannerRow[]>("/admin/settings/promo-banners", {
    query: { country },
  });

export const createPromoBanner = (payload: Partial<PromoBannerRow>) =>
  api.post<PromoBannerRow>("/admin/settings/promo-banners", payload);

export const updatePromoBanner = (
  id: string,
  payload: Partial<PromoBannerRow>,
) => api.patch<PromoBannerRow>(`/admin/settings/promo-banners/${id}`, payload);

/** **قائمةُ الأيقونات المقرَّرة — تُقرأ ولا تُنسخ** (قرارُ المالك 2026-08-31).
 *
 * **ولا نسخةٌ ثانيةٌ تُكتب هنا**: نسختان تفترقان بحرفٍ يوماً، **فيعرض
 * المنتقي ما يرفضه الباب** — والمشرفُ يختار من قائمةٍ ثم يُمنع ولا يفهم لمَ.
 */
export const listServiceIcons = () =>
  api.get<string[]>("/admin/settings/service-icons");

/** **المقاصدُ المبنيّةُ ومن يراها** — والأدوارُ جزءُ الجواب لا زينة.
 *
 * `/account/bookings` مبنيٌّ **عند الراكب وحدَه**، **وبلاطةُ كبتنٍ تشير إليه
 * تقع على `path="*"`** — فاللوحةُ تعرض لكلِّ جمهورٍ ما يصلح له، **ولا تكتب
 * القائمةَ بيدها**.
 */
export const listServiceDestinations = () =>
  api.get<Record<string, string[]>>("/admin/settings/service-destinations");

/** **المسوّدةُ وحدَها تُحذف** — وما عُرض مرّةً يُخفى.
 *
 * **والزرُّ يُرسم معطَّلاً بعلّته** لا يُرسم ثم يرتدّ: زرٌّ يعمل ثم يرتدّ
 * يعلّم المشرفَ أن يعيد المحاولة، ومعطَّلٌ يقول لمَ يعلّمه أن يُخفي بدلَه.
 */
export const deleteServiceTile = (id: string) =>
  api.del<void>(`/admin/settings/service-tiles/${id}`);

export const deletePromoBanner = (id: string) =>
  api.del<void>(`/admin/settings/promo-banners/${id}`);

/** **صورةُ اللافتة — تُرفع وتُخزَّن ويخدمها باب** (الترحيلة `0064`).
 *
 * **والأربعةُ تُبنى معاً**: العمودُ والرفعُ والبابُ والعرض — **وواحدٌ ناقصاً
 * يعيد عطبَ الصورة المكسورة** الذي نُزع له العمودُ في 2026-08-30.
 */
export const uploadBannerImage = (id: string, file: File) =>
  upload<PromoBannerRow>(`/admin/settings/promo-banners/${id}/image`, file);

export const deleteBannerImage = (id: string) =>
  api.del<PromoBannerRow>(`/admin/settings/promo-banners/${id}/image`);

/** **بايتاتٌ أو ٤٠٤** — ولا حقلَ يقول «لها صورة».
 *
 * `<img>` لا يحمل ترويسةً، فتُجلب بالمفتاح وتُعرض من `blob:` — **ومن يفتحها
 * يغلقها**. وهي نسخةُ `driverDocumentBlob` على بابٍ آخر.
 *
 * **وبابُ اللوحة لا بابُ التطبيق**: الثاني يشترط سوقَ صاحبِ الحساب،
 * **والمشرفُ يهيّئ سوقاً قبل أن يُفتح** فيقرأ سوقاً ليس سوقَه.
 */
export async function bannerImageBlob(id: string): Promise<string> {
  const answer = await fetch(
    `${API_URL}/admin/settings/promo-banners/${id}/image`,
    { headers: { Authorization: `Bearer ${tokens.access() ?? ""}` } },
  );
  if (!answer.ok) throw new Error("لا صورة");
  return URL.createObjectURL(await answer.blob());
}


// ── حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31)
//
// **ولا بابَ تجميدٍ ولا فكّ**: التجمّدُ والاستئنافُ آليّان حين تسقط قناةُ
// السوق وتعود، **وفكُّ إيقافِ الحساب بتأكيد الرقم وحدَه** — وزرٌّ يفكّ بلا
// تأكيدٍ يُفرِّغ الحملةَ من معناها.

export const listVerificationCampaigns = () =>
  api.get<VerificationCampaignRow[]>("/admin/verification-campaigns");

export const createVerificationCampaign = (
  payload: { country_code: CountryCode; deadline_days: number },
) => api.post<VerificationCampaignRow>("/admin/verification-campaigns", payload);

/** **الإطلاقُ ضغطةُ المالك** — ولا تُرسل رسالةٌ واحدةٌ قبلها. */
export const startVerificationCampaign = (id: string) =>
  api.post<VerificationCampaignRow>(
    `/admin/verification-campaigns/${id}/start`,
  );

export const cancelVerificationCampaign = (id: string) =>
  api.post<VerificationCampaignRow>(
    `/admin/verification-campaigns/${id}/cancel`,
  );

// ------------------------------------------------------- سجلُّ الإصدارات

/** سجلُّ الإصدارات — **والحاكمُ منها مُعلَّمٌ من الخلفية** (البند ٨، §43). */
export const listReleases = (app?: ClientApp) =>
  api.get<AppRelease[]>("/admin/releases", {
    query: app ? { app } : undefined,
  });

/** **و`confirm_min_supported_build` هو الإذنُ الثاني** — يُرسل حين يرتفع
 *  الحدُّ، والخلفيةُ ترفض بدونه. وورقةُ الشاشة هي الأولى. */
export const createRelease = (body: {
  app: ClientApp;
  build: number;
  min_supported_build: number;
  download_url: string;
  release_notes: string;
  reminder_hours: number;
  confirm_min_supported_build?: number;
}) => api.post<AppRelease>("/admin/releases", body);

export const updateRelease = (
  releaseId: string,
  body: {
    app: ClientApp;
    build: number;
    min_supported_build: number;
    download_url: string;
    release_notes: string;
    reminder_hours: number;
    confirm_min_supported_build?: number;
  },
) => api.put<AppRelease>(`/admin/releases/${releaseId}`, body);

export const deleteRelease = (releaseId: string) =>
  api.del<void>(`/admin/releases/${releaseId}`);

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

// ------------------------------------------------ السياساتُ والشروط (البند ١٠)

export const listPolicies = (params: {
  country_code?: CountryCode;
  doc_type?: PolicyDocType;
  app?: PolicyApp;
}) => api.get<PolicyVersion[]>("/admin/policies", { query: params });

/** **نسخةٌ جديدةٌ تولد مسوّدة** — والنشرُ فعلٌ ثانٍ، فحفظٌ ينشر يجعل كلَّ
 *  تصحيحٍ إعلاناً. ولا بابَ تعديلٍ: من أراد تصحيحَ حرفٍ كتب نسخة. */
export const createPolicyVersion = (body: {
  country_code: CountryCode;
  doc_type: PolicyDocType;
  app: PolicyApp;
  body_ar: string;
  body_en?: string | null;
  requires_reconsent: boolean;
}) => api.post<PolicyVersion>("/admin/policies", body);

export const publishPolicy = (policyId: string) =>
  api.post<PolicyVersion>(`/admin/policies/${policyId}/publish`);

/** **سحبُ النشر** — فيعود السوقُ بلا وثيقةٍ قائمة، **ولا يُمحى شيء**.
 *  وحالٌ تُدخَل ولا يُخرج منها «بابٌ بلا زرّ في اتجاهٍ واحد». */
export const withdrawPolicy = (policyId: string) =>
  api.post<PolicyVersion>(`/admin/policies/${policyId}/withdraw`);

export const deletePolicyDraft = (policyId: string) =>
  api.del<void>(`/admin/policies/${policyId}`);

export const getOrgProfile = () => api.get<OrgProfile>("/admin/policies/org");

export const saveOrgProfile = (body: OrgProfile) =>
  api.put<OrgProfile>("/admin/policies/org", body);

// ------------------------------------------------------------ الموقع (§49)
//
// **بابُ كتابةٍ واحدٌ لكلِّ الحقول**: حقولُ الصفحة تُقرأ معاً وتُكتب معاً،
// **وبابٌ لكلِّ مجموعةٍ يجعل «ما الذي تغيّر؟» جواباً يُجمع من ثلاثة سجلّات**.

export const readSite = () => api.get<SiteSettings>("/admin/site");

/** **ما لم يُرسَل لا يُمسّ** — والخلفيةُ تقرأ `exclude_unset`. */
export const updateSite = (body: SiteUpdate) =>
  api.patch<SiteSettings>("/admin/site", body);
