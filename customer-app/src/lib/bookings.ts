/** الرحلات المجدولة — مفتاحُها وأزمنتُها (12-ط).
 *
 * **والحدُّ الأدنى مكرَّرٌ هنا بقصد**: الخلفيةُ ترفض ما هو أقرب من نصف ساعة
 * (`MIN_LEAD_MINUTES`)، والشاشةُ تمنع اختيارَه أصلاً — فحقلٌ يقبل ما تعرف
 * الشاشةُ أنه سيُرفض يعلّم صاحبَه أن يجرّب ثم يُخطئ. والرفضُ في الخلفية هو
 * الحارس، وهذا راحةٌ لا حراسة.
 */

import { useSession } from "@/lib/session";
import { useFeature } from "@/lib/config";

export const MIN_LEAD_MINUTES = 30;
export const MAX_HORIZON_DAYS = 30;

export function useScheduledRides(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "scheduled_rides_enabled");
}

/** **الحجزُ المضمون** (§٦٣-ج/٣) — مفتاحُه يُخفي الخيارَ كلَّه لا يعطّله. **ولا رسمَ يُقرأ هنا**: لا بابَ عامٌّ ينشره قبل
 *  الحجز، **وصفرُه في السوق يُرفض من الخلفية** (`guaranteed_booking_unavailable`) فيُقال نصُّها تحت الزرّ. */
export function useGuaranteedBooking(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "guaranteed_booking_enabled");
}

/** **ساعتان قبل الموعد على الأقلّ** — مرآةُ `guarantees.MIN_LEAD` في الخلفية: ليتّسع لقبول كبتنٍ وتأكيدِه قبل الموعد
 *  بساعة. **ومكرَّرةٌ هنا بقصد** كحدِّ نصف الساعة أعلاه: الشاشةُ تعطّل ما تعرف أنه سيُرفض، **والرفضُ في الخلفية هو الحارس**. */
export const GUARANTEE_MIN_LEAD_MINUTES = 120;

/** أيتّسع الموعدُ المختارُ لحجزٍ مضمون؟ — `when` بصيغة `datetime-local` (وقتٌ محلّيٌّ بلا منطقة). */
export function guaranteeLeadOk(when: string): boolean {
  const at = new Date(when).getTime();
  return Number.isFinite(at) && at - Date.now() >= GUARANTEE_MIN_LEAD_MINUTES * 60_000;
}

/** قيمةٌ لحقل `datetime-local` — **بالوقت المحلي لا UTC**: الحقلُ يعرض ما
 *  يُعطى كما هو، و`toISOString` يعطي UTC فيرى صاحبُه ساعةً غيرَ ساعته. */
export function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function earliest(): Date {
  return new Date(Date.now() + MIN_LEAD_MINUTES * 60_000);
}

export function latest(): Date {
  return new Date(Date.now() + MAX_HORIZON_DAYS * 86_400_000);
}
