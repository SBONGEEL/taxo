/** **«لم نتمكن من تحديد موقعك»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ج) — **المنطقُ الخالص**: السببُ من الإشارات، والنصُّ والزرُّ لكلِّ سبب.
 *
 *  **ونسخةٌ بايتاً في التطبيقين** (`driver-app/src/lib/location-help.ts`) — الرسالةُ واحدةٌ بنصّ المالك حرفاً، فلا تفترق جملةٌ عن أختها.
 *
 *  **ترتيبُ الإشارات**: ما يقوله الغلافُ (إذنُ التطبيق، وزرُّ الموقع في الهاتف) أصدقُ من رمز خطأ المتصفّح — والأقدمُ لا يقولهما، فيُقرأ
 *  الرمز: ١ رفضُ الإذن، ٢ لا مصدرَ للموقع (GPS مطفأٌ غالباً)، ٣ انقضت المهلةُ بلا قراءة (إشارةٌ ضعيفة). **ولا يُخمَّن ما لا إشارةَ له**. */

export type LocationCause = "gps_off" | "permission" | "weak" | "unknown";
export type SignalState = "on" | "off" | "unknown";

/** **نصُّ المالك حرفاً** */
export const LOCATION_MESSAGE =
  "لم نتمكن من تحديد موقعك الحالي. تأكد أن زر الموقع (GPS) مفعّل في هاتفك، ثم اضغط تحديث الموقع";
export const WEAK_SIGNAL_MESSAGE = "الإشارة ضعيفة، اقترب من نافذة أو اخرج قليلاً ثم اضغط تحديث";
export const REFRESH_LABEL = "تحديث الموقع الحالي";

export function locationCause(input: {
  errorCode: number | null;
  permission: SignalState;
  services: SignalState;
}): LocationCause {
  if (input.permission === "off") return "permission";
  if (input.services === "off") return "gps_off";
  if (input.errorCode === 1) return "permission";
  if (input.errorCode === 2) return "gps_off";
  if (input.errorCode === 3) return "weak";
  return "unknown";
}

export function messageFor(cause: LocationCause): string {
  return cause === "weak" ? WEAK_SIGNAL_MESSAGE : LOCATION_MESSAGE;
}

/** **الزرُّ الثاني بحسب السبب** — `key` صفحةٌ يفتحها الغلاف: `location_services` زرُّ الموقع في الهاتف، و`location` إذنُ التطبيق.
 *  **و`null` حيث لا صفحةَ تُصلح شيئاً** (إشارةٌ ضعيفة: الحلُّ مكانُ الهاتف لا إعدادُه). */
export function actionFor(cause: LocationCause): { label: string; key: "location_services" | "location" } | null {
  if (cause === "gps_off") return { label: "فتح إعدادات الموقع", key: "location_services" };
  if (cause === "permission") return { label: "فتح إذن الموقع", key: "location" };
  return null;
}
