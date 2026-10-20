/** **إشعاراتُ المالك خارج اللوحة** (SPEC §٨١/٢–٣) — المتصفّحُ على الحاسوب، وتطبيقُ الإدارة على الهاتف.
 *
 * ## المتصفّح — يعمل واللسانُ مغلق
 *
 * **عاملُ خدمةٍ** (`public/alerts-sw.js`) يستقبل الدفعَ ويرسم الإشعارَ بأيقونة فئته وشارةِ TAXO وزرَّي «افتح» و«مقروء». **وإعدادُ
 * Firebase يصله في رابط تسجيله** من `GET /config` — قيمٌ عامّةٌ بطبيعتها تعيش في عقد FCM لا في ملفٍّ هنا (كتطبيق الراكب). **وعنوانُ
 * الخادم معه** (`API_URL` المخبوز في البناء) فيُرسل «مقروء» بلا جلسة، برمز الإشعار نفسِه.
 *
 * **والإذنُ يُطلب بزرٍّ لا عند الإقلاع**: طلبٌ لم يطلبه أحدٌ يُرفض ثمّ لا يُسأل ثانية. **ومن منحه من قبل يُسجَّل بصمت** عند كلِّ فتح.
 *
 * ## الهاتف — تطبيقُ الإدارة نفسُه
 *
 * **الحزمةُ الجديدةُ تحمل ملحقاً أصليّاً** (`AdminAlertsPlugin.java`): قنواتُه الستُّ بأصواتها، وخدمةٌ ترسم الإشعارَ بأيقونته وأزراره.
 * **ويُسأل عنه لا يُفترض** — الشاشاتُ تُحمَّل من الخادم فقد تكون أحدثَ من الحزمة: حزمةٌ بلا الملحق يصلها الإشعارُ كما يرسمه النظام.
 */

import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";

import { API_URL } from "@/api/client";
import { registerDevice } from "@/api/endpoints";
import { deviceId, platform } from "@/lib/device";

export interface FirebaseWebConfig {
  apiKey: string;
  projectId: string;
  appId: string;
  messagingSenderId?: string;
}

/** **من عقد FCM كما ينشره `GET /config`** — و`null` بلا عقدٍ مفعَّل: غيابُه الوضعُ الافتراضيّ لا عطل. */
export function firebaseConfigOf(fcm: Record<string, string | undefined> | undefined): FirebaseWebConfig | null {
  if (!fcm?.project_id || !fcm.api_key || !fcm.app_id) return null;
  return {
    apiKey: fcm.api_key,
    projectId: fcm.project_id,
    appId: fcm.app_id,
    ...(fcm.sender_id ? { messagingSenderId: fcm.sender_id } : {}),
  };
}

export type BrowserAlertsState = "granted" | "denied" | "default" | "unsupported" | "unconfigured";

export function browserAlertsState(fcm: Record<string, string | undefined> | undefined): BrowserAlertsState {
  if (Capacitor.isNativePlatform()) return "unsupported";
  if (!("Notification" in window) || !("serviceWorker" in navigator)) return "unsupported";
  if (!firebaseConfigOf(fcm) || !fcm?.vapid_key) return "unconfigured";
  return Notification.permission;
}

/** **يسجّل المتصفّحَ لإشعارات المالك** — `ask` يطلب الإذنَ (من زرّ)، وبدونه يُسجَّل من منح الإذنَ سابقاً وحدَه. */
export async function enableBrowserAlerts(
  fcm: Record<string, string | undefined> | undefined,
  { ask }: { ask: boolean },
): Promise<BrowserAlertsState> {
  const state = browserAlertsState(fcm);
  if (state === "unsupported" || state === "unconfigured" || state === "denied") return state;
  const config = firebaseConfigOf(fcm)!;
  let permission: NotificationPermission = Notification.permission;
  if (permission === "default") {
    if (!ask) return "default";
    permission = await Notification.requestPermission();
  }
  if (permission !== "granted") return permission;

  const { initializeApp, getApps, getApp } = await import("firebase/app");
  const { getMessaging, getToken, isSupported, onMessage } = await import("firebase/messaging");
  if (!(await isSupported())) return "unsupported";
  const app = getApps().length ? getApp() : initializeApp({ ...config });
  const query = new URLSearchParams({ config: JSON.stringify(config), api: API_URL });
  // **النطاقُ الجذر** — هو نفسُه عاملُ تثبيت اللوحة على الهاتف (`manifest.webmanifest`)، ولا يخبّئ شيئاً
  const registration = await navigator.serviceWorker.register(`/alerts-sw.js?${query.toString()}`, { scope: "/" });
  const token = await getToken(getMessaging(app), {
    vapidKey: fcm!.vapid_key!,
    serviceWorkerRegistration: registration,
  }).catch(() => null);
  if (!token) return "denied";
  await registerDevice({ device_id: deviceId(), token, platform: platform() });
  // **واللوحةُ مفتوحةً لا يرسم العاملُ شيئاً** (Firebase يسلّمها للصفحة) — فيُسأل الجرسُ فوراً بدل انتظار دورته
  onMessage(getMessaging(app), () => window.dispatchEvent(new CustomEvent("taxo:admin-alert")));
  return "granted";
}

// ═════════════════════════ الهاتف — الملحقُ الأصليّ

interface AdminAlertsNative {
  /** إصدارُ قنوات الإدارة وخدمتها — `51` (`services/admin_alerts.ADMIN_NATIVE`) */
  version(): Promise<{ level: number }>;
  /** عنوانُ الخادم لزرِّ «مقروء» — **من البناء نفسِه** (`API_URL`) لا نسخةٌ في الحزمة */
  configure(options: { apiBase: string }): Promise<void>;
  /** **يرسم الإشعارَ على هذا الهاتف بلا FCM** — لصفحة المعاينة: الشكلُ والصوتُ قبل الطرح */
  preview(data: Record<string, string>): Promise<void>;
  addListener(
    event: "alertTap",
    listener: (data: { record_type?: string; record_id?: string; kind?: string; alert_id?: string }) => void,
  ): Promise<PluginListenerHandle>;
}

const native = registerPlugin<AdminAlertsNative>("AdminAlerts");

/** **ما يحمله هذا الهاتف** — `undefined` لحزمةٍ أقدمَ بلا الملحق أو للمتصفّح، فيُرسَل إليه كما اليوم. */
export async function adminNativeLevel(): Promise<number | undefined> {
  if (Capacitor.getPlatform() !== "android") return undefined;
  if (!Capacitor.isPluginAvailable("AdminAlerts")) return undefined;
  try {
    await native.configure({ apiBase: API_URL });
    const { level } = await native.version();
    return level || undefined;
  } catch {
    return undefined;
  }
}

/** **نقرةُ إشعارٍ رسمه الملحق** — تفتح سجلَّه. **والمسارُ يُشتقّ هنا** من نوعه ومعرّفه، لا يُقرأ من الإشعار. */
export async function listenToNativeAlertTaps(
  open: (alert: { record_type: string | null; record_id: string | null; kind: string }) => void,
): Promise<() => void> {
  if (!Capacitor.isPluginAvailable("AdminAlerts")) return () => undefined;
  const handle = await native.addListener("alertTap", (data) =>
    open({ record_type: data.record_type || null, record_id: data.record_id || null, kind: data.kind ?? "" }),
  );
  return () => void handle.remove();
}

export { deviceId };

/** **معاينةٌ على هذا الهاتف** — `false` في المتصفّح أو على حزمةٍ بلا الملحق، فيُرسم الزرُّ حيث يعمل وحدَه. */
export function canPreviewOnPhone(): boolean {
  return Capacitor.getPlatform() === "android" && Capacitor.isPluginAvailable("AdminAlerts");
}

export async function previewOnPhone(sample: { kind: string; tone: string; title: string; body: string }): Promise<void> {
  await native.preview({
    kind: sample.kind,
    tone: sample.tone,
    title: `معاينة · ${sample.title}`,
    body: sample.body,
    tag: `preview:${sample.kind}`,
    record_type: "",
    record_id: "",
  });
}
