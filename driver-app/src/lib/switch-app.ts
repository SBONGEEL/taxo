/** التبديلُ إلى تطبيق الراكب — **القرارُ هنا، لا في الشاشة** (SPEC §23).
 *
 * أربعُ حالاتٍ لا اثنتان، وكلٌّ لها مخرجٌ مختلف:
 *
 * | الحال | ما يقع |
 * |---|---|
 * | يملك دورَ الراكب | يُفتح التطبيقُ الآخرُ بجلسته — بلا كلمةِ مرورٍ ولا رمز |
 * | لا يملكه | لا يقع عملياً: كلُّ كبتنٍ راكبٌ أيضاً بحكم التسجيل — ويبقى الفرعُ لأن الغيابَ لا يُخمَّن |
 * | في رحلةٍ جارية | يُقال له **لماذا** لا يعمل الآن — والنصُّ من الخلفية |
 * | التطبيقُ غير مثبَّت | صفحةٌ تشرح وتعطي مدخلَ التثبيت — لا خطأ ولا صمت |
 *
 * **وفتحُ التطبيق الآخر بـ`intent://` لا بمخططٍ عاري**، وثلاثةُ أسباب:
 *
 * ١. `package=` يثبّت المستقبِل، فلا يلتقط الرمزَ تطبيقٌ سجّل المخططَ نفسَه.
 * ٢. `S.browser_fallback_url` يعطي «غير مثبَّت» جواباً **حتمياً** من النظام،
 *    بدل مهلةٍ نخمّن بعدها أن التطبيق لم يُفتح — والتخمينُ يخطئ على جهازٍ بطيء.
 * ٣. الرمزُ يسافر في **مخططٍ خاصٍّ لا يبلغ خادماً**: لا نداءَ شبكةٍ يحمله ولا
 *    سجلَّ وسيطٍ يقيّده. وعمرُه ثلاثون ثانيةً واستعمالُه واحد، فما بقي منه في
 *    سجلِّ نشاطٍ على الجهاز لا يفتح شيئاً بعد ثوانٍ.
 */

import { startHandoff } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { User } from "@/api/types";

/** حزمةُ تطبيق الكبتن ومخططُه — قيمتان تُكتبان هنا لا تُخمَّنان. */
const RIDER_PACKAGE = "ly.tajora.rider";
const RIDER_SCHEME = "taxo-rider";

/** صفحةُ «غير مثبَّت» — يفتحها النظامُ نفسُه حين لا يجد الحزمة. */
export const NOT_INSTALLED_PATH = "/account/switch/rider-not-installed";

export type SwitchState =
  | { kind: "available" }
  | { kind: "needs_registration" }
  | { kind: "blocked"; reason: string };

/** أيَّ حالٍ نحن فيها **قبل** الضغط — فالزرُّ يُرسم بما يقدر عليه. */
export function switchState(user: User | null): SwitchState {
  if (!user) return { kind: "needs_registration" };
  return user.roles?.includes("rider")
    ? { kind: "available" }
    : { kind: "needs_registration" };
}

function fallbackUrl(): string {
  return `${window.location.origin}${NOT_INSTALLED_PATH}`;
}

/** يبني نيّةَ أندرويد — والرمزُ في استعلامِ مخططٍ خاصٍّ لا يبلغ خادماً. */
export function intentUrl(token: string): string {
  const fallback = encodeURIComponent(fallbackUrl());
  return (
    `intent://handoff?t=${encodeURIComponent(token)}#Intent;scheme=${RIDER_SCHEME};package=${RIDER_PACKAGE};` +
    `S.browser_fallback_url=${fallback};end`
  );
}

/**
 * يفتح تطبيقَ الكبتن بجلسةٍ منقولة.
 *
 * **ولا يُطلب الرمزُ إلا عند الضغط**: عمرُه ثلاثون ثانية، فطلبُه عند رسم الشاشة
 * يجعله ميتاً قبل أن يُضغط.
 */
export async function switchToRider(): Promise<void> {
  const { token } = await startHandoff();
  window.location.href = intentUrl(token);
}

/** رسالةُ المنع كما كتبتها الخلفية — ولا تُكتب هنا عربيةٌ ثانية (§17). */
export function blockedReason(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "handoff_blocked_by_active_work") {
    return error.message;
  }
  return null;
}
