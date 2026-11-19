/** **«تم العثور على كبتن» — متى يُقال** (أمرُ المالك ٢٠٢٦-١١-١٩، ورقةُ البحث).
 *
 *  يُقال **لحظةَ ينتقل الطلبُ نفسُه من البحث إلى القبول أمام عين الراكب** — لا لرحلةٍ فُتحت مقبولةً (قبولٌ قديمٌ ليس «وجدنا الآن»)،
 *  ولا حين تتبدّل الرحلةُ بأخرى. **ويُحسب عند صاحب الشاشة لا في الورقة**: الورقةُ تُركَّب من جديدٍ مع كلِّ حالٍ (`key` في `Home`)
 *  فلا تعرف الحالَ التي قبلها — **وهذا بعينه ما أخفى السطرَ في أوّل رفع** (قِيس على الإنتاج ٢٠٢٦-١١-١٩).
 *  بلا React — يُختبر بـ`node --test` (`tests/ride-found.test.ts`).
 */

export interface RideMoment {
  id: string;
  status: string;
}

const SEARCHING = new Set(["searching", "requested"]);

/** أهذا الانتقالُ «وجدنا كبتناً الآن»؟ — الرحلةُ نفسُها، من البحث، إلى القبول. */
export function foundNow(previous: RideMoment | null, next: RideMoment | null): boolean {
  return (
    previous !== null &&
    next !== null &&
    previous.id === next.id &&
    SEARCHING.has(previous.status) &&
    next.status === "accepted"
  );
}

/** مدّةُ السطر على الشاشة ثمّ يخفت. */
export const FOUND_MS = 5_000;
