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
  User,
  Vehicle,
  VehicleCategory,
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
export const startSignupChallenge = (phone: string, country_code: CountryCode) =>
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

export const listDocuments = () =>
  api.get<DriverDocuments>("/drivers/me/documents");

/** رفعُ مستند — `multipart` لا JSON، فيمر خارج `api.*` بعميلٍ يعرف الملفات. */
export const uploadDocument = (docType: DocumentType, file: File) =>
  upload<DocumentUpload>(`/drivers/me/documents/${docType}`, file);
