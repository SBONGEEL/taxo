/** «شارك التطبيق» — **ورقةُ المشاركة في النظام** (اقتراحُ Testers Community وأمرُ المالك ٢٠٢٦-١٠-٢٧، `design/PLAY-TEST-LOG.md`).
 *
 * **ثلاثُ طبقاتٍ بترتيبها**: إضافةُ `@capacitor/share` في الغلاف (ورقةُ أندرويد الأصليّة — **و`WebView` لا يعرف `navigator.share`**)،
 * ثمّ `navigator.share` في متصفّحٍ يعرفه، ثمّ **الحافظة** حين لا ورقة — **وغلافٌ قديمٌ بلا الإضافة يقع على الحافظة لا على صمت**.
 *
 * **والرابطُ لكلِّ تطبيقٍ من حيث يُثبَّت فعلاً**: الراكبُ منشورٌ على Google Play، **والكبتنُ لم يُنشر بعدُ هناك** — فرابطُه صفحةُ التحميل
 * في موقعنا، ويصير رابطَ المتجر يومَ يُنشر (سطرٌ واحدٌ هنا).
 *
 * **ونسخةٌ واحدةٌ في التطبيقين، متطابقةٌ بايتاً** — والتطبيقُ يُمرَّر لا يُكتب فيها.
 */
import { Capacitor } from "@capacitor/core";
import { Share } from "@capacitor/share";

import { tr } from "@/lib/i18n";

type App = "rider" | "driver";

const LINK: Record<App, string> = {
  rider: "https://play.google.com/store/apps/details?id=ly.tajora.rider",
  driver: "https://taxo.tajora.ly/download",
};

function message(app: App): { title: string; text: string } {
  return app === "rider"
    ? { title: tr("TAXO — تطبيق الرحلات"), text: tr("جرّب TAXO: اطلب رحلتك، واعرف السعر قبل أن تؤكّد، وتابع كبتنك على الخريطة.") }
    : { title: tr("TAXO Driver — تطبيق الكبتن"), text: tr("اعمل كبتناً مع TAXO: الأجرة أمامك قبل القبول، وأرباحك ومحفظتك في مكانٍ واحد.") };
}

export type ShareOutcome = "shared" | "copied" | "cancelled" | "failed";

/** **مُلغاةٌ لا خطأ**: من أغلق الورقةَ بلا اختيارٍ قرّر — لا رسالةَ عطبٍ له. */
function cancelled(error: unknown): boolean {
  const text = String((error as { message?: string })?.message ?? error).toLowerCase();
  return text.includes("cancel") || text.includes("abort");
}

export async function shareApp(app: App): Promise<ShareOutcome> {
  const { title, text } = message(app);
  const url = LINK[app];
  if (Capacitor.isPluginAvailable("Share")) {
    try {
      await Share.share({ title, text, url, dialogTitle: tr("شارك التطبيق") });
      return "shared";
    } catch (error) {
      if (cancelled(error)) return "cancelled";
    }
  } else if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return "shared";
    } catch (error) {
      if (cancelled(error)) return "cancelled";
    }
  }
  try {
    await navigator.clipboard.writeText(`${text}\n${url}`);
    return "copied";
  } catch {
    return "failed";
  }
}

/** **ما يُقال بعد المحاولة** — ولا شيءَ لمن ألغى أو شارك (الورقةُ نفسُها قالت). */
export function shareNote(outcome: ShareOutcome): string | null {
  if (outcome === "copied") return tr("نُسخ رابط التطبيق — الصقه في أي محادثة.");
  if (outcome === "failed") return tr("تعذّرت المشاركة — جرّب مرة أخرى.");
  return null;
}
