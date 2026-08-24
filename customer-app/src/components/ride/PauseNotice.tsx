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
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { cn, formatMoney } from "@/lib/utils";

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
    <div
      className={cn(
        "mt-10 rounded-13 border p-12",
        pause.over_max ? "border-warn bg-surface-2" : "border-line bg-surface-2",
      )}
    >
      <div className="flex items-end justify-between gap-10">
        <div>
          <p className="text-12 text-muted">
            {pause.kind === "arrival"
              ? "الكبتن ينتظرك عند نقطة الانطلاق"
              : "الكبتن واقفٌ بطلبك"}
          </p>
          {/* الوقتُ يُحسب هنا — والمالُ لا */}
          <p className="text-20 font-bold tabular-nums text-ink">
            {elapsed(pause.started_at, now)}
          </p>
        </div>
        <div className="text-end">
          {/* **والمهلةُ تُقال قبل أن تنتهي لا بعدها**: راكبٌ يرى صفراً ولا يعرف
              لماذا يظنّ العدّادَ معطوباً، ثم يفاجئه رقمٌ بعد دقيقة */}
          <p className="text-12 text-muted">
            {billing ? "رسم الانتظار حتى الآن" : `أول ${free} دقائق مجاناً`}
          </p>
          <p className="font-bold text-ink">
            {formatMoney(ride.pause_charge, ride.currency)}
          </p>
        </div>
      </div>
      {pause.over_max ? (
        <p className="mt-8 text-12 leading-relaxed text-warn">
          تجاوز الانتظارُ الحدَّ المسموح — العدّادُ ما زال يعمل، وللكبتن أن
          يُنهي الرحلة عند هذه النقطة.
        </p>
      ) : null}
    </div>
  );
}
