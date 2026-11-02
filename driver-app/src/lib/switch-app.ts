/** زرُّ «كن راكباً» — **القرارُ هنا، لا في الشاشة** (SPEC §23، وأمرُ المالك ٢٠٢٦-١١-٠٢).
 *
 * سؤالان يقرّران ما يقع: **أتطبيقُ الراكب مثبَّتٌ على هذا الهاتف؟** و**أيملك هذا الحسابُ دورَ الراكب؟**
 *
 * | الحال | ما يقع |
 * |---|---|
 * | غيرُ مثبَّت | يُفتح رابطُ تنزيله — **من `GET /config` لا من هنا** (حقلُ المتجر في «الموقع»؛ تطبيقُ الراكب منشورٌ في Play) |
 * | مثبَّت، والحسابُ بلا دور الراكب | يُفتح بتسليمٍ يحمل **الرقمَ لا الجلسة** — فيفتح الآخرُ دخولَه ورقمُه مكتوب، وكلمةُ المرور تضيف الملفّ (§21.6) |
 * | مثبَّت، والحسابُ يملكه | يُفتح بجلسته — بلا كلمةِ مرورٍ ولا رمز |
 * | في رحلةٍ جارية | يُقال **لماذا** لا يعمل الآن — والنصُّ من الخلفية |
 *
 * **ولا رمزَ تحقّقٍ في أيٍّ منها**: الحسابُ قائمٌ ورقمُه مُثبَتٌ منذ سجّل، فرمزٌ يُرسل هنا رسالةٌ لا يحتاجها أحد.
 *
 * **والفتحُ بـ`AppLauncher` لا بـ`intent://`** — وهذا قِيس لا افتُرض: عنوانُ `intent://` سلوكٌ خاصٌّ بمتصفح كروم، **ولا يفعل شيئاً
 * داخل WebView**؛ قِيس على S21 فبقي تطبيقُ الراكب في المقدمة ولم يُفتح شيء. و`canOpenUrl` يعطي «غير مثبَّت» جواباً **حتمياً من
 * النظام** يُسأل **قبل** المحاولة، فلا يرمش شيءٌ على الشاشة ولا يُخمَّن بعد مهلة.
 *
 * **والرمزُ يسافر في مخططٍ خاصٍّ لا يبلغ خادماً**: لا نداءَ شبكةٍ يحمله ولا سجلَّ وسيطٍ يقيّده. وعمرُه قصيرٌ واستعمالُه واحد.
 * **ونسختُه في تطبيق الراكب** بالاتجاه المعاكس.
 */

import { App } from "@capacitor/app";
import { AppLauncher } from "@capacitor/app-launcher";
import { Capacitor } from "@capacitor/core";
import { useState } from "react";

import { startHandoff } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { AppLink } from "@/api/types";
import { useConfig } from "@/lib/config";
import { useSession } from "@/lib/session";
import { tr } from "@/lib/i18n";

/** حزمةُ هذا التطبيق كما يُنشر — **ولاحقةُ القناة تُقرأ ممّا يزيد عليها** (`.test` للتجريبيّ، وما يُضاف بعده). */
const OWN_PACKAGE = "ly.tajora.driver";

/** **حزمةُ الأخ في القناة نفسِها** — `ly.tajora.rider` للعامّ، و`ly.tajora.rider.test` بجوار `ly.tajora.driver.test`.
 *
 * **والخادمُ يعطي حزمةَ المنتج لا القناة**: لا يعرف أيَّ نسخةٍ تسأله، والنسختان تتعايشان على الهاتف الواحد (`channels.json`) —
 * فسؤالُ التجريبيِّ عن حزمة العامّ يقول «غير مثبَّت» وأخوه التجريبيُّ بجواره.
 */
async function siblingPackage(base: string): Promise<string> {
  try {
    const { id } = await App.getInfo();
    return id.startsWith(OWN_PACKAGE) ? base + id.slice(OWN_PACKAGE.length) : base;
  } catch {
    return base;
  }
}

/** **أمثبَّتٌ تطبيقُ الراكب؟** — والمتصفّحُ لا يملك جواباً، فيُقرأ «لا» ويُعطى رابطَ التنزيل. */
export async function riderInstalled(link: AppLink): Promise<boolean> {
  if (!Capacitor.isNativePlatform()) return false;
  // **`canOpenUrl` على أندرويد يأخذ اسمَ الحزمة لا عنواناً** — قِيس على S21: بتمرير العنوان يسجّل المكوّنُ «Package name
  // 'taxo-…://handoff' not found». **وعلى iOS العكس**: لا أسماءَ حزمٍ هناك، و`canOpenURL` يسأل عن **مخطّط** مُصرَّحٍ به في
  // `LSApplicationQueriesSchemes` — وبغيره يعيد false عن مثبَّت (٢٠٢٦-٠٩-٢٩)
  const probe = Capacitor.getPlatform() === "ios" ? "taxo-rider://" : await siblingPackage(link.package);
  try {
    return (await AppLauncher.canOpenUrl({ url: probe })).value;
  } catch {
    return false;
  }
}

/** يفتح صفحةَ التنزيل — **تطبيقُ المتجر أوّلاً إن كان الرابطُ رابطَ Play**، والصفحةُ نفسُها إن لم يُفتح (أمرُ المالك).
 *
 * **و`completed` هو الجواب لا الاستثناء**: `AppLauncher.openUrl` على أندرويد يلتقط «لا تطبيقَ لهذا العنوان» ويعيد `false` —
 * فهاتفٌ بلا متجر يصل الصفحةَ نفسَها ولا يبقى زرُّه بلا أثر.
 */
export async function openDownload(url: string): Promise<void> {
  if (!Capacitor.isNativePlatform()) {
    window.open(url, "_blank", "noopener");
    return;
  }
  const id = playId(url);
  if (id && Capacitor.getPlatform() === "android") {
    try {
      if ((await AppLauncher.openUrl({ url: `market://details?id=${encodeURIComponent(id)}` })).completed) return;
    } catch {
      /* لا متجرَ على هذا الهاتف — فالصفحة */
    }
  }
  await AppLauncher.openUrl({ url }).catch(() => undefined);
}

/** معرِّفُ الحزمة من رابط Play — أو لا شيء لرابطٍ آخر (الموقعُ الرسميّ). */
function playId(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.hostname === "play.google.com" ? parsed.searchParams.get("id") : null;
  } catch {
    return null;
  }
}

/** رسالةُ المنع كما كتبتها الخلفية — ولا تُكتب هنا عربيةٌ ثانية (§17). */
export function blockedReason(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "handoff_blocked_by_active_work") {
    return error.message;
  }
  return null;
}

/** **زرُّ «كن راكباً» — نصُّه وظهورُه وضغطُه**، بيتٌ واحد.
 *
 * **والكلمةُ هنا «راكب/سائق» بقرار المالك وحدَه** (٢٠٢٦-١١-٠٢): «كبتن» تبقى في كلِّ موضعٍ آخرَ من التطبيق كما هي، وهذا الزرُّ
 * وحدَه يقول «التبديل إلى الراكب»، **وبصيغة المؤنّث لصاحبة الحساب** حين يُعرف جنسُها.
 */
export function useBecomeRider(): {
  /** **يُرسم في سوقٍ مفتوحٍ وحدَه** — الأردن والجزائر اليوم، **وليبيا مخفيّة** (أمرُ المالك) */
  visible: boolean;
  label: string;
  sub: string;
  busy: boolean;
  blocked: string | null;
  press: () => Promise<void>;
} {
  const { config } = useConfig();
  const { user } = useSession();
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);

  const link = config?.app_links?.rider ?? null;
  const market = config?.countries.find((entry) => entry.country_code === user?.country_code);
  const visible = Boolean(user && link && market?.status === "open");
  const both = Boolean(user?.roles.includes("rider"));
  const female = user?.gender === "female";

  const label = both
    ? female ? tr("التبديل إلى الراكبة") : tr("التبديل إلى الراكب")
    : female ? tr("كوني راكبة") : tr("كن راكباً");
  const sub = both
    ? tr("حسابك نفسُه في تطبيق Taxo — بلا تسجيل دخول")
    : female
      ? tr("اطلبي مشاويرك من Taxo — برقمك نفسِه، بلا حسابٍ جديد")
      : tr("اطلب مشاويرك من Taxo — برقمك نفسِه، بلا حسابٍ جديد");

  async function press() {
    if (!link || busy) return;
    setBusy(true);
    setBlocked(null);
    try {
      if (!(await riderInstalled(link))) {
        await openDownload(link.download_url);
        return;
      }
      // **ولا يُطلب الرمزُ إلا عند الضغط**: عمرُه قصير، فطلبُه عند رسم الشاشة يجعله ميتاً قبل أن يُضغط
      let token = "";
      try {
        token = (await startHandoff()).token;
      } catch (error) {
        // **إلا المنعَ المعلن**: «أنهِ رحلتك أولاً» رفضٌ مقصودٌ له سببٌ يُقال — **وغيرُه يفتح التطبيقَ بلا رمز** فيتولّاه بشاشته
        if (blockedReason(error)) throw error;
      }
      await AppLauncher.openUrl({ url: `taxo-rider://handoff?t=${encodeURIComponent(token)}` });
    } catch (caught) {
      setBlocked(blockedReason(caught));
    } finally {
      setBusy(false);
    }
  }

  return { visible, label, sub, busy, blocked, press };
}
