/** عميل HTTP واحد لكل نداءات الخلفية.
 *
 * ثلاثة أشياء لا تُكرَّر في كل شاشة، فتسكن هنا:
 *
 * 1. **ترجمة الخطأ**: الخلفية تردّ جسماً موحداً `{code, message}` (انظر
 *    `core/exceptions.py`)، فيرتفع `ApiError` برسالته العربية جاهزةً للعرض —
 *    ولا تخترع الواجهة نصّاً لخطأٍ قالته الخلفية بالعربية أصلاً.
 * 2. **تجديد الجلسة**: توكن الدخول قصير العمر، والتجديد **دورةٌ واحدة**
 *    (`rotate_refresh_token` يحذف المفتاح ويرفض إعادته). فطلبٌ يرتدّ 401
 *    يجدّد **مرةً واحدة** ويعيد المحاولة، وطلباتٌ متوازية تتقاسم نفس وعد
 *    التجديد — وإلا أحرق كلٌّ منها رمز الآخر وخرج المستخدم من حسابه.
 * 3. **العنوان**: مسارٌ واحد `/api/v1` في مكانٍ واحد.
 *
 * ومفاتيحُ التخزين مسبوقةٌ بـ`taxo.admin.`: التطبيقات الثلاثة تفتح على نفس
 * المضيف في التطوير، وجلسةٌ تدهس جلسةً تُخرج أحدها من حسابه بلا سبب ظاهر.
 */

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001"
).replace(/\/$/, "");

export const API_PREFIX = "/api/v1";
export const API_URL = `${BASE_URL}${API_PREFIX}`;

const ACCESS_KEY = "taxo.admin.access_token";
const REFRESH_KEY = "taxo.admin.refresh_token";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly retryAfter?: number,
    /** حقولٌ إضافية يحملها جسمُ الخطأ — مثل `fallback_channel` (12-هـ).
     *
     * `AppError.extra` في الخلفية يُدمج في الجسم، وهو ما يجعل الرفضَ ذا مخرج:
     * «تعذّر إرسال رمز واتساب» + القناةُ التالية = زرٌّ يُرسم، بدل رسالةٍ لا
     * تفعل شيئاً.
     */
    readonly extra: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** قيمةٌ نصّية من حقولِ الخطأ الإضافية، أو `null`. */
  field(key: string): string | null {
    const value = this.extra[key];
    return typeof value === "string" ? value : null;
  }
}

// ------------------------------------------------------------ التخزين

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  save(pair: { access_token: string; refresh_token: string }) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

/** يُستدعى حين يسقط التجديد — تلتقطه طبقة الجلسة فتعيد المستخدم للدخول. */
let onSessionLost: () => void = () => {};
export function setSessionLostHandler(handler: () => void) {
  onSessionLost = handler;
}

/** يُستدعى حين تردّ الخلفية `totp_enrollment_required` (SPEC §14.1، 12-د).
 *
 * الإلزامُ يسري على جلسةٍ قائمة لحظةَ إشعاله — الحارسُ في الخلفية يقرأ الصفَّ
 * في كل طلب — فقد يرتدّ **أيُّ** نداءٍ في أيّ شاشة. ولو تُرك لكل شاشة أن
 * تترجمه بنفسها لرأى المشرفُ خطأً أحمر في كل بطاقة بدل بابٍ يفتح: مكانُه هنا،
 * فتقوده طبقةُ الجلسة إلى شاشة الأمان مرةً واحدة.
 */
let onEnrollmentRequired: () => void = () => {};
export function setEnrollmentRequiredHandler(handler: () => void) {
  onEnrollmentRequired = handler;
}

// ------------------------------------------------------------ التجديد

let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const token = tokens.refresh();
  if (!token) return false;

  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
  });

  if (!response.ok) {
    tokens.clear();
    return false;
  }
  tokens.save(await response.json());
  return true;
}

/** التجديد **مرةً واحدة مهما تزامنت الطلبات**: الرمز يُستهلك عند أول دورة. */
function refreshOnce(): Promise<boolean> {
  refreshing ??= refreshSession().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

// ------------------------------------------------------------ الطلب

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** مسارٌ عام لا يحمل توكناً (`/config`، `/auth/*`). */
  anonymous?: boolean;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== "")
      url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function toError(response: Response): Promise<ApiError> {
  let code = "http_error";
  let message = "تعذّر الاتصال بالخادم";
  try {
    const body = await response.json();
    code = body.code ?? code;
    // **الحقلُ `detail` لا `message`**: هذا ما يكتبه معالجُ الأخطاء في
    // `core/exceptions.py` (`{"code": …, "detail": …}`). وقراءةُ `message`
    // وحدها كانت تُسقط كلَّ نصٍّ عربيٍّ كتبته الخلفية فتحلّ محلَّه رسالةٌ عامة
    // — أي أن قاعدةَ «لا تخترع الواجهةُ نصّاً لخطأٍ سمّته الخلفية» كانت
    // مكتوبةً ولا تعمل. و`message` تبقى مقروءةً احتياطاً لا أكثر
    message = body.detail ?? body.message ?? message;
    return new ApiError(response.status, code, message, body.retry_after, body);
  } catch {
    return new ApiError(response.status, code, message);
  }
}

async function send<T>(
  path: string,
  options: RequestOptions,
  retry: boolean,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const access = tokens.access();
  if (!options.anonymous && access) headers.Authorization = `Bearer ${access}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "لا اتصال بالإنترنت — حاول مجدداً");
  }

  if (response.status === 401 && retry && !options.anonymous) {
    if (await refreshOnce()) return send<T>(path, options, false);
    tokens.clear();
    onSessionLost();
  }

  if (!response.ok) {
    const error = await toError(response);
    if (error.code === "totp_enrollment_required") onEnrollmentRequired();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  return send<T>(path, options, true);
}

/** رفعُ ملفٍ واحد بـ`multipart`.
 *
 * خارج `request` عمداً: ذاك يضع `Content-Type: application/json` ويُسلسِل
 * الجسم، وكلاهما يفسد الرفع — حدُّ الأجزاء (boundary) يكتبه المتصفح ولا
 * يجوز أن نكتبه نحن. ولا يشارك التجديد التلقائي لأن الملف لا يُقرأ مرتين:
 * توكنٌ منتهٍ هنا يعني إعادةَ الرفع لا إعادةَ الطلب صامتةً.
 */
export async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);

  const access = tokens.access();
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "PUT",
      headers: access ? { Authorization: `Bearer ${access}` } : {},
      body: form,
    });
  } catch {
    throw new ApiError(0, "network_error", "لا اتصال بالإنترنت — حاول مجدداً");
  }

  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

export const api = {
  get: <T>(
    path: string,
    options: Omit<RequestOptions, "method" | "body"> = {},
  ) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  // **بجسمٍ**: إطفاءُ التحقق الثنائي يطلب رمزاً حاضراً (SPEC §14.1)، ورمزٌ في
  // مسار URL يسكن سجلَّ الوصول وسِجلَّ المتصفح — وهو بيانُ اعتمادٍ لا مُعرّف
  del: <T>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "DELETE" }),
};
