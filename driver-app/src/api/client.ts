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
 * ومفاتيحُ التخزين مسبوقةٌ بـ`taxo.driver.`: التطبيقان قد يفتحان على نفس
 * المضيف في التطوير، وجلسةٌ تدهس جلسةً تُخرج أحدهما من حسابه بلا سبب ظاهر.
 */

/** **أصلُ الخلفية** — يُصدَّر لأن رسمات المركبات ملفاتٌ تخدمها الخلفيةُ لا
 *  الحزمة: في الإنتاج التطبيقُ على `driver.tajora.ly` والخلفيةُ على
 *  `api.tajora.ly`، فمسارٌ نسبيٌّ يُبنى على أصل الصفحة يقع على موقعٍ لا صورةَ
 *  فيه. والبناءُ في مكانٍ واحد (`lib/skins.ts::skinAssetUrl`) لا في كل بطاقة. */
export // **ولا احتياطَ صامتٌ لعنوان** (أربعُ نسخ، 2026-08-26): كان هنا
// `?? "http://127.0.0.1:8001"` — **فبناءٌ نُسي فيه المتغيّرُ ينجح ويُشحن**،
// ويفتح صاحبُ الهاتف تطبيقاً يخاطب **هاتفَه نفسَه**. وهي بعينها العلّةُ التي
// أوقفت `POSTGRES_PASSWORD:?` عن الاحتياط: **قيمةٌ افتراضيةٌ لشيءٍ يقرّر إلى
// أين تذهب البيانات ليست تسهيلاً، بل عطبٌ مؤجَّل.**
//
// **والوقوفُ صريحٌ عند أوّل نداء** لا عند البناء وحدَه: `check:target` يمنع
// البناءَ بلا هدف، وهذا يمنع حزمةً أفلتت منه من أن تعمل صامتةً.
const RAW_BASE = import.meta.env.VITE_API_BASE_URL;
if (!RAW_BASE) {
  throw new Error(
    "VITE_API_BASE_URL غيرُ مضبوط — بُنيت هذه الحزمةُ بلا عنوانِ خلفية. " +
      "تُبنى بـ: TAXO_CHANNEL=<public|test> node tools/build-channel.mjs <app>",
  );
}
export const BASE_URL = RAW_BASE.replace(/\/$/, "");

export const API_PREFIX = "/api/v1";
export const API_URL = `${BASE_URL}${API_PREFIX}`;
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws`;

const ACCESS_KEY = "taxo.driver.access_token";
const REFRESH_KEY = "taxo.driver.refresh_token";

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

/** **رمزُ التجديد في الذاكرة ما دام التطبيقُ حيّاً** — ومن ورائه بيتٌ واحدٌ
 * على القرص: `localStorage` حين تكون البصمةُ مطفأة، **والمخزنُ الآمن وحدَه**
 * حين تُشعَل.
 *
 * **ولمَ لا بيتان**: الرمزُ **يُستهلك مرّةً ويُدوَّر** (`rotate_refresh_token`)،
 * **فنسخةٌ ثانيةٌ تموت عند أوّل تجديد** ثم تردّ «جلسة منتهية» بلا سبب يظهر —
 * وهو الشكلُ الثامن. انظر `lib/biometric.ts`.
 */
let liveRefresh: string | null = null;

/** يُملأ من `lib/biometric` — **حقنٌ لا استيراد**: `client` طبقةٌ تحته، واستيرادُ
 *  الأعلى من الأسفل يصنع حلقةً ويجعل الملحقَ يُحمَّل في المتصفّح بلا داعٍ. */
let persistRefresh: (token: string) => void = () => {};
export function setRefreshPersister(fn: (token: string) => void) {
  persistRefresh = fn;
}

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => liveRefresh ?? localStorage.getItem(REFRESH_KEY),
  /** **يُستدعى بعد كلِّ تدوير** — فيبقى المخزَّنُ هو الحيَّ لا نسخةً منه. */
  save(pair: { access_token: string; refresh_token: string }) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    liveRefresh = pair.refresh_token;
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    persistRefresh(pair.refresh_token);
  },
  /** **يُنزع من `localStorage` حين تُشعَل البصمة** — بيتٌ واحدٌ لا اثنان. */
  detachFromLocalStorage() {
    localStorage.removeItem(REFRESH_KEY);
  },
  /** يُسلَّم إلى مسار الفتح: يضع الرمزَ المفتوحَ في الذاكرة قبل التجديد. */
  adoptRefresh(token: string) {
    liveRefresh = token;
  },
  clear() {
    liveRefresh = null;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

/** يُستدعى حين يسقط التجديد — تلتقطه طبقة الجلسة فتعيد المستخدم للدخول. */
let onSessionLost: (serverRejected: boolean) => void = () => {};
export function setSessionLostHandler(handler: (serverRejected: boolean) => void) {
  onSessionLost = handler;
}

// ------------------------------------------------------------ التجديد

let refreshing: Promise<boolean> | null = null;

/** **هل رفض الخادمُ رمزاً قدّمناه فعلاً؟** — أم لم يكن لدينا ما نقدّمه؟
 *
 * **والفرقُ هو كلُّ شيء** (صُحّح 2026-08-29): «لا رمزَ ⇒ انتهت الجلسة» كان
 * **صادقاً ببيتٍ واحد** — يومَ كان الرمزُ في `localStorage` أو لا مكانَ له.
 * **فلمّا صار له بيتان** (المخزنُ الآمن حين تُشعَل البصمة) صار غيابُه عن
 * الذاكرة **لا يعني غيابَه**.
 *
 * **وأثرُه كان أن الميزةَ لا تعمل أبداً**: إقلاعٌ بارد ⇒ الذاكرةُ فارغة ⇒
 * «انتهت الجلسة» ⇒ `forgetToken()` **يمحو الرمزَ قبل أن يُستعمل مرّةً**.
 */
let serverRejectedToken = false;

async function refreshSession(): Promise<boolean> {
  const token = tokens.refresh();
  if (!token) {
    // **لا رمزَ في الذاكرة ليس إبطالاً من الخادم** — فلا يُمحى المخزَّن،
    // وتُعرض شاشةُ الدخول بزرِّ البصمة إن كان ثمّة رمزٌ محفوظ
    serverRejectedToken = false;
    return false;
  }

  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
  });

  if (!response.ok) {
    // **هنا وحدَه قال الخادمُ «لم تعد صالحة»** — رمزٌ قُدِّم فرُفض
    serverRejectedToken = true;
    tokens.clear();
    return false;
  }
  tokens.save(await response.json());
  return true;
}

/** **بابُ التجديد نفسُه لمسار البصمة** — ولا نداءَ ثانٍ إلى `/auth/refresh`.
 *
 * **ولمَ لا نداءٌ خاصٌّ بالبصمة**: نسخةٌ ثانيةٌ من منطق التجديد تعني موضعين
 * يكتبان الرمزَ المُدوَّر، ويوماً يُصلَح أحدُهما — وهو بابان ينشران الشيءَ
 * نفسَه. **والفتحُ يضع الرمزَ في الذاكرة ثمّ يمرّ من هنا كأيِّ تجديد.**
 */
export function refreshNow(): Promise<boolean> {
  return refreshOnce();
}

/** التجديد **مرةً واحدة مهما تزامنت الطلبات**: الرمز يُستهلك عند أول دورة. */
function refreshOnce(): Promise<boolean> {
  refreshing ??= refreshSession().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

// ------------------------------------------------- أخطاء الشبكة الأربعة

/** **مهلةٌ لكل صنفِ مسار، لا مهلةٌ واحدةٌ من أبطئها.**
 *
 * مهلةٌ موحّدةٌ على أبطأ مسار تترك شاشةَ «اقبل الطلب» تدور دقيقةً على شبكةٍ
 * ساقطة — والكبتنُ ينتظر عدّاداً مدّتُه عشرون ثانية. فالتصنيفُ ليس تنظيماً:
 * قيمةُ المهلة هي **كم يصبر المستخدمُ قبل أن يُقال له ماذا يفعل**.
 *
 * **وكلُّ رقمٍ مشتقٌّ من سقف الخادم لمساره** — لا من تقدير. والقاعدة: مهلةُ
 * العميل **تتجاوز** سقفَ الخادم؛ وإلا قطعنا طلباً سيُجيب عنه الخادمُ فعلاً،
 * فيعيد صاحبُه الإرسال على عمليةٍ تمّت.
 *
 * | الصنف | ما قِيس (محلياً) | سقفُ الخادم | المهلة |
 * |---|---|---|---|
 * | تفاعلٌ لحظيّ (قاعدةُ بيانات فقط) | ٦–٥١ مللي | لا نداءَ خارجيّ | **١٥ث** |
 * | مسارٌ بنداء مزوّد (تقدير/إعادة توجيه) | ١٩٩–٨٤٩ مللي | ١٠ث (`directions`) | **٢٠ث** |
 * | إرسالُ رمز | ٠٫٧٤–٣٫٥ث | ٤٥ث (`15 + 30`) | **٥٠ث** |
 *
 * والرفعُ **بلا مهلة** — ومعه زرُّ إلغاءٍ ومؤشرُ تقدّم: ملفٌّ كبيرٌ على شبكةٍ
 * بطيئة يتجاوز أيَّ رقمٍ وهو ناجح، فالمخرجُ بيد صاحبه لا بيد عدّاد.
 */
const TIMEOUT_INTERACTIVE_MS = 15_000;
const TIMEOUT_PROVIDER_MS = 20_000;
const TIMEOUT_OTP_MS = 50_000;

/** المساراتُ التي تخرج عن صنف التفاعل اللحظي — وما عداها لحظيّ. */
function timeoutFor(path: string): number {
  if (path === "/auth/challenge" || path === "/auth/password-reset/challenge") {
    return TIMEOUT_OTP_MS;
  }
  if (path === "/rides/estimate" || path.endsWith("/reroute")) {
    return TIMEOUT_PROVIDER_MS;
  }
  return TIMEOUT_INTERACTIVE_MS;
}

/** **أربعةُ أخطاءٍ لا «خطأٌ مجهول»** (SPEC ١٧.٦).
 *
 * والفرقُ بينها فرقٌ في **ما يفعله القارئ**: «لا اتصال» يجعله يفحص شبكته،
 * و«الخادم لا يستجيب» يجعله ينتظر — ورسالةٌ واحدةٌ لهما تُرسل نصفَ الناس
 * يفحصون ما ليس معطوباً.
 */
function networkError(error: unknown): ApiError {
  if ((error as Error)?.name === "TimeoutError" || (error as Error)?.name === "AbortError") {
    return new ApiError(
      0,
      "network_timeout",
      "الخادم لا يستجيب — انتهت المهلة. أعد المحاولة",
    );
  }
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return new ApiError(
      0,
      "network_offline",
      "لا اتصال بالإنترنت — تحقّق من شبكتك ثم أعد المحاولة",
    );
  }
  return new ApiError(
    0,
    "network_unreachable",
    "تعذّر الوصول إلى الخادم — أعد المحاولة بعد قليل",
  );
}

/** ردٌّ وصل ولم يُقرأ: حالةٌ رابعةٌ غيرُ الثلاث — الخادمُ حيٌّ وجوابُه ليس ما نتوقع. */
function unexpectedResponse(): ApiError {
  return new ApiError(
    0,
    "network_unexpected",
    "ردٌّ غير متوقَّع من الخادم — أعد المحاولة",
  );
}

/** يجمع مهلةَ المسار مع إلغاءِ المستدعي إن وُجد. */
function withTimeout(path: string, signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(timeoutFor(path));
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

// ------------------------------------------------------------ الطلب

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** مسارٌ عام لا يحمل توكناً (`/config`، `/auth/*`). */
  anonymous?: boolean;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
  /** **بايتاتٌ لا JSON**: صورةُ الراكب (البند ٥٢) تمرّ بنفس المسار فتأخذ
   *  تجديدَ التوكن ومعالجةَ الخطأ وعنوانَ الخادم من مكانٍ واحد. ومسارٌ ثانٍ
   *  لها كان سيعيد كتابة الأربعة ثم يفترق عنها أوّلَ تعديل. */
  raw?: boolean;
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
    // **`message` وحدَه** — عقدُ الأخطاء (SPEC القسم ١٥): كلُّ خطأٍ من الخلفية
    // يحمل `code` و`message` عربيةً جاهزةً للعرض، و`field` حين يخصّ حقلاً.
    //
    // وكان الاسمُ `detail`، فصادم اسمَ FastAPI نفسِه في الـ422 حيث تكون قيمتُه
    // **مصفوفةَ أخطاءٍ** لا نصّاً — فيُمرَّر كائنٌ إلى `Error` ويقرأ المستخدمُ
    // `[object Object]`. اسمٌ واحدٌ لمعنيين هو العطبُ نفسُه، لا تسميتُه.
    //
    // **ولا احتياطَ على `detail`**: احتياطٌ كهذا يُبقي الشكلَ القديم يعمل، فلا
    // يُكتشف مسارٌ نُسي — وقاعدةُ «لا شكلَ ثانٍ ولا استثناء» تُحرَس بالكسر.
    message = body.message ?? message;
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
      signal: withTimeout(path, options.signal),
    });
  } catch (error) {
    // إلغاءٌ من المستدعي (تبديلُ شاشة) ليس خطأً يُعرض
    if ((error as Error).name === "AbortError" && options.signal?.aborted) {
      throw error;
    }
    throw networkError(error);
  }

  if (response.status === 401 && retry && !options.anonymous) {
    if (await refreshOnce()) return send<T>(path, options, false);
    tokens.clear();
    // **يُبلَّغ أَرفض الخادمُ رمزاً أم لم يكن لدينا رمز** — والمحوُ للأوّل
    // وحدَه (القاعدةُ الثالثة من الأربع: «ردُّ الخادم بأن الجلسة لم تعد صالحة»)
    onSessionLost(serverRejectedToken);
  }

  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  if (options.raw) return (await response.blob()) as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw unexpectedResponse();
  }
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
export interface UploadOptions {
  /** نسبةُ ما رُفع (٠–١٠٠) — تُستدعى مراراً أثناء الرفع. */
  onProgress?: (percent: number) => void;
  /** إلغاءٌ بيد المستخدم. */
  signal?: AbortSignal;
  /** تاريخُ انتهاء صلاحية المستند — `YYYY-MM-DD`، ويُترك فارغاً لما لا ينتهي. */
  expiresOn?: string;
}

export async function upload<T>(
  path: string,
  file: File,
  options: UploadOptions = {},
): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  // **حقلٌ يُرسَل حين يُملأ وحدَه** (البند ب): خانةٌ فارغةٌ تُرسَل نصّاً فارغاً
  // فتصير `date` غيرَ صالحةٍ ويرتدّ الرفعُ كلُّه بـ422 — والوثيقةُ التي لا
  // تنتهي (صورةُ المركبة) خانتُها فارغةٌ بحقّ.
  if (options.expiresOn) form.append("expires_on", options.expiresOn);
  const access = tokens.access();

  // **`XMLHttpRequest` لا `fetch`، ولسببٍ واحدٍ لا بديلَ عنه**: `fetch` **لا
  // يبلّغ عن تقدّم الرفع** إطلاقاً (لا حدثَ ولا تيّار)، فمن يرفع صورةً على
  // شبكةٍ بطيئة يرى شاشةً واقفةً لا يدري أتتقدّم أم ماتت. و`XHR` وحدَه يملك
  // `upload.onprogress`.
  //
  // **ولا مهلةَ عليه** — ومعه مخرجان بدلَها: نسبةٌ تُطمئن، وزرُّ إلغاءٍ يقطع.
  // ملفٌّ كبيرٌ على شبكةٍ بطيئة يتجاوز أيَّ مهلةٍ معقولة **وهو ناجح**، وقطعُه
  // بعدّادٍ يعيد الرفعَ من أوّله بلا سبب. **وشاشةٌ بلا مخرجٍ هي العطبُ نفسُه
  // الذي يُصلحه عقدُ الأخطاء**، فالمخرجُ بيد صاحبها لا بيد عدّاد.
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", `${API_URL}${path}`);
    if (access) request.setRequestHeader("Authorization", `Bearer ${access}`);

    // **كاشفُ الركود** — والإلغاءُ وحدَه لا يغني عنه: الإلغاءُ يعالج من قرّر
    // التوقّف، والركودُ يعالج **وصلةً ماتت صامتة**. مقبسٌ يسقط أثناء الرفع لا
    // يُطلق `onerror` بالضرورة: الـTCP يعيد الإرسالَ في صمتٍ دقائقَ قبل أن
    // يستسلم، فيقف الشريطُ عند ٤٧٪ بلا حدثٍ ولا رسالة — وهي الشاشةُ بلا مخرجٍ
    // التي يوجد هذا العقدُ لإزالتها.
    //
    // **والمدّةُ مقيسةٌ لا مقدَّرة** (2026-08-18، Edge حقيقي عبر CDP على نفس
    // المسار): أكبرُ فجوةٍ بين حدثين كانت **١٢٢ مللي** على localhost،
    // و**٤٣٣ مللي** على ٥٠ك.ب/ث، و**١٤٤٠ مللي** على ١٢ك.ب/ث — أي على وصلةٍ
    // بالكاد صالحةٍ للاستعمال (٥٠٦ك.ب في ٤٣ ثانية). فعشرون ثانيةً نحوُ
    // **أربعةَ عشرَ ضعفَ** أسوأِ فجوةٍ مقيسة: لا تشتعل على رفعٍ بطيءٍ حيّ،
    // وتسبق استسلامَ الـTCP (دقائق) بكثير.
    const STALL_MS = 20_000;
    let stalled = false;
    let stallTimer: ReturnType<typeof setTimeout> | undefined;

    const armStall = () => {
      clearTimeout(stallTimer);
      stallTimer = setTimeout(() => {
        stalled = true;
        request.abort();
      }, STALL_MS);
    };

    request.upload.onprogress = (event) => {
      armStall();
      if (!event.lengthComputable) return;
      options.onProgress?.(Math.round((event.loaded / event.total) * 100));
    };

    const abort = () => request.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    const done = () => {
      clearTimeout(stallTimer);
      options.signal?.removeEventListener("abort", abort);
    };

    // **الإلغاءُ ليس خطأً يُعرض**: صاحبُه يعرف أنه ألغى، ورسالةٌ حمراءُ بعده
    // تجعله يظنّ أن شيئاً انكسر. فيُرمى `AbortError` كما يرميه `fetch`،
    // فتعرفه الشاشاتُ بالاسم نفسِه ولا تعرض له شيئاً.
    request.onabort = () => {
      done();
      // **يُفرَّق القطعان**: قطعُ الركود عطبٌ يُعرض ومعه إعادةُ المحاولة، وقطعُ
      // المستخدم قرارُه هو فلا يُعرض له شيء. وهما يمرّان بنفس الحدث.
      if (stalled) {
        reject(
          new ApiError(
            0,
            "network_timeout",
            "توقّف الرفع — انقطع الاتصال. أعد المحاولة",
          ),
        );
        return;
      }
      reject(new DOMException("أُلغي الرفع", "AbortError"));
    };
    request.onerror = () => {
      done();
      reject(networkError(new Error("upload failed")));
    };
    // **`ontimeout` صريحةٌ ولو لم نضبط `xhr.timeout`**: قيمتُها الافتراضية صفرٌ
    // (بلا مهلة)، لكنّ معالجاً غائباً يعني أن ضبطَ المهلة يوماً يُسقط الوعدَ
    // بلا رفضٍ ولا حلّ — فيبقى المستخدمُ أمام شريطٍ لا ينتهي.
    request.ontimeout = () => {
      done();
      reject(
        new ApiError(0, "network_timeout", "انتهت مهلة الرفع — أعد المحاولة"),
      );
    };
    request.onload = () => {
      done();
      if (request.status >= 200 && request.status < 300) {
        try {
          resolve(JSON.parse(request.responseText) as T);
        } catch {
          reject(unexpectedResponse());
        }
        return;
      }
      // نفسُ عقد الأخطاء: `code` و`message` عربيةً — لا نصَّ خامٍ من الخادم
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(request.responseText) as Record<string, unknown>;
      } catch {
        /* ردٌّ غيرُ مقروء — تُستعمل الحالةُ وحدَها */
      }
      reject(
        new ApiError(
          request.status,
          String(body.code ?? "http_error"),
          String(body.message ?? "تعذّر رفع الملف — أعد المحاولة"),
          undefined,
          body,
        ),
      );
    };

    armStall();
    request.send(form);
  });
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
  del: <T>(path: string, options: RequestOptions = {}) =>
    request<T>(path, { ...options, method: "DELETE" }),
  /** بايتاتٌ خام — للصور التي تمرّ بحارسِ الجلسة (صورةُ الراكب، البند ٥٢). */
  blob: (path: string, options: Omit<RequestOptions, "method" | "body"> = {}) =>
    request<Blob>(path, { ...options, method: "GET", raw: true }),
};
