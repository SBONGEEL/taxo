/** تقدّمُ المحطات وعدّادُ الانتظار عند الراكب (SPEC القسم 5.10، المرحلة 12-ب) — بلغة TAXO 2.0 «R29e»
 *  (`design/t2-new/rider/R29e-trip-stops-wait.dc.html`) داخل ورقة R09، **في المظهرين والنسائيّ**.
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
 * من نصٍّ يقول «المحطة ١ من ٢». **والواقفُ عندها مربّعٌ بالجمر** كمربّعات المحطات في ورقة الطلب (R06).
 */

import { Fragment, useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { currencyLabel, formatMoney } from "@/lib/utils";

import "@/screens/t2/request.css";

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
    <div className="t2-stopbar">
      <div className="t2-stopbar-track">
        {ride.stops.map((stop, index) => {
          const done = stop.resumed_at !== null;
          const here = stop.arrived_at !== null && stop.resumed_at === null;
          return (
            <Fragment key={stop.id}>
              <span className={done ? "t2-stopbar-sq done" : here ? "t2-stopbar-sq here" : "t2-stopbar-sq"}>
                {index + 1}
              </span>
              <span className={done ? "t2-stopbar-join done" : "t2-stopbar-join"} aria-hidden="true" />
            </Fragment>
          );
        })}
        <span className="t2-stopbar-end">وجهتك</span>
      </div>

      {waiting ? (
        <div className="t2-meter">
          <div>
            <p className="t2-meter-label">الكبتن واقفٌ عند المحطة {waiting.sequence}</p>
            {/* الوقتُ يُحسب هنا — والمالُ لا */}
            <p dir="ltr" className="t2-meter-clock">
              {elapsed(waiting.arrived_at!, now)}
            </p>
          </div>
          <div className="t2-meter-money">
            <p className="t2-meter-label">رسم الانتظار حتى الآن</p>
            <p className="t2-meter-amount">
              <span dir="ltr" className="t2-num">
                {formatMoney(ride.waiting_charge)}
              </span>
              <span className="t2-meter-cur">{currencyLabel(ride.currency)}</span>
            </p>
          </div>
        </div>
      ) : null}

      {waiting?.over_max_wait ? (
        <p className="t2-note warn">
          <span className="t2-icon" aria-hidden="true">error</span>
          <span>تجاوز الانتظار الحدَّ المسموح عند هذه المحطة — يمكن للكبتن إنهاء الرحلة هنا.</span>
        </p>
      ) : null}
    </div>
  );
}
