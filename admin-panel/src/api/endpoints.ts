/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import { api } from "@/api/client";
import type {
  DeactivationRequestRow,
  AdminDriverRow,
  AdminRideDetail,
  AdminRideRow,
  AppConfig,
  AuditAction,
  AuditLog,
  AuthResponse,
  Campaign,
  CampaignAudience,
  CommissionAppliesTo,
  CommissionSetting,
  CountryCode,
  CountryFeatureFlags,
  Delivery,
  DisputeResolution,
  DriverDocument,
  DriverDocuments,
  DriverStatus,
  AdminReferralRow,
  FeatureKey,
  Gender,
  LiveMap,
  LoginResponse,
  NotificationSetting,
  Payment,
  PaymentMethod,
  PaymentSetting,
  ReferralSetting,
  RideSharingSetting,
  ReferralSummary,
  PaymentStatus,
  PricingRule,
  PromoCode,
  Reports,
  RideStatus,
  SecurityPolicy,
  Subscription,
  SubscriptionDurationType,
  SubscriptionPlan,
  SubscriptionStatus,
  TopupRequest,
  TopupStatus,
  TotpConfirmation,
  TotpEnrollment,
  TotpStatus,
  ProviderCatalog,
  ProviderCredential,
  ProviderKey,
  ProviderTestResult,
  Overview,
  StatsPeriod,
  User,
  UserRole,
  VehicleCategory,
  Wallet,
  AdvanceRow,
  AdvanceSetting,
  WalletSetting,
  WalletTransaction,
  Withdrawal,
  WithdrawalStatus,
} from "@/api/types";

// ------------------------------------------------------ الكوبونات (12-ز)

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
export const login = (phone: string, password: string, country?: CountryCode) =>
  api.post<LoginResponse>(
    "/auth/login",
    { phone, password, country_code: country },
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
    { challenge_token, ...proof },
    { anonymous: true },
  );

export const getMe = () => api.get<User>("/auth/me");

// ------------------------------------------- التحقق الثنائي (المرحلة 12-د)

export const getMyTotp = () => api.get<TotpStatus>("/auth/me/totp");

export const enrollTotp = () => api.post<TotpEnrollment>("/auth/me/totp/enroll");

export const confirmTotp = (code: string) =>
  api.post<TotpConfirmation>("/auth/me/totp/confirm", { code });

export const verifyRecoveryCode = (recovery_code: string) =>
  api.post<TotpStatus>("/auth/me/totp/recovery/verify", { recovery_code });

export const disableTotp = (proof: { code?: string; recovery_code?: string }) =>
  api.del<void>("/auth/me/totp", { body: proof });

export const getSecurityPolicy = () => api.get<SecurityPolicy>("/admin/security");

export const updateSecurityPolicy = (body: {
  admin_totp_required?: boolean;
  admin_idle_timeout_minutes?: number;
}) => api.put<SecurityPolicy>("/admin/security", body);

export const logout = (refreshToken: string) =>
  api.post<void>("/auth/logout", { refresh_token: refreshToken });

// ------------------------------------------------------------ الحملات

export const listCampaigns = (status?: string) =>
  api.get<Campaign[]>("/admin/campaigns", { query: { status } });

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

export const getDriverDocuments = (driverId: string) =>
  api.get<DriverDocuments>(`/admin/drivers/${driverId}/documents`);

/** قبولٌ أو رفضٌ **بسبب** — والسببُ يصل صاحبَه في الإشعار (القسم 13/2). */
export const reviewDocument = (
  driverId: string,
  documentId: string,
  approved: boolean,
  note?: string,
) =>
  api.post<DriverDocument>(
    `/admin/drivers/${driverId}/documents/${documentId}/review`,
    { approved, note: note ?? null },
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

export const listTopups = (status?: TopupStatus) =>
  api.get<TopupRequest[]>("/admin/topups", { query: { status } });

export const confirmTopup = (id: string) =>
  api.post<TopupRequest>(`/admin/topups/${id}/confirm`, {});

export const rejectTopup = (id: string, note?: string) =>
  api.post<TopupRequest>(`/admin/topups/${id}/reject`, { note: note ?? null });

export const listWithdrawals = (status?: WithdrawalStatus) =>
  api.get<Withdrawal[]>("/admin/withdrawals", { query: { status } });

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

export const listPayments = (status?: PaymentStatus, country?: CountryCode) =>
  api.get<Payment[]>("/admin/payments", {
    query: { status, country_code: country },
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
    tip_preset_small?: string;
    tip_preset_medium?: string;
    tip_max?: string;
  },
) => api.patch<PaymentSetting>(`/admin/settings/payments/${country}`, payload);

// ------------------------------------------------- إحالةُ السائقات (12-ح)

export const getReferralSettings = (country: CountryCode) =>
  api.get<ReferralSetting>(`/admin/referrals/settings?country_code=${country}`);

export const updateReferralSettings = (
  country: CountryCode,
  payload: { reward_amount?: string; required_rides?: number },
) =>
  api.put<ReferralSetting>(
    `/admin/referrals/settings?country_code=${country}`,
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
export const listReferrals = (country: CountryCode, rewarded?: boolean) =>
  api.get<AdminReferralRow[]>(
    `/admin/referrals?country_code=${country}` +
      (rewarded === undefined ? "" : `&rewarded=${rewarded}`),
  );

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

/** الحظرُ **بسببٍ إلزامي** يدخل سجل التدقيق ولا يصل صاحب الحساب. */
export const blockUser = (userId: string, reason: string) =>
  api.post<User>(`/admin/users/${userId}/block`, { reason });

export const unblockUser = (userId: string, reason?: string) =>
  api.post<User>(`/admin/users/${userId}/unblock`, { reason: reason ?? null });

// ---------------------------------------------------- محفظةُ حسابٍ بعينه

export const getWallet = (userId: string) =>
  api.get<Wallet>(`/admin/wallets/${userId}`);

export const listWalletTransactions = (userId: string, limit = 20) =>
  api.get<WalletTransaction[]>(`/admin/wallets/${userId}/transactions`, {
    query: { limit },
  });

/** تجميدٌ يوقف حركة المحفظة **ويبقي صاحبها راكباً يدفع نقداً** (القسم 13/3).
 *
 * والسببُ اختياريٌّ في الخلفية، ويُرسل حين يكتبه المشرف: قيدُ تدقيقٍ يقول
 * «جُمّدت» بلا «لماذا» نصفُ قيد.
 */
export const freezeWallet = (userId: string, reason?: string) =>
  api.post<Wallet>(`/admin/wallets/${userId}/freeze`, {
    reason: reason ?? null,
  });

export const unfreezeWallet = (userId: string, reason?: string) =>
  api.post<Wallet>(`/admin/wallets/${userId}/unfreeze`, {
    reason: reason ?? null,
  });

// ------------------------------------------------------ الاشتراكات والباقات

export const listSubscriptions = (
  params: {
    subscription_status?: SubscriptionStatus;
    driver_id?: string;
    country_code?: CountryCode;
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
    limit?: number;
    offset?: number;
  } = {},
) => api.get<AuditLog[]>("/admin/settings/audit-logs", { query: params });

/** طلباتُ إلغاء التفعيل — والمعلّقةُ أولاً بحكم ترتيب الخلفية (البند ١٣). */
export const listDeactivations = (status?: string) =>
  api.get<DeactivationRequestRow[]>(
    "/admin/drivers/deactivations" + (status ? `?status=${status}` : ""),
  );

export const decideDeactivation = (
  id: string,
  payload: { approved: boolean; note?: string },
) => api.patch<DeactivationRequestRow>(`/admin/drivers/deactivations/${id}`, payload);

// ------------------------------------------------------ السلف (البند ١٥)

/** سياسةُ السلف لكل دولة — والقائمةُ لأن الجدولَ صغيرٌ ودولتان لا أكثر. */
export const listAdvanceSettings = () =>
  api.get<AdvanceSetting[]>("/admin/settings/advances");

export const updateAdvanceSettings = (
  country: CountryCode,
  payload: Partial<Omit<AdvanceSetting, "country_code">>,
) => api.patch<AdvanceSetting>(`/admin/settings/advances/${country}`, payload);

/** السلفُ بمتبقّيها — **مطروحاً في الخلفية** لا في المتصفح. */
export const listAdvances = (status?: string) =>
  api.get<AdvanceRow[]>("/admin/drivers/advances" + (status ? `?status=${status}` : ""));

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
