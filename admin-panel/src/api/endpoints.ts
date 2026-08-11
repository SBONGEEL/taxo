/** كلُّ نداءٍ للخلفية باسمه ومساره — لا سلسلةَ مسارٍ في شاشة.
 *
 * تُضاف المسارات هنا مع الشاشة التي تحتاجها لا قبلها: قائمةٌ من نداءاتٍ لا
 * يستدعيها أحد تُصدّق نفسها ثم تُكتشف خاطئةً حين تُستعمل أول مرة.
 */

import { api } from "@/api/client";
import type {
  AppConfig,
  AuthResponse,
  Campaign,
  CampaignAudience,
  CountryCode,
  Delivery,
  NotificationSetting,
  User,
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
