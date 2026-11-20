/** **مركزُ الأذونات** (SPEC §١٠٣ المرحلة A/28، أمرُ المالك ٢٠٢٦-١١-١٦) — **منسوخٌ بايتاً في التطبيقين** (`check:permissions-center`).
 *
 * المنطقُ هنا خالصٌ يُختبر بلا هاتف (`tests/permissions-center.test.ts`)، والجسرُ إلى ملحق `Permissions` الأصليّ في أسفله.
 * **والصفوفُ من الملحق لا من هنا**: الملحقُ يعيد ما أعلنه بيانُ التطبيق وحدَه — فلا يُعرض إذنٌ لا يستعمله التطبيق، ولا يُخترع حال.
 * و`unknown` (التشغيلُ التلقائيّ — لا يقرؤه أندرويد لأحد) **لا يُعدّ مطفأً**: لا شارةَ على ما لا يُعرف.
 */
import { Capacitor, registerPlugin } from "@capacitor/core";

export type PermissionKey =
  | "location"
  | "location_background"
  | "notifications"
  | "overlay"
  | "battery"
  | "autostart"
  | "full_screen"
  | "microphone";
export type PermissionState = "on" | "off" | "unknown";
export type AppKind = "driver" | "rider";
export interface PermissionRow {
  key: PermissionKey;
  state: PermissionState;
}
export type OpenedAt = "exact" | "vendor" | "details" | "none";

interface Meta {
  label: string;
  why: Record<AppKind, string>;
  /** خطواتٌ قصيرةٌ حين لا تُفتح الصفحةُ الدقيقة فنقع على «تفاصيل التطبيق» */
  steps: string[];
}

export const PERMISSION_META: Record<PermissionKey, Meta> = {
  location: {
    label: "الموقع",
    why: { driver: "لتصلك الطلباتُ القريبة ويرى الراكبُ مكانك.", rider: "لنعرف نقطةَ انطلاقك ونُريك الكباتنَ القريبين." },
    steps: ["افتح «الأذونات»", "اختر «الموقع»", "اختر «السماح أثناء استخدام التطبيق»"],
  },
  location_background: {
    label: "الموقع في الخلفية",
    why: { driver: "ليبقى موقعُك يصل وأنت متّصلٌ والتطبيقُ مغلق — وإلا لا تصلك الطلبات.", rider: "" },
    steps: ["افتح «الأذونات»", "اختر «الموقع»", "اختر «السماح طوال الوقت»"],
  },
  notifications: {
    label: "الإشعارات",
    why: { driver: "لتصلك الطلباتُ والرسائلُ والمكالمات.", rider: "لتعرف متى وصل الكبتن ورسائلَه ومكالماته." },
    steps: ["افتح «الإشعارات»", "فعّل «السماح بالإشعارات»"],
  },
  overlay: {
    label: "الظهور فوق التطبيقات",
    why: { driver: "لتظهر الفقاعةُ وطلبُ الرحلة وأنت في تطبيقٍ آخر.", rider: "" },
    steps: ["افتح «إعدادات متقدّمة» أو «الظهور فوق التطبيقات»", "فعّل TAXO كبتن"],
  },
  battery: {
    label: "الاستثناء من توفير البطارية",
    why: { driver: "كي لا يوقف الهاتفُ التطبيقَ وأنت متّصل.", rider: "" },
    steps: ["افتح «البطارية»", "اختر «غير مقيّد» أو «بلا قيود»"],
  },
  autostart: {
    label: "التشغيل التلقائي",
    why: { driver: "بعض الهواتف توقف التطبيقَ في الخلفية ما لم يُسمح له بالتشغيل التلقائيّ.", rider: "" },
    steps: ["افتح «البطارية» أو «إدارة التطبيقات»", "اختر «التشغيل التلقائي»", "فعّل TAXO كبتن"],
  },
  full_screen: {
    label: "تنبيه الطلب بملء الشاشة",
    why: { driver: "ليظهر الطلبُ على شاشة القفل كالمكالمة الواردة.", rider: "لتظهر المكالمةُ الواردةُ على شاشة القفل." },
    steps: ["افتح «الإشعارات بملء الشاشة»", "فعّل التطبيق"],
  },
  microphone: {
    label: "الميكروفون",
    why: { driver: "للمكالمة مع الراكب داخل التطبيق.", rider: "للمكالمة مع الكبتن داخل التطبيق والبحث بالصوت." },
    steps: ["افتح «الأذونات»", "اختر «الميكروفون»", "اختر «السماح أثناء استخدام التطبيق»"],
  },
};

/** **الأساسيّة** — ما بغيره لا يعمل التطبيقُ كما يُنتظر؛ منها تُحسب الشارةُ والمرورُ الأوّلُ والبلاغ */
export const ESSENTIAL: Record<AppKind, readonly PermissionKey[]> = {
  driver: ["location", "location_background", "notifications", "overlay", "battery", "full_screen"],
  rider: ["location", "notifications"],
};

/** ترتيبُ العرض — الأساسيّةُ أوّلاً بترتيبها، ثمّ الباقي */
export function ordered(rows: readonly PermissionRow[], app: AppKind): PermissionRow[] {
  const rank = (key: PermissionKey) => {
    const at = ESSENTIAL[app].indexOf(key);
    return at < 0 ? 100 + Object.keys(PERMISSION_META).indexOf(key) : at;
  };
  return [...rows].filter((row) => PERMISSION_META[row.key]).sort((a, b) => rank(a.key) - rank(b.key));
}

/** **الأساسيّةُ المطفأة** — `unknown` لا يُعدّ، وما لم يُعلنه البيانُ غائبٌ أصلاً */
export function essentialsOff(rows: readonly PermissionRow[], app: AppKind): PermissionKey[] {
  return ordered(rows, app)
    .filter((row) => row.state === "off" && ESSENTIAL[app].includes(row.key))
    .map((row) => row.key);
}

/** **بصمةُ البلاغ** — يُبلَّغ حين تتغيّر وحدَها، فالكتابةُ نادرة */
export function reportKey(off: readonly PermissionKey[]): string {
  return [...off].sort().join(",");
}

/** **الشرحُ قبل الإذن الحسّاس** (الخطوة c من الأمر) — هذه تُشرح قبل أن يُطلب النظامُ أو تُفتح صفحتُه */
export const SENSITIVE: ReadonlySet<PermissionKey> = new Set(["location_background", "overlay", "battery", "full_screen", "microphone"]);

// ── الجسر ───────────────────────────────────────────────────────────────

interface NativePermissions {
  status(): Promise<{ rows: PermissionRow[]; brand: string; sdk: number }>;
  request(options: { key: PermissionKey }): Promise<unknown>;
  open(options: { key: PermissionKey }): Promise<{ opened?: OpenedAt }>;
}

const native = registerPlugin<NativePermissions>("Permissions");

/** **الغلافُ يحمل الملحق؟** — الأقدمُ لا، فلا صفحةَ ولا شارةَ ولا بلاغ: التطبيقُ كما كان حرفاً */
export function centerAvailable(): boolean {
  return Capacitor.isNativePlatform() && ["android", "ios"].includes(Capacitor.getPlatform()) && Capacitor.isPluginAvailable("Permissions");
}

export async function readPermissions(): Promise<PermissionRow[]> {
  if (!centerAvailable()) return [];
  try {
    return (await native.status()).rows ?? [];
  } catch {
    return [];
  }
}

/** يطلب الإذنَ داخل التطبيق إن كان إذنَ تشغيل، وإلا يفتح صفحتَه — ويعيد أين وقع الفتح (أو `null` إن طُلب داخلياً) */
export async function askPermission(key: PermissionKey): Promise<OpenedAt | null> {
  if (!centerAvailable()) return "none";
  try {
    const answer = (await native.request({ key })) as { opened?: OpenedAt } | undefined;
    return answer?.opened ?? null;
  } catch {
    return "none";
  }
}

export async function openPermission(key: PermissionKey): Promise<OpenedAt> {
  if (!centerAvailable()) return "none";
  try {
    return (await native.open({ key })).opened ?? "none";
  } catch {
    return "none";
  }
}

// ── «لم نتمكن من تحديد موقعك» (SPEC §١٠٩-ج) ─────────────────────────────

/** **إذنُ الموقع وزرُّ الموقع في الهاتف معاً** — الثاني ليس إذناً فلا صفَّ له في المركز (`ordered` يُسقط ما لا شرحَ له)؛
 *  والغلافُ الأقدمُ لا يقوله فيبقى `unknown` — **ولا يُخمَّن**. */
export async function readLocationSignals(): Promise<{ permission: PermissionState; services: PermissionState }> {
  const unknown = { permission: "unknown" as PermissionState, services: "unknown" as PermissionState };
  if (!centerAvailable()) return unknown;
  try {
    const rows = ((await native.status()).rows ?? []) as unknown as { key: string; state: PermissionState }[];
    const of = (key: string) => rows.find((row) => row.key === key)?.state ?? "unknown";
    return { permission: of("location"), services: of("location_services") };
  } catch {
    return unknown;
  }
}

/** **صفحةُ «الموقع» في إعدادات الهاتف** حيث زرُّ GPS — في الغلاف الذي يعرفها وحدَه (`readLocationSignals().services` معروف) */
export async function openLocationServices(): Promise<OpenedAt> {
  if (!centerAvailable()) return "none";
  try {
    return (await native.open({ key: "location_services" as PermissionKey })).opened ?? "none";
  } catch {
    return "none";
  }
}
