/** «التعليمةُ التالية» — **تظهر على الخط، وتختفي صامتةً عند الانحراف**.
 *
 * **قرارُ المالك (2026-08-20، SPEC §26)**: الشريطُ يظهر ما دام الكبتن على الخط
 * المجمَّد، ويختفي **بلا رسالةٍ وبلا «يُعاد الحساب…»**. فلا يقول شيئاً خاطئاً
 * أبداً. **والعلّةُ قاعدةٌ لا تفصيل**: شاشةٌ تقول ما لا يقع أسوأُ من شاشةٍ
 * صامتة — تعليمةٌ مجمَّدةٌ تُقرأ على أنها الآن، فتصير كذباً لا نقصاً.
 *
 * **والقياسُ على هندسة الخطوة لا على الخطّ المرسوم**: قِيس (2026-08-20) أن
 * `overview=simplified` خطؤه يبلغ **٨٣١ م** في أسوأ مسارٍ مخزَّنٍ عندنا،
 * وهندسةَ الخطوات خطؤها **٤٫٨ م**. فقياسٌ على الأول يُخفي الشريطَ عن كبتنٍ
 * يسير على الطريق تماماً — عكسَ ما بُني له.
 *
 * **والإخفاءُ فوريٌّ والإظهارُ متأنٍّ** — وهي عدمُ تماثلٍ مقصودة: الإخفاءُ
 * **مجّانيّ** (يغيب تلميح)، والإظهارُ الخاطئ **يكذب**. فقفزةُ GPS واحدةٌ تُخفيه
 * فوراً، وثلاثُ قراءاتٍ متتاليةٍ على الخط هي ما يعيده — وبغير ذلك يرفّ الشريطُ
 * ظهوراً واختفاءً في يد من يقود.
 */

import { metersBetween, offRouteMeters } from "@/lib/eta";
import type { Coordinates } from "@/api/types";

export interface RouteStep {
  text: string;
  distance_m: number;
  shape: number[][];
}

/** ما يُعرض الآن — و`null` تعني **لا شريط**، وهي حالٌ صحيحةٌ لا عطب. */
export interface NextInstruction {
  text: string;
  /** كم بقي حتى المناورة، بالأمتار. */
  meters: number;
}

/** الخطوةُ التي يقف عليها الكبتن — **أقربُ خطوةٍ إليه**، أو `null`.
 *
 * ولا يُفترض التقدّمُ بالترتيب: كبتنٌ عاد إلى الوراء أو دخل من منتصف الشارع
 * يبقى على خطوةٍ حقيقية، وعدّادٌ يمشي إلى الأمام وحدَه كان سيقفل دونه.
 */
export function currentStep(
  steps: readonly RouteStep[],
  at: Coordinates | null,
  thresholdM: number,
): { step: RouteStep; index: number; away: number } | null {
  if (!at || steps.length === 0) return null;
  let best: { step: RouteStep; index: number; away: number } | null = null;
  for (const [index, step] of steps.entries()) {
    const away = offRouteMeters(step.shape, at);
    if (away === null) continue;
    if (best === null || away < best.away) best = { step, index, away };
  }
  if (best === null || best.away > thresholdM) return null;
  return best;
}

/** نصُّ الشريط ومسافتُه — **التعليمةُ التالية لا التي يقف عليها**.
 *
 * من يسير في شارعٍ يحتاج أن يعرف **ما بعده**؛ و«القيادة في شارع زهران» وهو
 * فيه خبرٌ لا يفيد. فيُعرض نصُّ الخطوة التالية، ومسافتُها ما بقي حتى نهايةِ
 * الخطوة الحالية.
 */
export function nextInstruction(
  steps: readonly RouteStep[],
  at: Coordinates | null,
  thresholdM: number,
): NextInstruction | null {
  const here = currentStep(steps, at, thresholdM);
  if (here === null) return null;
  const upcoming = steps[here.index + 1];
  if (!upcoming) return null;
  const end = here.step.shape[here.step.shape.length - 1];
  const meters = at
    ? Math.round(metersBetween(at, { lng: end[0], lat: end[1] }))
    : here.step.distance_m;
  return { text: upcoming.text, meters };
}

/** **ثلاثُ قراءاتٍ لتعود، وواحدةٌ لتغيب** — وهو ما يمنع الرفيف. */
export const BACK_ON_ROUTE_STREAK = 3;
