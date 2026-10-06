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
  /** **نوعُ المناورة واتجاهُها بكلمة Mapbox** (§٦٢-ج/٤٢) — و`null`/غيابُهما (خطوةٌ خُزِّنت قبلهما) نصٌّ بلا سهم. */
  maneuver?: string | null;
  modifier?: string | null;
}

/** ما يُعرض الآن — و`null` تعني **لا شريط**، وهي حالٌ صحيحةٌ لا عطب. */
export interface NextInstruction {
  text: string;
  /** كم بقي حتى المناورة، بالأمتار. */
  meters: number;
  /** سهمُ المناورة — و`null` حين لا يُعرف (`maneuverIcon`). */
  icon: string | null;
  /** **رقمُ خطوتها في المسار** — يميّز مناورتين بنصٍّ واحد، فلا تُسكت نغمةُ الأولى نغمةَ الثانية (`lib/turn-cue`). */
  index: number;
}

/** **سهمُ المناورة من نوعها واتجاهها** (§٦٢-ج/٤٢، C06 · C07) — باسم أيقونةٍ في مقتطَع الخطّ (`index.html`).
 *
 * **و`null` لكلِّ ما لا يُعرف يقيناً**: سهمٌ يُخمَّن خطأً يكذب على من يقود، والنصُّ تحته يقول الاتجاهَ على كلِّ حال. فالدوّارُ
 * بلا جهةٍ لا سهمَ له (لا أيقونةَ لـ«الدوّار مستقيماً»)، والمناورةُ المجهولةُ كذلك. **والمرآةُ لا تُقلب**: يمينُ الطريق يمينٌ في RTL.
 */
export function maneuverIcon(step: Pick<RouteStep, "maneuver" | "modifier"> | undefined): string | null {
  const type = step?.maneuver ?? null;
  const modifier = step?.modifier ?? null;
  if (type === null) return null;
  if (type === "arrive") return "flag";
  const left = modifier !== null && modifier.includes("left");
  const right = modifier !== null && modifier.includes("right");
  if (type === "roundabout" || type === "rotary" || type === "roundabout turn" || type === "exit roundabout" || type === "exit rotary") {
    if (left) return "roundabout_left";
    if (right) return "roundabout_right";
    return null;
  }
  if (type === "merge") return "merge";
  if (type === "fork") return left ? "fork_left" : right ? "fork_right" : "straight";
  if (type === "on ramp" || type === "off ramp") return left ? "ramp_left" : right ? "ramp_right" : "straight";
  switch (modifier) {
    // **الدورانُ يساراً** في طرقٍ تُساق على اليمين (الأردن وليبيا)
    case "uturn":
      return "u_turn_left";
    case "sharp right":
      return "turn_sharp_right";
    case "right":
      return "turn_right";
    case "slight right":
      return "turn_slight_right";
    case "straight":
      return "straight";
    case "slight left":
      return "turn_slight_left";
    case "left":
      return "turn_left";
    case "sharp left":
      return "turn_sharp_left";
    default:
      return type === "depart" || type === "continue" || type === "new name" ? "straight" : null;
  }
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
  return { text: upcoming.text, meters, icon: maneuverIcon(upcoming), index: here.index + 1 };
}

/** **ثلاثُ قراءاتٍ لتعود، وواحدةٌ لتغيب** — وهو ما يمنع الرفيف. */
export const BACK_ON_ROUTE_STREAK = 3;
