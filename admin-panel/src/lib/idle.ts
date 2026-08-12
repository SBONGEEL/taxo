/** مؤقّتُ الخمول — الطبقةُ الثانية من مهلة اللوحة (SPEC §14.1، المرحلة 12-د).
 *
 * **ويقيس نشاطَ الإنسان لا حركةَ الشبكة**، وهذا هو الفرق الذي يجعله حارساً لا
 * زينة: الخريطةُ الحيّة تستفتي الخلفية كل خمس ثوانٍ، فمقياسٌ مبنيٌّ على
 * النداءات يجدّد جلسةَ مكتبٍ خالٍ إلى الأبد. ولذلك لا تُحسب المهلةُ هنا من
 * `fetch` ولا من تدوير التوكن — بل من نقرةٍ أو ضغطةِ مفتاحٍ أو تمرير.
 *
 * وما تملكه هذه الطبقةُ **تبويبٌ متروكٌ على مكتب**؛ أما توكنُ تجديدٍ مسروق
 * فتملكه الخلفيةُ بعمر مفتاح الـrefresh. واحدةٌ منهما وحدها وعدٌ لا يُوفى:
 * الخلفيةُ لا ترى المكتبَ الخالي، والمتصفحُ لا يرى توكناً سُرق منه.
 *
 * **والقياسُ ختمُ وقتٍ يُفحص دورياً، لا `setTimeout` يُعاد ضبطه مع كل حركة**،
 * لسببين: ضبطُ مؤقّتٍ في كل حركة فأرةٍ عملٌ في مسارٍ ساخن، **والأهمُّ** أن
 * حاسوباً أُغلق غطاؤه ساعةً يُجمّد المؤقّتات — فيستيقظ ومؤقّتُه لم ينتهِ
 * ويستأنف جلسةً عمرُها ساعة. أما الختمُ فيُقرأ عند الاستيقاظ فيُخرج فوراً.
 */

import { useEffect, useRef } from "react";

/** أحداثُ نشاطٍ حقيقيّ. `mousemove` **ليست** منها عمداً: قطةٌ على لوحة
 *  المفاتيح أو فأرةٌ يهزّها اهتزازُ المكتب تُبقي الجلسةَ حيّة بلا إنسان. */
const ACTIVITY_EVENTS = [
  "pointerdown",
  "keydown",
  "wheel",
  "touchstart",
  "submit",
] as const;

/** كم مرةً نفحص الختم. أخفُّ من أن يُحسب، وأدقُّ من أن يترك جلسةً دقائقَ زائدة. */
const TICK_MS = 15_000;

export function useIdleLogout(
  minutes: number | null,
  onIdle: () => void,
): void {
  // المرجعان يمنعان إعادةَ تركيب المستمعين مع كل تصيير: الدالةُ تتغيّر
  // مرجعيّاً في كل مرة، وربطُها في التبعيات يعيد ضبطَ الختم فلا يخمل أحدٌ أبداً
  const lastActive = useRef(Date.now());
  const handler = useRef(onIdle);
  handler.current = onIdle;

  useEffect(() => {
    if (!minutes || minutes <= 0) return;

    const limit = minutes * 60_000;
    const touch = () => {
      lastActive.current = Date.now();
    };

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, touch, { passive: true, capture: true });
    }
    // العودةُ إلى التبويب نشاطٌ أيضاً — لكنها تُفحص أولاً: من غاب ساعةً ثم
    // عاد يجب أن يجد الجلسةَ منتهيةً لا مُجدَّدةً بعودته
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastActive.current >= limit) {
        handler.current();
        return;
      }
      touch();
    };
    document.addEventListener("visibilitychange", onVisible);

    const timer = window.setInterval(() => {
      if (Date.now() - lastActive.current >= limit) handler.current();
    }, TICK_MS);

    return () => {
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, touch, { capture: true });
      }
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [minutes]);
}
