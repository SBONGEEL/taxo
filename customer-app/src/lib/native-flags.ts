/** **مفاتيحُ الطرف الأصليّ التي تُقرأ خارج الرئيسيّة** (SPEC §١٠٣ المرحلة A/8 وA/9) — تُكتب حين تُعرف الدولة:
 *
 * - `in_app_update` ⇐ زرُّ «تحديث» في بوّابة التحديث يجرّب Google Play أوّلاً (`setPlayInAppUpdate`)، ويُحفظ لإقلاعٍ قادم.
 * - `in_app_review` ⇐ طلبُ تقييم المتجر بعد الرحلة الناجحة (`setReviewAllowed`) — مطفأً لا يُطلب أبداً.
 *
 * **ولا يمسّ أيٌّ منهما نداءً ولا مالاً.**
 */
import { useEffect } from "react";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { setReviewAllowed } from "@/lib/in-app-review";
import { setPlayInAppUpdate } from "@/lib/update-gate";

export function useNativeFlags(country: CountryCode | undefined): void {
  const play = useFeature(country, "in_app_update");
  const review = useFeature(country, "in_app_review");
  useEffect(() => {
    if (country) setPlayInAppUpdate(play);
  }, [country, play]);
  useEffect(() => {
    setReviewAllowed(review);
  }, [review]);
}
