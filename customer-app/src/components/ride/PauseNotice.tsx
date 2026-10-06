/** «العدّادُ يعمل ولماذا» — ما يراه الراكبُ أثناء وقفةٍ غير مخطَّطة (§5.10-ب)، بلغة TAXO 2.0 «R29e»
 *  (`design/t2-new/rider/R29e-trip-stops-wait.dc.html`) داخل ورقتي R08 · R09، **في المظهرين والنسائيّ**.
 *
 * **وسطرٌ صريحٌ حين ينشأ، لا رقمٌ يظهر في الفاتورة آخرَ الرحلة**: مواصفةُ البند
 * تقولها بنصِّها — **مبلغٌ لم يُعلَن حين نشأ يُقرأ خطأً في الحساب**. والراكبُ
 * الذي يرى الرسمَ أولَ مرةٍ في شاشة الدفع يفتح نزاعاً على مالٍ استحقّه الكبتن.
 *
 * **والوقتُ يُحسب هنا والمالُ يأتي من الخلفية** (§14) — كشريط المحطات تماماً.
 *
 * **والنصُّ يفرّق بين الحالين**: انتظارٌ عند الوصول (تأخّر هو) ووقفةٌ في منتصف
 * الرحلة (طلبها هو). وجملةٌ واحدةٌ لهما تلوم من لم يفعل شيئاً في إحداهما.
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { currencyLabel, formatMoney } from "@/lib/utils";

import "@/screens/t2/request.css";

function elapsed(since: string, now: number): string {
  const started = new Date(since).getTime();
  const seconds = Math.max(0, Math.floor((now - started) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

export function PauseNotice({ ride }: { ride: Ride }) {
  const pause = ride.open_pause;
  // **كلَّ ثانيةٍ هنا لا كلَّ عشر**: المعروضُ ثوانٍ تمشي، بخلاف شاشة الكبتن
  // التي تعرض دقائقَ صحيحة — وعدّادُ ثوانٍ يقفز عشراً يُقرأ معطوباً
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!pause) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [pause?.id]);

  if (!pause) return null;

  const minutes = (now - new Date(pause.started_at).getTime()) / 60_000;
  const free = pause.free_minutes;
  const billing = minutes >= free;

  return (
    <div className={pause.over_max ? "t2-pause over" : "t2-pause"}>
      <div className="t2-meter">
        <div>
          <p className="t2-meter-label">
            {pause.kind === "arrival" ? "الكبتن ينتظرك عند نقطة الانطلاق" : "الكبتن واقفٌ بطلبك"}
          </p>
          {/* الوقتُ يُحسب هنا — والمالُ لا */}
          <p dir="ltr" className="t2-meter-clock">
            {elapsed(pause.started_at, now)}
          </p>
        </div>
        <div className="t2-meter-money">
          {/* **والمهلةُ تُقال قبل أن تنتهي لا بعدها**: راكبٌ يرى صفراً ولا يعرف
              لماذا يظنّ العدّادَ معطوباً، ثم يفاجئه رقمٌ بعد دقيقة */}
          <p className="t2-meter-label">{billing ? "رسم الانتظار حتى الآن" : `أول ${free} دقائق مجاناً`}</p>
          <p className="t2-meter-amount">
            <span dir="ltr" className="t2-num">
              {formatMoney(ride.pause_charge)}
            </span>
            <span className="t2-meter-cur">{currencyLabel(ride.currency)}</span>
          </p>
        </div>
      </div>
      {pause.over_max ? (
        <p className="t2-note warn">
          <span className="t2-icon" aria-hidden="true">error</span>
          <span>تجاوز الانتظارُ الحدَّ المسموح — العدّادُ ما زال يعمل، وللكبتن أن يُنهي الرحلة عند هذه النقطة.</span>
        </p>
      ) : null}
    </div>
  );
}
