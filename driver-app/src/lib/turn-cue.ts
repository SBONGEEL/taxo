/** **نغمةُ المنعطف** — «صوت الإرشاد» في C15 (§٦١-ط/٩، §٦٢-ج/٣٤). **نغمةٌ لا كلام**: الإرشادُ المنطوقُ لا يُبنى من طبقة الويب.
 *
 * **مرّةً لكلِّ مناورة** حين يبقى دونها `TURN_CUE_M` — **والشريطُ الظاهرُ شرطُها**: التعليمةُ تغيب فوراً عند الانحراف وتعود بعد
 * ثلاث قراءات (`BACK_ON_ROUTE_STREAK`)، **فلا نغمةَ لمنعطفٍ لا يُرى سهمُه**. ومفتاحُها وجهارتُها في `lib/sound` (مطفأةٌ افتراضاً).
 *
 * **ولا تُعزف والتطبيقُ خلف غيره**: من يقود بخرائط قوقل أو Waze يسمع إرشادَها، **ونغمتان لمنعطفٍ واحدٍ أربكُ من واحدة**.
 */

import { useEffect, useRef } from "react";

import type { NextInstruction, RouteStep } from "@/lib/next-instruction";
import { play } from "@/lib/sound";

/** **قبل المنعطف بـ150 م** — نحو عشر ثوانٍ بسرعة المدينة (50 كم/س)، وتكفي للتمهّل وإشارة الانعطاف. */
export const TURN_CUE_M = 150;

export function useTurnCue(instruction: NextInstruction | null, steps: readonly RouteStep[]): void {
  const cued = useRef<Set<number>>(new Set());
  // **مسارٌ جديدٌ صفحةٌ جديدة** (الاقترابُ ثمّ الرحلة، أو إعادةُ التوجيه): أرقامُ الخطوات تخصّ مسارَها
  useEffect(() => {
    cued.current = new Set();
  }, [steps]);
  useEffect(() => {
    if (!instruction || instruction.meters > TURN_CUE_M || cued.current.has(instruction.index)) return;
    cued.current.add(instruction.index);
    if (document.visibilityState === "visible") play("turn");
  }, [instruction]);
}
