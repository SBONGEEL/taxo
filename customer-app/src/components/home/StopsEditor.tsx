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

import { ArrowDown, ArrowUp, MapPin, Plus, X } from "lucide-react";

import { MAX_STOPS } from "@/lib/multistop";


export interface DraftStop {
  lat: number;
  lng: number;
  address: string | null;
}

export function StopsEditor({
  stops,
  onChange,
  onAdd,
  waitingNote,
}: {
  stops: DraftStop[];
  onChange: (next: DraftStop[]) => void;
  onAdd: () => void;
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

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <p className="text-12 text-muted">
          محطات في الطريق
          {stops.length > 0
            ? ` · ${stops.length}/${MAX_STOPS}`
            : ""}
        </p>
        {stops.length < MAX_STOPS ? (
          <button
            type="button"
            onClick={onAdd}
            className="flex items-center gap-4 text-12 font-medium text-ink"
          >
            <Plus className="size-14" />
            إضافة محطة
          </button>
        ) : null}
      </div>

      {stops.length === 0 ? (
        <p className="text-12 leading-relaxed text-muted">
          يمكنك إضافة حتى {MAX_STOPS} محطتين في الطريق —
          يقف الكبتن عندهما ثم يكمل إلى وجهتك.
        </p>
      ) : (
        <ul className="space-y-8">
          {stops.map((stop, index) => (
            <li
              key={`${stop.lat},${stop.lng},${index}`}
              className="flex items-center gap-10 rounded-12 border border-line bg-surface px-12 py-10"
            >
              {/* المحطةُ مربّعٌ برقمها — الشكلُ يميّزها عن الطرفين والرقمُ
                  يقول ترتيبَها (DESIGN.md §2.8-ب) */}
              <span className="flex size-20 flex-none items-center justify-center rounded-2 bg-warn text-10 font-bold text-inv">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-14 text-ink">
                {stop.address ?? "نقطة على الخريطة"}
              </span>

              <button
                type="button"
                aria-label="تحريك لأعلى"
                disabled={index === 0}
                onClick={() => move(index, -1)}
                className="text-muted disabled:opacity-30"
              >
                <ArrowUp className="size-16" />
              </button>
              <button
                type="button"
                aria-label="تحريك لأسفل"
                disabled={index === stops.length - 1}
                onClick={() => move(index, 1)}
                className="text-muted disabled:opacity-30"
              >
                <ArrowDown className="size-16" />
              </button>
              <button
                type="button"
                aria-label="حذف المحطة"
                onClick={() => onChange(stops.filter((_, at) => at !== index))}
                className="text-danger"
              >
                <X className="size-16" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {stops.length > 0 && waitingNote ? (
        <p className="mt-8 flex items-start gap-6 text-12 leading-relaxed text-muted">
          <MapPin className="mt-2 size-14 shrink-0" />
          {waitingNote}
        </p>
      ) : null}
    </div>
  );
}
