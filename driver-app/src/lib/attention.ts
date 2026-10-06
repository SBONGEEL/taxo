/** **ما يحتاج انتباهَ الكبتن في رئيسيته** (§٦٢-ج/٤٣، C04) — بيتٌ واحدٌ لسؤالين: «أتحتاج وثائقُه فعلاً؟» و«أمرتفعٌ الطلبُ حوله؟».
 *
 * **والجوابان من الخلفية كما هما**: الوثائقُ من `GET /drivers/me/documents` (ما ينقص وما يُطلب رفعُه والحالُ والانتهاء)، والطلبُ من
 * `GET /drivers/me/demand` (نعم/لا وحدَها). **ولا يُخترع شيء**: فشلُ النداء «لا» — نقطةٌ أو سطرٌ يُرى على باطلٍ أسوأُ من غيابه.
 */

import { useEffect, useState } from "react";

import { getDemand, listDocuments } from "@/api/endpoints";
import type { DriverDocuments } from "@/api/types";

/** يومُ الجهاز `YYYY-MM-DD` — **مقارنةُ تاريخين لا مال**؛ وتاريخُ الانتهاء يومٌ تقويميٌّ بلا ساعة. */
function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** **أتحتاج وثائقُه فعلاً؟** — مطلوبٌ ناقص · رفعٌ مطلوب · مستندٌ مرفوض · صلاحيةٌ انقضت. */
function documentsNeedAttention(state: DriverDocuments): boolean {
  if (state.missing_required.length > 0 || state.awaiting_upload.length > 0) return true;
  const day = today();
  return state.documents.some(
    (document) =>
      document.review_status === "rejected" || (document.expires_on !== null && document.expires_on < day),
  );
}

/** نقطةُ «الوثائق» — تُقرأ مرّةً عند الفتح، **ومن الطلب نفسِه** الذي تقرأ به شاشةُ المركبة وثائقَها. */
export function useDocumentsAttention(): boolean {
  const [needed, setNeeded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((state) => {
        if (!cancelled) setNeeded(documentsNeedAttention(state));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return needed;
}

/** **كلَّ دقيقتين** — الطلبُ حول نقطةٍ لا يتبدّل في ثوانٍ، والسؤالُ يقرأ طلباتِ ربع ساعة. */
const DEMAND_EVERY_MS = 120_000;

/** «الطلب مرتفع حولك» — **ما دام متصلاً في رئيسيته وحدَها**: من لا يستقبل لا طلبَ حوله، ومن في رحلةٍ لا يقرؤه. */
export function useDemandHigh(active: boolean): boolean {
  const [high, setHigh] = useState(false);
  useEffect(() => {
    if (!active) {
      setHigh(false);
      return;
    }
    let cancelled = false;
    const ask = () =>
      getDemand()
        .then((answer) => {
          if (!cancelled) setHigh(answer.high);
        })
        .catch(() => undefined);
    void ask();
    const timer = window.setInterval(ask, DEMAND_EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [active]);
  return high;
}
