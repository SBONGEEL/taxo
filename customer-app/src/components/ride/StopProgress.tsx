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
 *
 * **بلغة TAXO 2.0** (لوحةُ `design/t2-new/rider/R09b`): بطاقةُ «كم متبقية» في R09، ومربّعُ المحطة المرقَّم من «محطاتك» في R06 —
 * ما مضى أخضرُ خافت، وما هو الآن بالجمر، وما بعده حافّةٌ متقطّعة؛ والوقتُ بخطِّ الأرقام.
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { formatMoney } from "@/lib/utils";

import "@/screens/t2/money.css";

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
    <div className="t2-m-meter">
      <div className="t2-m-track">
        {ride.stops.map((stop, index) => {
          const done = stop.resumed_at !== null;
          const here = stop.arrived_at !== null && stop.resumed_at === null;
          return (
            <div key={stop.id} className="t2-m-track-seg">
              <span className={done ? "t2-m-stop done" : here ? "t2-m-stop here" : "t2-m-stop"}>{index + 1}</span>
              <span className={done ? "t2-m-link-line done" : "t2-m-link-line"} aria-hidden="true" />
            </div>
          );
        })}
        <span className="t2-m-track-end">وجهتك</span>
      </div>

      {waiting ? (
        <div className="t2-m-meter-row">
          <div>
            <div className="t2-m-meter-label">الكبتن واقفٌ عند المحطة {waiting.sequence}</div>
            {/* الوقتُ يُحسب هنا — والمالُ لا */}
            <div dir="ltr" className="t2-m-clock">
              {elapsed(waiting.arrived_at!, now)}
            </div>
          </div>
          <div className="t2-m-meter-end">
            <div className="t2-m-meter-label">رسم الانتظار حتى الآن</div>
            <div className="t2-m-meter-charge">{formatMoney(ride.waiting_charge, ride.currency)}</div>
          </div>
        </div>
      ) : null}

      {waiting?.over_max_wait ? (
        <p className="t2-m-meter-note">
          <span className="t2-icon" aria-hidden="true">error</span>
          <span>
            تجاوز الانتظار الحدَّ المسموح عند هذه المحطة — يمكن للكبتن إنهاء
            الرحلة هنا.
          </span>
        </p>
      ) : null}
    </div>
  );
}
