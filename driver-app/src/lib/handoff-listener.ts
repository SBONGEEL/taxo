/** استقبالُ جلسةٍ منقولة — **قبل أن يُركَّب أيُّ مكوّن** (SPEC §23).
 *
 * **وليست شاشةً، وهذا قِيس لا رأي**: وُضعت أوّلاً مساراً (`/handoff`) داخل
 * `Boot`، و`Boot` يحجب الرسمَ حتى يجتمع `config` والجلسة — فالمسارُ الذي
 * يُنشئ الجلسةَ كان ينتظرها. مقيسٌ على S21: الرمزُ في `location.hash`،
 * و`/config` يجيب **200**، والترحيبيةُ **باقية**، والمبادلةُ لم تقع أبداً.
 *
 * فصارت المبادلةُ هنا: نداءٌ واحدٌ قبل React، والترحيبيةُ هي الانتظارُ المرئيّ
 * (وهي لذلك موجودة). ولا شاشةَ ثالثةً تُضاف لتقول «جارٍ».
 *
 * **وبابان لا باب**، وهذا قِيس أيضاً:
 *
 * | حالُ التطبيق | من أين يصل العنوان |
 * |---|---|
 * | يعمل سلفاً | `appUrlOpen` |
 * | **مُغلَق** (إقلاعٌ بارد) | `getLaunchUrl()` — و`appUrlOpen` **لا يُطلق** |
 *
 * والإقلاعُ الباردُ هو الحالُ الغالبة: من يبدّل نادراً يجد الآخرَ مغلقاً.
 *
 * **والفشلُ صامت** (قرارُ المالك): الزرُّ مُشغِّلٌ نجح فعلُه — فُتح التطبيق.
 * فرمزٌ منتهٍ أو مرفوضٌ يترك التطبيقَ يتولّى نفسَه بشاشته، بلا رسالةِ خطأ.
 */

import { App } from "@capacitor/app";

import { exchangeHandoff } from "@/api/endpoints";
import { tokens } from "@/api/client";

/** يقرأ الرمزَ من عنوان المخطط الخاصّ — أو لا شيء. */
function tokenOf(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.host === "handoff" ? parsed.searchParams.get("t") : null;
  } catch {
    return null; // عنوانٌ لا يُحلَّل — ولا يُسقط التطبيق
  }
}

async function adopt(url: string): Promise<void> {
  const token = tokenOf(url);
  if (!token) return;
  try {
    const { tokens: pair } = await exchangeHandoff(token);
    tokens.save(pair);
    // **يُعاد التحميلُ لا يُنقَل المسار**: الجلسةُ تُقرأ عند الإقلاع، وتبديلُها
    // تحت شجرةٍ مركَّبةٍ يترك شاشاتٍ رُسمت لصاحبٍ آخر
    window.location.replace("/");
  } catch {
    /* رمزٌ منتهٍ أو مرفوض — يتولّى التطبيقُ نفسَه، وبصمت */
  }
}

export function listenForHandoff(): void {
  void App.addListener("appUrlOpen", ({ url }) => void adopt(url));
  // **والإقلاعُ الباردُ يُسأل صراحةً** — لا يصله حدث
  void App.getLaunchUrl().then((launch) => {
    if (launch?.url) void adopt(launch.url);
  });
}
