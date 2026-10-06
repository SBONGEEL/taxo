/** إضافةُ المحطات الوسيطة وترتيبُها وحذفُها — قبل التأكيد لا بعده.
 *
 * **الترتيبُ والحذف يقعان هنا** لأن تغيير الوجهة بعد أن سار الكبتن يغيّر
 * السعرَ المتفق عليه، وذاك طلبٌ جديد لا تعديل (SPEC القسم 5.10). فما يصل
 * الخلفيةَ قائمةٌ مرتَّبةٌ نهائية، ولا مسارَ لإعادة ترتيب رحلةٍ قائمة.
 *
 * **والتحريكُ بسهمين لا بالسحب**: السحبُ على قائمةٍ من سطرين أو ثلاثة داخل
 * ورقةٍ سفلية يتنازع مع سحب الورقة نفسها، ويحتاج لمسةً طويلة لا يعرفها
 * المستخدم. وسهمان يقولان ما يفعلانه ويعملان بالنقر — والقائمةُ ثلاثةٌ على
 * الأكثر فلا مسافة تُقطع.
 *
 * **ولا سعرَ يُحسب هنا**: إضافةُ محطةٍ تعيد سؤال `POST /rides/estimate`
 * فيعود الرقمُ من الخلفية (القسم 14) — ولا يُجمع رسمُ محطةٍ على مبلغٍ معروض.
 */

import { MAX_STOPS } from "@/lib/multistop";

export interface DraftStop {
  lat: number;
  lng: number;
  address: string | null;
}

export function StopsEditor({
  stops,
  onChange,
  waitingNote,
}: {
  stops: DraftStop[];
  onChange: (next: DraftStop[]) => void;
  /** سطرُ رسم الانتظار — نصٌّ جاهزٌ من المستدعي، فلا يُصاغ مالٌ هنا. */
  waitingNote: string | null;
}) {
  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= stops.length) return;
    const next = [...stops];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  // **وجهُ TAXO 2.0 وحدَه** (`ConfirmRideT2`، «R06»): الترتيبُ والحذفُ والنصوصُ هي هي، **والإضافةُ زرُّ «+» في بطاقة المسار**
  // كما رسمته اللوحة — فلا يُرسم هنا زرٌّ ثانٍ لها، ولا سطرُ الشرح وهو بلا محطات. **ونُزع الوجهُ القائم** (R29): لم يبقَ من يرسمه.
  if (stops.length === 0) return null;
  return (
    <div className="t2-stops">
      <div className="t2-stops-head">
        محطات في الطريق · {stops.length}/{MAX_STOPS}
      </div>
      <ul className="t2-stops-list">
        {stops.map((stop, index) => (
          <li key={`${stop.lat},${stop.lng},${index}`} className="t2-stop">
            <span className="t2-stop-num">{index + 1}</span>
            <span className="t2-stop-label">{stop.address ?? "نقطة على الخريطة"}</span>
            <button
              type="button"
              aria-label="تحريك لأعلى"
              disabled={index === 0}
              onClick={() => move(index, -1)}
              className="t2-stop-btn"
            >
              <span className="t2-icon" aria-hidden="true">arrow_upward</span>
            </button>
            <button
              type="button"
              aria-label="تحريك لأسفل"
              disabled={index === stops.length - 1}
              onClick={() => move(index, 1)}
              className="t2-stop-btn"
            >
              <span className="t2-icon" aria-hidden="true">arrow_downward</span>
            </button>
            <button
              type="button"
              aria-label="حذف المحطة"
              onClick={() => onChange(stops.filter((_, at) => at !== index))}
              className="t2-stop-btn danger"
            >
              <span className="t2-icon" aria-hidden="true">close</span>
            </button>
          </li>
        ))}
      </ul>
      {waitingNote ? (
        <p className="t2-note">
          <span className="t2-icon" aria-hidden="true">location_on</span>
          {waitingNote}
        </p>
      ) : null}
    </div>
  );
}
