/** «هل خدمة التوصيل النسائي معروضةٌ على صاحبة هذه الشاشة؟» — سؤالٌ بجواب واحد.
 *
 * يجيبه هذا الملف وحده فتتفق عليه الشاشات: اختيارُ التفضيل عند الطلب،
 * والتفضيلُ الافتراضي في الملف، والسِمة الوردية. ولو أجابت كلُّ شاشةٍ بنفسها
 * لظهر المفتاح في واحدةٍ وغاب عن أخرى بعد أول تعديل.
 *
 * شرطان معاً:
 *
 * 1. **`women_service_enabled` مفعّلٌ في دولتها** — ومطفأً لا يظهر شيءٌ
 *    إطلاقاً: لا خيارٌ معطّل ولا رسالةُ اعتذار (SPEC القسم 4/`feature_flags`).
 * 2. **وقد أعلنت جنسها أنثى**. وهذا قرارُ واجهةٍ لا قيدُ خلفية: التعدادُ
 *    ثلاثيٌّ في القاعدة، لكنّ عرضَ «اطلب كبتنة» على راكبٍ رجل يفتح بابَ ما
 *    وُجدت الخدمة لإغلاقه — أن يطلب رجلٌ امرأةً بعينها لتقوده. فالخدمةُ
 *    تُعرض على من أنشئت لها، وتفضيلُ الكبتن (جانبه هو) يبقى ثلاثياً كاملاً.
 */

import type { GenderPreference } from "@/api/types";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export function useWomenService(): {
  available: boolean;
  defaultPreference: GenderPreference;
} {
  const { user } = useSession();
  const enabled = useFeature(user?.country_code, "women_service_enabled");
  return {
    available: enabled && user?.gender === "female",
    defaultPreference: user?.ride_gender_preference ?? "any",
  };
}
