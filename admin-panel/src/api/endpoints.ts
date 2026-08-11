/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import { api } from "@/api/client";
import type {
  AdminDriverRow,
  AppConfig,
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
  FeatureKey,
  NotificationSetting,
  Payment,
  PaymentSetting,
  PaymentStatus,
  TopupRequest,
  TopupStatus,
  ProviderCatalog,
  ProviderCredential,
  ProviderKey,
  ProviderTestResult,
  User,
  WalletSetting,
  Withdrawal,
  WithdrawalStatus,
} from "@/api/types";

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
  api.post<AuthResponse>(
    "/auth/login",
    { phone, password, country_code: country },
    { anonymous: true },
  );

export const getMe = () => api.get<User>("/auth/me");

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
  }>,
) => api.patch<WalletSetting>(`/admin/settings/wallet/${country}`, payload);

export const listPaymentSettings = () =>
  api.get<PaymentSetting[]>("/admin/settings/payments");

export const updatePaymentSettings = (
  country: CountryCode,
  payload: { cliq_confirmation_hours: number },
) => api.patch<PaymentSetting>(`/admin/settings/payments/${country}`, payload);

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
