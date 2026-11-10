/** **نقطةُ التقاطٍ مقترحة** (البند ١١، §٩٧/١١) — تُسأل الخلفيّةُ عن دبّوس الانطلاق في ورقة التأكيد وحدَها، **والراكبُ يقبل أو يُبقي
 *  دبّوسه**. و«أبقِ دبّوسي» يُسكت الاقتراحَ لذلك الدبّوس بعينه — فلا يعود كلّما أُعيد رسمُ الورقة.
 */

import { useEffect, useState } from "react";

import { pickupSuggestion, type PickupSuggestion } from "@/api/endpoints";
import type { Coordinates } from "@/api/types";

const keyOf = (point: Coordinates) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`;

export function usePickupSuggestion(pickup: Coordinates | null, active: boolean) {
  const [found, setFound] = useState<{ key: string; suggestion: PickupSuggestion } | null>(null);
  const [kept, setKept] = useState<string | null>(null);
  const key = pickup ? keyOf(pickup) : null;

  useEffect(() => {
    if (!active || !pickup || key === null || key === kept) return;
    const controller = new AbortController();
    // **بعد سكون الدبّوس** لا مع كلِّ حركة
    const timer = window.setTimeout(() => {
      pickupSuggestion(pickup.lat, pickup.lng, controller.signal)
        .then((suggestion) => setFound(suggestion ? { key, suggestion } : null))
        .catch(() => undefined);
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
    // `pickup` يُقرأ بمفتاحه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, key, kept]);

  const suggestion = active && found && found.key === key && key !== kept ? found.suggestion : null;
  return { suggestion, keep: () => setKept(key) };
}
