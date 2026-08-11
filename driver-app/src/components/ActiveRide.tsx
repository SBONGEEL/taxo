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

import { useState } from "react";

import type { GenderPreference, Ride } from "@/api/types";
import { arabicDigits, cn } from "@/lib/utils";

export interface CancelReason {
  label: string;
  /** `undefined` = نصٌّ حرّ؛ والمصنَّف يُسقط الرسوم ويُدخل بلاغاً. */
  code?: "gender_mismatch";
}

/** أسبابُ إلغاء الكبتن كما في التصميم النسائي. */
const CANCEL_REASONS: CancelReason[] = [
  { label: "الراكب غير موجود" },
  { label: "الراكب ليس أنثى — عدم تطابق", code: "gender_mismatch" },
  { label: "سلوك غير لائق" },
];

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
  /** يمرّر السببَ المصنَّف مع نصّه — الخلفية تفرّق بينهما (المرحلة 10-ج). */
  onCancel: (reason: CancelReason) => void;
  /** تفضيلُ الكبتن الدائم — به وحده يظهر سببُ «عدم التطابق». */
  genderPreference: GenderPreference;
}

export function ActiveRide({
  ride,
  currencyLabel,
  busy,
  onAdvance,
  onCancel,
  genderPreference,
}: Props) {
  const phase = PHASES[ride.status as Phase] ?? PHASES.accepted;
  const riding = ride.status === "in_progress";
  const [picking, setPicking] = useState(false);
  const [reason, setReason] = useState<CancelReason | null>(null);
  const reasons = CANCEL_REASONS.filter(
    (option) => option.code !== "gender_mismatch" || genderPreference !== "any",
  );

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
          className="w-full rounded-15 bg-brand p-15 text-center text-15 font-bold text-brand-ink disabled:opacity-50"
        >
          {phase.action}
        </button>
        <button
          type="button"
          onClick={() => setPicking(true)}
          disabled={busy}
          className="mt-11 w-full text-center text-12 font-semibold text-muted"
        >
          إلغاء الرحلة
        </button>
      </div>

      {/* ورقةُ أسباب الإلغاء — و«الراكب ليس أنثى» لا تُعرض إلا إن كان الكبتن
          قد قصر عمله على جنس: الخلفية ترفضها في غير ذلك (`CancelReasonNot
          Applicable`)، وزرٌّ يعمل ثم يرتدّ يعلّم إعادةَ المحاولة */}
      {picking ? (
        <div className="absolute inset-0 z-30 flex flex-col justify-end bg-dim">
          <div className="rounded-t-24 border-t border-line bg-surface px-20 pb-24 pt-18">
            <div className="mx-auto mb-16 h-4 w-38 rounded-full bg-line" />
            <div className="text-17 font-bold text-ink">سبب الإلغاء</div>
            <div className="mt-14 flex flex-col gap-9">
              {reasons.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setReason(option)}
                  className={cn(
                    "flex items-center gap-11 rounded-13 border p-13 text-start",
                    reason?.label === option.label
                      ? "border-brand-brd bg-brand-soft"
                      : "border-line",
                  )}
                >
                  <span
                    className={cn(
                      "block size-17 flex-none rounded-full border-2",
                      reason?.label === option.label
                        ? "border-5 border-brand"
                        : "border-line",
                    )}
                  />
                  <span
                    className={cn(
                      "text-13.5",
                      reason?.label === option.label
                        ? "font-bold text-brand"
                        : "text-ink",
                    )}
                  >
                    {option.label}
                  </span>
                </button>
              ))}
            </div>

            {reason?.code === "gender_mismatch" ? (
              <p className="mt-14 rounded-13 border border-line bg-surface-2 p-14 text-12.5 leading-relaxed text-muted">
                لن تُحتسب عليكِ رسوم إلغاء. ويُسجَّل بلاغٌ على حساب الراكب،
                وتكرارُ البلاغات يوسم الحساب للمراجعة.
              </p>
            ) : null}

            <button
              type="button"
              disabled={busy || reason === null}
              onClick={() => {
                setPicking(false);
                onCancel(reason!);
              }}
              className="mt-16 w-full rounded-15 bg-danger p-15 text-center text-15 font-bold text-white disabled:opacity-50"
            >
              تأكيد الإلغاء
            </button>
            <button
              type="button"
              onClick={() => setPicking(false)}
              className="w-full pt-10 text-center text-13 text-muted"
            >
              تراجع
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
