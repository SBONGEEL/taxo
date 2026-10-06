/** **تفضيلا القيادة على الجهاز** (§٦١-ط/٦–٧) — كبقية تفضيلات الجهاز: مفتاحٌ لكلٍّ في `localStorage` بقراءةٍ تتحمّل الخطأ.
 *
 * - **تطبيقُ الملاحة**: «اختيار النظام» **افتراضاً — وهو ما يحدث اليوم حرفاً** (`geo:` في أندرويد يترك الاختيارَ للنظام) ·
 *   «خرائط قوقل» · «Waze».
 * - **القبولُ التلقائيُّ للطلبات القريبة**: **مطفأٌ افتراضاً** — ومن لم يُشعله لا يتغيّر عنده شيء.
 */

export type NavApp = "system" | "google" | "waze";

export const NAV_APPS: { value: NavApp; label: string }[] = [
  { value: "system", label: "اختيار النظام" },
  { value: "google", label: "خرائط قوقل" },
  { value: "waze", label: "Waze" },
];

/** **دون كيلومترٍ واحد** كما رُسم («أقل من 1 كم فقط»). */
export const AUTO_ACCEPT_KM = 1;

const NAV_KEY = "taxo.driver.nav_app";
const AUTO_KEY = "taxo.driver.auto_accept";
const TRAFFIC_KEY = "taxo.driver.traffic";

export function navApp(): NavApp {
  try {
    const value = localStorage.getItem(NAV_KEY);
    return value === "google" || value === "waze" ? value : "system";
  } catch {
    return "system";
  }
}

export function setNavApp(value: NavApp): void {
  try {
    if (value === "system") localStorage.removeItem(NAV_KEY);
    else localStorage.setItem(NAV_KEY, value);
  } catch {
    // جهازٌ يرفض التخزين: يبقى «اختيار النظام» — ما يحدث اليوم
  }
}

export function autoAcceptEnabled(): boolean {
  try {
    return localStorage.getItem(AUTO_KEY) === "on";
  } catch {
    return false;
  }
}

/** **طبقةُ الزحام** (§٦٢-ج/٤٨) — مطفأةٌ حتى يرفعها هو من الخريطة الموسَّعة، **وتتبعه في خرائطه كلِّها** (الرئيسيةُ والرحلة). */
export function trafficLayer(): boolean {
  try {
    return localStorage.getItem(TRAFFIC_KEY) === "on";
  } catch {
    return false;
  }
}

export function setTrafficLayer(on: boolean): void {
  try {
    if (on) localStorage.setItem(TRAFFIC_KEY, "on");
    else localStorage.removeItem(TRAFFIC_KEY);
  } catch {
    // جهازٌ يرفض التخزين: تبقى لهذه الفتحة وحدَها
  }
}

export function setAutoAccept(on: boolean): void {
  try {
    if (on) localStorage.setItem(AUTO_KEY, "on");
    else localStorage.removeItem(AUTO_KEY);
  } catch {
    // جهازٌ يرفض التخزين: يبقى مطفأً
  }
}
