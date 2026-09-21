/** حزمةٌ كسولةٌ لا تصل بعد رفعٍ — **إعادةٌ واحدةٌ لا حلقة** (٢٠٢٦-٠٩-٢١).
 *
 * ## العطبُ الذي بُني له — مقيسٌ لا مفترَض
 *
 * **كلُّ بناءٍ يُدوِّر بصماتِ حزمه**، وقِيس أنّ **تغييرَ محرفٍ واحدٍ في نصٍّ
 * داخل شاشةٍ واحدة بدّل بصماتِ ٦٠ ملفّاً من ٦٩** — لأن تغيُّرَ بصمةٍ يُدوِّر
 * بصماتِ كلِّ من يستوردها. **والخادمُ لا يُبقي من البناء السابق شيئاً**
 * (كلُّ ملفّات `assets/` بختمٍ زمنيٍّ واحدٍ هو لحظةُ الرفع).
 *
 * **فمن فتح التطبيقَ قبل الرفع ثمّ تنقّل بعده** يطلب حزمةً باسمٍ لم يعد
 * موجوداً، فيجيب nginx **٤٠٤** ويرمي المتصفّحُ
 * `TypeError: Failed to fetch dynamically imported module`. **وأُعيد إنتاجُه
 * بالبناء مرّتين والتنقّلِ عبرهما**، وجاءت الرسالةُ حرفاً بحرف كالتي أمسكها
 * الإنتاج.
 *
 * **والشاشةُ تبقى على ما كانت والعنوانُ يتغيّر** — لأن `Suspense` ينتظر وعداً
 * لن يُحلّ. **فلا رسالةَ ولا بياضٌ حتى**: تنقّلٌ لا يقع، وهو أسوأُ من انهيارٍ
 * يُرى.
 *
 * ## والعلاجُ إعادةٌ واحدة — **وثلاثةُ أشياءَ تمنعها أن تصير حلقة**
 *
 * ١. **الرايةُ في `sessionStorage`**: تنجو من الإعادة نفسِها. ومتغيّرٌ في
 *    الذاكرة يُمحى بالإعادة **فيدور إلى الأبد**، و`localStorage` يبقى بعد
 *    إغلاق اللسان **فيمنع إصلاحاً مشروعاً بعد أسبوع**.
 * ٢. **ومؤقّتةٌ بعشر ثوانٍ**: رفعٌ ثانٍ بعد ساعةٍ يستحقّ إعادةً ثانية،
 *    **ورايةٌ أبديّةٌ تحبس صاحبَها على عطبٍ زال**.
 * ٣. **ومفتاحُها عنوانُ الحزمة الساقطة** — يُقرأ من نصِّ الخطأ نفسِه. فسقوطُ
 *    حزمةٍ لا يمنع إصلاحَ أخرى، **ولا يحتاج كلُّ موضعِ نداءٍ أن يُسمّي نفسَه**.
 *
 * **وإن سقطت بعد الإعادة تُرمى ولا تُعاد**: حدُّ الخطأ يلتقطها فيقول شيئاً
 * مفهوماً. **وشاشةٌ تقول «حدث خطأ» أصدقُ من إعادةٍ لا تنتهي.**
 *
 * ## وما لا يفعله — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * **لا يحرس من يعمل**: من يملأ نموذجاً أو في رحلةٍ قائمةٍ **تُعاد صفحتُه تحته**
 * فيضيع ما لم يُرسَل. **ولذلك بُني معه النصفُ الثاني على الخادم** — إبقاءُ حزم
 * البناء السابق سبعةَ أيام (`scripts/deploy.sh`) — **فالإعادةُ لا تقع أصلاً
 * لمن كان بينهما**. وهذا الملفُّ هو الشبكةُ الأخيرةُ لا الأولى.
 */

import { lazy } from "react";
import type { ComponentType } from "react";

/** **مدّةُ الرايةِ**: أقصرُ من أن تحبس، وأطولُ من دورةِ إعادةٍ واحدة. */
const RETRY_WINDOW_MS = 10_000;

const PREFIX = "taxo.chunk-retry:";

/** **أسماءُ ثلاثةِ متصفّحاتٍ لعطبٍ واحد** — ولا يُفترض أحدُها.
 *
 * Chrome: `Failed to fetch dynamically imported module` ·
 * Firefox: `error loading dynamically imported module` ·
 * Safari: `Importing a module script failed`.
 * **ومن أمسك واحداً فقط ترك ثلثَي المستخدمين بلا علاج.**
 */
const CHUNK_ERROR =
  /failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed/i;

function isChunkError(error: unknown): boolean {
  return CHUNK_ERROR.test(String((error as Error | null)?.message ?? ""));
}

/** عنوانُ الحزمة الساقطة من نصِّ الخطأ — **وهو المفتاحُ بلا أن يُسمّيه أحد**. */
function chunkKey(error: unknown): string {
  const message = String((error as Error | null)?.message ?? "");
  const url = /https?:\/\/[^\s)]+/.exec(message)?.[0];
  return PREFIX + (url ?? "unknown");
}

/** **وكلُّ لمسةٍ للتخزين في `try`**: محجوبٌ أو ممتلئٌ يرمي، **ورميةٌ هنا
 *  تبتلع العطبَ الأصليَّ** وتترك صاحبَها بلا شاشةٍ ولا رسالة. */
function readStamp(key: string): number {
  try {
    return Number(sessionStorage.getItem(key) ?? 0);
  } catch {
    return 0;
  }
}

function writeStamp(key: string, value: number): boolean {
  try {
    sessionStorage.setItem(key, String(value));
    return true;
  } catch {
    // **تخزينٌ محجوب**: لا رايةَ تُكتب، فلا إعادةَ — والخطأُ يُرمى ويُعرض.
    // وإعادةٌ بلا رايةٍ هي الحلقةُ بعينها.
    return false;
  }
}

/** `lazy` بديلاً — **التوقيعُ نفسُه**، فلا موضعَ نداءٍ يتغيّر.
 *
 * **وهذا هو سببُ أن يُغلَّف `lazy` لا أن تُغلَّف سبعةٌ وسبعون نداءً**: ما
 * يُطبَّق في موضعٍ واحدٍ لا يُنسى في الثامن والسبعين، **وما يُكتب في كلِّ
 * موضعٍ يُنسى في أحدها** — وهي قاعدةُ «الحارسُ يُطبَّق لا يُتذكَّر».
 */
// **`any` هنا توقيعُ React نفسِه** لا تساهلٌ: `lazy` مُعرَّفٌ
// `<T extends ComponentType<any>>`، **ومن ضيّقه إلى `never` منع كلَّ مكوّنٍ
// يأخذ خاصّيّة** — قِيس فسقط التصريفُ في الثلاثة.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyChunk<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
) {
  return lazy(() =>
    factory().catch((error: unknown) => {
      if (!isChunkError(error)) throw error;

      const key = chunkKey(error);
      const now = Date.now();
      if (now - readStamp(key) > RETRY_WINDOW_MS && writeStamp(key, now)) {
        window.location.reload();
        // **لا يُرسَم شيءٌ قبل الإعادة**: وعدٌ لا يُحلّ يُبقي `Suspense` على
        // بديله، فلا تومض شاشةُ خطأٍ ثمّ تُعاد الصفحةُ فوقها.
        return new Promise<{ default: T }>(() => {});
      }
      // **أُعيدت ثمّ سقطت** — يُرمى فيلتقطه حدُّ الخطأ، ولا يُعاد ثانيةً.
      throw error;
    }),
  );
}
