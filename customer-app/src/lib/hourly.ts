/** **بالساعة** (§٦٣-ج/٥) — مفتاحُها في تطبيق الراكب، وساعتُها أثناء الرحلة، وعدُّ ساعاتها بعربيةٍ تُقرأ.
 *
 * **مطفأً لا يظهر شيءٌ جديد** (قاعدةُ `lib/parcel.ts`): بلاطةُ «بالساعة» تبقى «قريباً» كما كانت. **والرحلةُ القائمةُ تُقرأ من صفّها
 * لا من المفتاح** — `ride.ride_type` يصل دائماً، فرحلةٌ بالساعة جاريةٌ تبقى كذلك ولو أُطفئ المفتاحُ بعدها («الإطفاءُ يمنع الجديد
 * ولا يفكّ القائم»).
 *
 * **ولا مالَ يُحسب هنا** (§14): سعرُ الساعة والمجموعُ من التقدير، والكيلومتراتُ المشمولةُ من الرحلة (`hourly_included_km`).
 * **وما يُحسب وقتٌ لا مال**: الباقي من «البدء + الساعات»، وما زاد عليها بالدقائق — وما زاد يُسعَّر في الخلفية عند الإنهاء.
 */

import { useEffect, useState } from "react";

import type { Ride } from "@/api/types";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export function useHourly(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "hourly_enabled");
}

/** «ساعة واحدة · ساعتان · 3 ساعات · 11 ساعة» — **العربيةُ تعدّ بالمثنّى والجمع** (قاعدةُ `freeMinutes`)، والخاناتُ لاتينية (§20). */
export function hoursLabel(count: number): string {
  if (count === 1) return "ساعة واحدة";
  if (count === 2) return "ساعتان";
  if (count <= 10) return `${count} ساعات`;
  return `${count} ساعة`;
}

/** «لساعةٍ واحدة · لساعتين · لـ 3 ساعات» — **المجرورُ غيرُ المرفوع**: «لـ ساعتان» نحوٌ مكسورٌ تحت مبلغ. */
export function forHours(count: number): string {
  if (count === 1) return "لساعةٍ واحدة";
  if (count === 2) return "لساعتين";
  return `لـ ${hoursLabel(count)}`;
}

/** **رحلةٌ بالساعة بلا وجهة** — الطلبُ أرسل نقطةَ الانطلاق نفسَها وجهةً (عقدُ `HourlyIn`)، فالنقطتان متطابقتان. **ولا يُقرأ غيابُ
 *  العنوان** دليلاً: وجهةٌ من الدبوس قد تُطلب قبل أن يصل عنوانُها. */
export function noDestination(ride: Pick<Ride, "pickup" | "dropoff">): boolean {
  return ride.pickup.lat === ride.dropoff.lat && ride.pickup.lng === ride.dropoff.lng;
}

/** «1:59:30» أو «59:30» — **ساعةٌ رقميّةٌ بخاناتٍ لاتينية** (§20)، والساعاتُ حين تبلغ واحدةً وحدَها. */
export function clockText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

/** **ساعةُ الرحلة** — الباقي بالثواني حتى «البدء + الساعات»، **ثمّ ما زاد بالدقائق** (`over`، و`left` صفر). و`null` قبل البدء
 *  أو بلا ساعات. **تتقدّم كلَّ ثانية محلّياً** كعدّاد الوقفة (`PauseNotice`) — من نقطة البدء المقيسة لا من رقمٍ يصل مع كلِّ إطار. */
export function useHourlyClock(startedAt: string | null, hours: number | null): { left: number; over: number } | null {
  const [now, setNow] = useState(() => Date.now());
  const running = startedAt !== null && hours !== null;
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (!running) return null;
  const started = new Date(startedAt).getTime();
  if (Number.isNaN(started)) return null;
  const left = Math.round((started + hours * 3_600_000 - now) / 1000);
  return left > 0 ? { left, over: 0 } : { left: 0, over: Math.floor(-left / 60) };
}
