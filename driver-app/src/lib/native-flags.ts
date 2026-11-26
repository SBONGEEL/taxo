/** **مفاتيحُ الطرف الأصليّ التي تُقرأ خارج الرئيسيّة** (SPEC §١٠٣ المرحلة A/8 وA/9) — تُكتب حين تُعرف الدولة:
 *
 * - `in_app_update` ⇐ زرُّ «تحديث» في بوّابة التحديث يجرّب Google Play أوّلاً (`setPlayInAppUpdate`)، ويُحفظ لإقلاعٍ قادم.
 * - الدولةُ نفسُها ⇐ بوّابةُ التحديث ترسلها في الإقلاع القادم فيُختار حدُّ تلك الدولة من لوحة الإصدارات (`setUpdateCountry`).
 * - `in_app_review` ⇐ طلبُ تقييم المتجر بعد الرحلة الناجحة (`setReviewAllowed`) — مطفأً لا يُطلب أبداً.
 *
 * **ولا يمسّ أيٌّ منهما نداءً ولا مالاً.**
 */
import { useEffect } from "react";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { setReviewAllowed } from "@/lib/in-app-review";
import { setPlayInAppUpdate, setUpdateCountry } from "@/lib/update-gate";

export function useNativeFlags(country: CountryCode | undefined): void {
  const play = useFeature(country, "in_app_update");
  const review = useFeature(country, "in_app_review");
  useEffect(() => {
    if (country) setPlayInAppUpdate(play);
  }, [country, play]);
  // **سوقُ التطبيق لبوّابة التحديث** (SPEC §43، ٢٠٢٦-١١-٢٦) — حدُّ اللوحة لكلِّ دولة يُقرأ في الإقلاع القادم
  useEffect(() => {
    if (country) setUpdateCountry(country);
  }, [country]);
  useEffect(() => {
    setReviewAllowed(review);
  }, [review]);
}
