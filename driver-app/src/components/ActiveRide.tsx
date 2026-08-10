/** الرحلة النشطة — SPEC القسم 12/4، وشكلُها من `DESIGN.md` §5.3.
 *
 * ثلاثةُ أطوارٍ بزرٍّ واحد يتبدّل نصُّه: «وصلتُ إلى الراكب» ← «بدء الرحلة»
 * ← «إنهاء الرحلة». والانتقالُ يُطلب من الخلفية وحدها
 * (`services/rides.py::ALLOWED_TRANSITIONS`) — الزرُّ يسأل ولا يقرّر، والحالةُ
 * الجديدة تأتي من ردّها لا من افتراضٍ محلي.
 *
 * ولون النقطتين يحمل الطور: قبل الركوب الانطلاقُ حيٌّ والوجهةُ خافتة، وبعد
 * `in_progress` ينعكسان (`DESIGN.md` §2.8).
 *
 * **ولا شاشةَ تحصيلٍ هنا**: `POST /rides/{id}/complete` يُنهي الرحلة،
 * وتحصيلُ الأجرة شاشةٌ مستقلة على `payments` تأتي في الجلسة التالية —
 * فالزرُّ الأخير ينهي الرحلة ويعود بالكبتن إلى الرئيسية حتى تُبنى.
 */

import type { Ride } from "@/api/types";
import { arabicDigits, cn } from "@/lib/utils";

const PHASES = {
  accepted: { title: "في الطريق إلى الراكب", action: "وصلتُ إلى الراكب" },
  arrived: { title: "بانتظار الراكب", action: "بدء الرحلة" },
  in_progress: { title: "الرحلة جارية", action: "إنهاء الرحلة" },
} as const;

type Phase = keyof typeof PHASES;

interface Props {
  ride: Ride;
  currencyLabel: string;
  busy: boolean;
  onAdvance: () => void;
  onCancel: () => void;
}

export function ActiveRide({
  ride,
  currencyLabel,
  busy,
  onAdvance,
  onCancel,
}: Props) {
  const phase = PHASES[ride.status as Phase] ?? PHASES.accepted;
  const riding = ride.status === "in_progress";

  return (
    <>
      {/* شريطُ الطور أعلى الخريطة */}
      <div className="pointer-events-none absolute inset-x-0 top-14 z-10 flex justify-center">
        <span className="rounded-full border border-line bg-surface px-18 py-8 text-12.5 font-bold text-ink">
          {phase.title}
        </span>
      </div>

      <div className="absolute inset-x-0 bottom-0 z-10 rounded-t-22 border-t border-line bg-surface px-18 pb-22 pt-16">
        <div className="mb-13 flex items-center gap-12">
          <div className="flex size-44 items-center justify-center rounded-full border border-line bg-surface-2 text-14 font-bold text-ink">
            ر
          </div>
          <div className="flex-1">
            <div className="text-14 font-bold text-ink">راكب TAXO</div>
            <div className="text-11 text-muted">
              {arabicDigits(ride.estimated_fare)} {currencyLabel}
            </div>
          </div>
          {/* الاتصال مسارٌ في النظام لا في التطبيق: رقمُ الراكب لا يصل
              الكبتن (القسم 14)، فالزرّ يُخفى حتى يُبنى الاتصال المُقنَّع */}
        </div>

        <div className="mb-15 grid grid-cols-[12px_1fr] gap-x-10 gap-y-4">
          <span
            className={cn(
              "mx-auto mt-5 block size-8 rounded-full",
              riding ? "bg-muted" : "bg-ok",
            )}
          />
          <div className={cn("text-12.5", riding ? "text-muted" : "text-ink")}>
            {ride.pickup_address ?? "نقطة الانطلاق"}
          </div>
          <span className="mx-auto block h-12 w-2 bg-line" />
          <span />
          <span
            className={cn(
              "mx-auto mt-2 block size-8 rounded-2",
              riding ? "bg-ok" : "bg-muted",
            )}
          />
          <div className={cn("text-12.5", riding ? "text-ink" : "text-muted")}>
            {ride.dropoff_address ?? "الوجهة"}
          </div>
        </div>

        <button
          type="button"
          onClick={onAdvance}
          disabled={busy}
          className="w-full rounded-15 bg-accent p-15 text-center text-15 font-bold text-accent-ink disabled:opacity-50"
        >
          {phase.action}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="mt-11 w-full text-center text-12 font-semibold text-muted"
        >
          إلغاء الرحلة
        </button>
      </div>
    </>
  );
}
