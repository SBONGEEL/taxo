/** تقدّمُ المحطات وعدّادُ الانتظار عند الراكب (SPEC القسم 5.10، المرحلة 12-ب).
 *
 * **العدّادُ يمشي هنا والمبلغُ يأتي من الخلفية** — وهذا الفصلُ هو كلُّ القصة:
 * عرضُ الوقت حسابُ وقت، وعرضُ المال حسابُ مال، والقسم 14 يحصر الثاني في
 * الخلفية وحدها. فالثواني تُحسب محلياً من `arrived_at`، وأما `waiting_charge`
 * فيصل محسوباً مع كل قراءةٍ للرحلة ويُعرض كما وصل.
 *
 * **ولا مفاجأةَ في شاشة الدفع**: ما يقرؤه الراكب واقفاً هو ما يُحصَّل — وهو
 * سببُ وجود هذا المكوّن أصلاً. عدّادٌ يظهر بعد الرحلة لا يمنع مفاجأة.
 *
 * **والمنتهيةُ خيطٌ أخضر** (`DESIGN.md` §2.8-ب): التقدّمُ يُقرأ من الشكل لا
 * من نصٍّ يقول «المحطة ١ من ٢».
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { cn, formatMoney } from "@/lib/utils";

/** `mm:ss` — والمصدرُ ختمُ الخلفية لا لحظةُ فتح الشاشة. */
function elapsed(since: string, now: number): string {
  const seconds = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000));
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export function StopProgress({ ride }: { ride: Ride }) {
  const waiting = ride.stops.find(
    (stop) => stop.arrived_at !== null && stop.resumed_at === null,
  );

  // ثانيةٌ بثانية **للعدّاد وحده**؛ المبلغُ لا يُعاد حسابه هنا بحال
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!waiting) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [waiting]);

  if (ride.stops.length === 0) return null;

  return (
    <div className="rounded-12 border border-line bg-bg px-12 py-10">
      <div className="flex items-center gap-6">
        {ride.stops.map((stop, index) => {
          const done = stop.resumed_at !== null;
          const here = stop.arrived_at !== null && stop.resumed_at === null;
          return (
            <div key={stop.id} className="flex flex-1 items-center gap-6">
              <span
                className={cn(
                  "flex size-20 flex-none items-center justify-center rounded-2 text-10 font-bold",
                  done
                    ? "bg-ok text-accent-ink"
                    : here
                      ? "bg-warn text-accent-ink"
                      : "border border-line text-muted",
                )}
              >
                {index + 1}
              </span>
              <span
                className={cn("h-px flex-1", done ? "bg-ok" : "bg-line")}
                aria-hidden
              />
            </div>
          );
        })}
        <span className="text-12 text-muted">وجهتك</span>
      </div>

      {waiting ? (
        <div className="mt-10 flex items-end justify-between">
          <div>
            <p className="text-12 text-muted">
              الكبتن واقفٌ عند المحطة {waiting.sequence}
            </p>
            {/* الوقتُ يُحسب هنا — والمالُ لا */}
            <p className="text-20 font-bold tabular-nums text-ink">
              {elapsed(waiting.arrived_at!, now)}
            </p>
          </div>
          <div className="text-end">
            <p className="text-12 text-muted">رسم الانتظار حتى الآن</p>
            <p className="font-bold text-ink">
              {formatMoney(ride.waiting_charge, ride.currency)}
            </p>
          </div>
        </div>
      ) : null}

      {waiting?.over_max_wait ? (
        <p className="mt-8 text-12 leading-relaxed text-warn">
          تجاوز الانتظار الحدَّ المسموح عند هذه المحطة — يمكن للكبتن إنهاء
          الرحلة هنا.
        </p>
      ) : null}
    </div>
  );
}
