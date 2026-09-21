/** تقاريرُ الأعطال من الجهاز — **ثلاثةُ أبوابٍ ومِصفاةٌ قبلها** (2026-09-20).
 *
 * **ولا حزمةَ طرفٍ ثالث**: الحمولةُ تُبنى هنا حقلاً حقلاً، فلا يُرسل إلا ما
 * كُتب اسمُه في هذا الملفّ. وحزمةٌ جاهزةٌ تجمع **كلَّ** ما تجده — تخزينَ
 * المتصفّح ورؤوسَ الطلبات ونصَّ الشاشة — ثمّ يُطلب منها أن تنسى؛ **وهذا
 * مقلوبٌ**: الأصلُ ألّا يُجمع، لا أن يُجمع ثمّ يُنسى.
 *
 * ## الأبوابُ الثلاثة
 *
 * `window.onerror` لما يُرمى ولا يُمسَك · `unhandledrejection` **لوعدٍ يُرفض
 * بلا ماسك، وهو الذي لا يظهر على شاشةٍ أصلاً** · وحدُّ الخطأ حين تسقط شجرةُ
 * React. ورابعٌ بإصبع صاحبه: زرُّ «أرسل تقريراً».
 *
 * ## ومعها الفُتات — **ما كان يفعله، لا ما انكسر** (٢٠٢٦-٠٩-٢١)
 *
 * الأبوابُ الأربعةُ تقول **أين** انكسر؛ و`lib/breadcrumbs.ts` يمسك الخطواتِ
 * السابقة — تنقّلاً ونداءَ خلفيةٍ بفعله وحالته — **بلا جسمٍ ولا استعلام**.
 * فيصير «كيف وصل إلى هنا» مقروءاً بدل أن يُخمَّن.
 *
 * ## وما يمنع هذا الملفَّ من أن يصير هو العطب
 *
 * مُبلِّغٌ عن الأعطال يعمل داخل عطبٍ قائم، **فكلُّ سطرٍ فيه يفترض أن ما حوله
 * منهار**:
 *
 * - **سقفُ جلسة** (خمسةُ إرسالاتٍ تلقائية): حلقةُ رسمٍ تُطلق مئاتِ الأخطاء في
 *   الثانية، **وخمسةٌ منها تقول ما تقوله خمسُمئة**.
 * - **جمعُ المتكرر**: العطبُ نفسُه في الجلسة نفسِها يزيد `repeat` ولا يُضيف
 *   صفّاً — **أربعون تُرسَل مرّةً واحدةً تحمل أربعين**.
 * - **٤٢٩ تعني «توقّف»**: إعادةُ المحاولة على سدٍّ هي كيف يصير هاتفٌ واحدٌ
 *   إغراقاً للخادم.
 * - **وكلُّ لمسةٍ لـ`localStorage` في `try`**: تخزينٌ ممتلئٌ أو محجوبٌ يرمي،
 *   **ورميةٌ داخل معالج خطأٍ تبتلع الخطأ الأصليّ** وتترك صاحبَها بلا شيء.
 * - **وسقفُ حجمٍ للطابور**: طابورٌ ينمو بلا حدٍّ يملأ التخزين فيكسر حفظَ
 *   التوكن نفسِه — فيُخرِج المُبلِّغُ صاحبَه من حسابه.
 *
 * ## والتعطيلُ بيد صاحبه، والزرُّ لا يُعطَّل معه
 *
 * الإرسالُ التلقائيُّ **مُشعَلٌ افتراضاً** ويُطفئه صاحبُه من الإعدادات —
 * وهي قاعدةُ `lib/sound.ts` نفسُها: «ميزةٌ افتراضيةٌ يُطفئها صاحبُها، لا
 * ميزةٌ تنتظر إشعالاً». **وزرُّ «أرسل تقريراً» يعمل ولو أُطفئ**: من يضغطه
 * يقصد الإرسالَ في تلك اللحظة، وإطفاءُ القناة الخلفية ليس رفضاً للتبليغ.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { postErrorReport } from "@/api/endpoints";
import { type Crumb, maskPath, recentCrumbs, watchRoutes } from "@/lib/breadcrumbs";
import { deviceId, platform } from "@/lib/device";
import { lastRequestId } from "@/lib/request-id";

export type CrashApp = "rider" | "driver" | "panel";

const PREF_KEY = "taxo.crash_reports";
const QUEUE_KEY = "taxo.error_queue";

/** طابورٌ قصيرٌ بحدَّين — عدداً وحجماً */
const MAX_QUEUED = 10;
const MAX_QUEUE_BYTES = 64 * 1024;
/** محاولاتٌ لتقريرٍ واحد قبل أن يُسقَط */
const MAX_ATTEMPTS = 3;
/** **سقفُ الجلسة** — وما بعده لا يُرسل تلقائياً، والزرُّ يبقى */
const SESSION_SEND_CAP = 5;

type Report = {
  app: CrashApp;
  kind: "error" | "rejection" | "boundary" | "user_report";
  platform: "android" | "ios" | "web";
  release?: string;
  channel?: string;
  os_version?: string;
  device_hash: string;
  route?: string;
  name: string;
  message: string;
  stack?: string;
  component_stack?: string;
  breadcrumbs?: Crumb[];
  occurred_at: string;
  online: boolean;
  repeat: number;
  request_id?: string;
  note?: string;
};

type Queued = { report: Report; attempts: number };

let currentApp: CrashApp | null = null;
let sessionSends = 0;
let halted = false;
/** بصمةٌ محلّيةٌ للجمع داخل الجلسة — **للتكرار لا للتجميع في الخادم** */
const seenThisSession = new Map<string, Queued>();

// ------------------------------------------------------------ التفضيل

/** **الغيابُ يعني مُشعَلاً** — والخطأُ في القراءة يعني مُشعَلاً أيضاً. */
export function crashReportsEnabled(): boolean {
  try {
    return localStorage.getItem(PREF_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setCrashReportsEnabled(on: boolean): void {
  try {
    localStorage.setItem(PREF_KEY, on ? "on" : "off");
  } catch {
    /* تخزينٌ محجوب — التفضيلُ يضيع ولا يسقط شيء */
  }
}

// ------------------------------------------------------------- البناء

/** قالبُ المسار — **ولا يُرسل مُعرِّفٌ ولو كان في شريط العنوان**.
 *
 * **والتقنيعُ بيتٌ واحدٌ الآن** (`lib/breadcrumbs.maskPath`): كان هنا نسخةٌ
 * منه ونسخةٌ في الفُتات، **ونسختان تفترقان أوّلَ تعديل** — فيُقنَّع المسارُ
 * في مكانٍ ويُسرَّب في الآخر.
 */
function routeTemplate(): string {
  try {
    return maskPath(window.location.pathname);
  } catch {
    return "/";
  }
}

/** `sha256` لمُعرِّف الجهاز — **ويُخفق مُغلَقاً**.
 *
 * حيث لا `crypto.subtle` (سياقٌ غيرُ آمن) **لا يُرسل شيء**: إرسالُ المُعرِّف
 * خاماً «حتى لا يضيع التقرير» هو بعينه ما بُني هذا ليمنعه.
 */
async function deviceHash(): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  try {
    const digest = await subtle.digest(
      "SHA-256",
      new TextEncoder().encode(deviceId()),
    );
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("")
      .slice(0, 32);
  } catch {
    return null;
  }
}

async function releaseTag(): Promise<string | undefined> {
  if (!Capacitor.isNativePlatform()) return undefined;
  try {
    const info = await App.getInfo();
    return `${info.version}+${info.build}`.slice(0, 40);
  } catch {
    return undefined;
  }
}

function signatureOf(name: string, message: string, route: string): string {
  return `${name}|${message.slice(0, 120)}|${route}`;
}

async function build(
  kind: Report["kind"],
  error: unknown,
  componentStack: string | null,
  note?: string,
): Promise<Report | null> {
  const hash = await deviceHash();
  if (!hash || !currentApp) return null;

  const raw = error instanceof Error ? error : null;
  const crumbs = recentCrumbs();
  const name = (raw?.name || "Error").slice(0, 200);
  const message = (raw?.message || String(error ?? "")).slice(0, 2_000) || "—";

  return {
    app: currentApp,
    kind,
    platform: platform(),
    release: await releaseTag(),
    // **ما يعرفه العميلُ حقّاً**: وضعُ البناء، لا قناةُ النشر — تلك لا تبلغ
    // الحزمةَ اليوم (`TAXO_CHANNEL` متغيّرُ بناءٍ لا `VITE_`)
    channel: import.meta.env.MODE.slice(0, 20),
    os_version: navigator.userAgent.slice(0, 60),
    device_hash: hash,
    route: routeTemplate(),
    name,
    message,
    stack: raw?.stack?.slice(0, 8_000),
    component_stack: componentStack?.slice(0, 8_000) ?? undefined,
    // **ما كان يفعله قبل أن يقع** — وأثرُ المكدَّس لا يقوله أبداً.
    // **ويُحذف الحقلُ إن كان فارغاً** ولا يُرسل `[]`: مصفوفةٌ فارغةٌ تُقرأ
    // «جُمع فلم يكن شيء»، والغيابُ يُقرأ «لم يُجمع» — وهما خبران مختلفان.
    breadcrumbs: crumbs.length ? crumbs : undefined,
    occurred_at: new Date().toISOString(),
    online: navigator.onLine,
    repeat: 1,
    request_id: lastRequestId() ?? undefined,
    note,
  };
}

// ------------------------------------------------------------ الطابور

function readQueue(): Queued[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    return raw ? (JSON.parse(raw) as Queued[]) : [];
  } catch {
    return [];
  }
}

function writeQueue(items: Queued[]): void {
  try {
    let kept = items.slice(-MAX_QUEUED);
    // **الحجمُ حدٌّ ثانٍ**: عشرةُ تقاريرَ بأثرٍ طويلٍ تتجاوز ما يتجاوزه مئة قصير
    while (kept.length > 1 && JSON.stringify(kept).length > MAX_QUEUE_BYTES) {
      kept = kept.slice(1);
    }
    localStorage.setItem(QUEUE_KEY, JSON.stringify(kept));
  } catch {
    /* ممتلئٌ أو محجوب — يُترك الطابورُ كما هو ولا يسقط شيء */
  }
}

function enqueue(report: Report): void {
  writeQueue([...readQueue(), { report, attempts: 0 }]);
}

/** يُفرِغ الطابورَ — **ويتوقّف عند أوّل ٤٢٩**. */
async function flush(): Promise<void> {
  if (halted || !navigator.onLine) return;
  const pending = readQueue();
  if (pending.length === 0) return;

  const remaining: Queued[] = [];
  for (const item of pending) {
    if (halted) {
      remaining.push(item);
      continue;
    }
    try {
      await postErrorReport(item.report);
    } catch (caught) {
      const status = (caught as { status?: number })?.status ?? 0;
      if (status === 429) {
        // **سدٌّ لا عطب**: يُوقَف الإرسالُ لبقية الجلسة ويبقى ما لم يُرسل
        halted = true;
        remaining.push(item);
        continue;
      }
      // **٤xx لا تصير صالحةً بالإعادة** — تُسقَط ولا تُعاد
      if (status >= 400 && status < 500) continue;
      const attempts = item.attempts + 1;
      if (attempts < MAX_ATTEMPTS) remaining.push({ ...item, attempts });
    }
  }
  writeQueue(remaining);
}

// -------------------------------------------------------------- الأبواب

function capture(
  kind: Report["kind"],
  error: unknown,
  componentStack: string | null,
): void {
  if (!currentApp || halted || !crashReportsEnabled()) return;
  if (sessionSends >= SESSION_SEND_CAP) return;

  void (async () => {
    const report = await build(kind, error, componentStack);
    if (!report) return;

    // **المتكرِّرُ يزيد عدّاداً ولا يضيف صفّاً**
    const signature = signatureOf(report.name, report.message, report.route ?? "");
    const already = seenThisSession.get(signature);
    if (already) {
      already.report.repeat += 1;
      return;
    }
    seenThisSession.set(signature, { report, attempts: 0 });

    sessionSends += 1;
    enqueue(report);
    await flush();
  })();
}

/** حدُّ الخطأ ينادي هذه حين تسقط شجرةُ React. */
export function reportBoundary(
  error: unknown,
  componentStack: string | null,
): void {
  capture("boundary", error, componentStack);
}

/** زرُّ «أرسل تقريراً» — **يعمل ولو أُطفئ التلقائيُّ**، ولا يمرّ بسقف الجلسة. */
export async function sendUserReport(
  error: unknown,
  componentStack: string | null,
  note: string,
): Promise<boolean> {
  const report = await build("user_report", error, componentStack, note.trim());
  if (!report) return false;
  try {
    await postErrorReport(report);
    return true;
  } catch {
    // **يُحفظ ليُرسل لاحقاً** — من كتب جملةً لا تُرمى لأن الشبكة سقطت
    enqueue(report);
    return false;
  }
}

/** يُركَّب مرّةً عند الإقلاع — **قبل أيِّ شاشة**. */
export function installCrashReports(app: CrashApp): void {
  if (currentApp) return;
  currentApp = app;

  // **الفُتاتُ يبدأ قبل أوّل شاشة** — ومن يركّبه بعد التنقّل يفقد أوّلَه،
  // وهو الخطوةُ التي يُبنى عليها الباقي.
  watchRoutes();

  window.addEventListener("error", (event) => {
    capture("error", event.error ?? event.message, null);
  });

  window.addEventListener("unhandledrejection", (event) => {
    capture("rejection", event.reason, null);
  });

  // **وحين تعود الشبكة يُفرَّغ ما انتظرها**
  window.addEventListener("online", () => {
    void flush();
  });

  void flush();
}
