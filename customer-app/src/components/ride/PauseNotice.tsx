/** «العدّادُ يعمل ولماذا» — ما يراه الراكبُ أثناء وقفةٍ غير مخطَّطة (§5.10-ب).
 *
 * **وسطرٌ صريحٌ حين ينشأ، لا رقمٌ يظهر في الفاتورة آخرَ الرحلة**: مواصفةُ البند
 * تقولها بنصِّها — **مبلغٌ لم يُعلَن حين نشأ يُقرأ خطأً في الحساب**. والراكبُ
 * الذي يرى الرسمَ أولَ مرةٍ في شاشة الدفع يفتح نزاعاً على مالٍ استحقّه الكبتن.
 *
 * **والوقتُ يُحسب هنا والمالُ يأتي من الخلفية** (§14) — كشريط المحطات تماماً.
 *
 * **والنصُّ يفرّق بين الحالين**: انتظارٌ عند الوصول (تأخّر هو) ووقفةٌ في منتصف
 * الرحلة (طلبها هو). وجملةٌ واحدةٌ لهما تلوم من لم يفعل شيئاً في إحداهما.
 *
 * **بلغة TAXO 2.0** (لوحةُ `design/t2-new/rider/R08b`): بطاقةُ «كم متبقية» بعمودين — الوقتُ بخطِّ الأرقام، والمهلةُ تُقال قبل أن
 * تنتهي، **وحافّةُ التنبيه حين يتجاوز الحدّ**.
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { formatMoney } from "@/lib/utils";

import "@/screens/t2/money.css";

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
    <div className={pause.over_max ? "t2-m-meter gap warn" : "t2-m-meter gap"}>
      <div className="t2-m-meter-row">
        <div>
          <div className="t2-m-meter-label">
            {pause.kind === "arrival"
              ? "الكبتن ينتظرك عند نقطة الانطلاق"
              : "الكبتن واقفٌ بطلبك"}
          </div>
          {/* الوقتُ يُحسب هنا — والمالُ لا */}
          <div dir="ltr" className="t2-m-clock">
            {elapsed(pause.started_at, now)}
          </div>
        </div>
        <div className="t2-m-meter-end">
          {/* **والمهلةُ تُقال قبل أن تنتهي لا بعدها**: راكبٌ يرى صفراً ولا يعرف
              لماذا يظنّ العدّادَ معطوباً، ثم يفاجئه رقمٌ بعد دقيقة */}
          <div className="t2-m-meter-label">
            {billing ? "رسم الانتظار حتى الآن" : `أول ${free} دقائق مجاناً`}
          </div>
          <div className="t2-m-meter-charge">{formatMoney(ride.pause_charge, ride.currency)}</div>
        </div>
      </div>
      {pause.over_max ? (
        <p className="t2-m-meter-note">
          <span className="t2-icon" aria-hidden="true">error</span>
          <span>
            تجاوز الانتظارُ الحدَّ المسموح — العدّادُ ما زال يعمل، وللكبتن أن
            يُنهي الرحلة عند هذه النقطة.
          </span>
        </p>
      ) : null}
    </div>
  );
}
