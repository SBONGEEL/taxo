/** الوقتُ كما تكتبه لوحةُ TAXO 2.0 — **بيتٌ واحدٌ لشاشاتها** (R11 · R12).
 *
 * «اليوم · 10:12» · «أمس · 21:40» · «2 أكتوبر · 08:05»، ورأسُ الشهر «أكتوبر 2026» — **بخاناتٍ
 * لاتينية** (`DISPLAY_LOCALE`) كقاعدة المشروع كلِّه، وساعةٍ بأربعٍ وعشرين كما في اللوحة.
 */

import { DISPLAY_LOCALE } from "@/lib/utils";

const DAY_MS = 24 * 60 * 60 * 1000;

/** منتصفُ ليل اليوم بتوقيت الجهاز — منه يُقال «اليوم» و«أمس». */
export function startOfToday(): number {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

/** اليومُ والساعةُ منفصلين: الساعةُ تُرسم في `dir="ltr"` كي لا تنقلب خاناتُها. */
export function whenParts(iso: string, today: number): { day: string; time: string } {
  const at = new Date(iso);
  const time = at.toLocaleTimeString(DISPLAY_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const ms = at.getTime();
  if (ms >= today) return { day: "اليوم", time };
  if (ms >= today - DAY_MS) return { day: "أمس", time };
  return { day: at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }), time };
}

/** **موعدٌ قادم** كما ترسمه بطاقةُ «مجدولة» (R12): «غداً · 06:15 ص» — **بساعةٍ من اثنتي عشرة وص/م** كما في اللوحة
 *  (بطاقاتُ الماضي بأربعٍ وعشرين، وهذا رسمُها هي). */
export function aheadParts(iso: string, today: number): { day: string; time: string; half: string } {
  const at = new Date(iso);
  const hours = at.getHours();
  const time = `${String(hours % 12 || 12).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  const half = hours < 12 ? "ص" : "م";
  const ms = at.getTime();
  if (ms < today + DAY_MS) return { day: "اليوم", time, half };
  if (ms < today + 2 * DAY_MS) return { day: "غداً", time, half };
  return { day: at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }), time, half };
}

/** رأسُ الشهر: «أكتوبر 2026». */
export function monthOf(iso: string): string {
  return new Date(iso).toLocaleDateString(DISPLAY_LOCALE, { month: "long", year: "numeric" });
}

/** سلاسلُ متّصلةٌ بالشهر **بالترتيب الذي تصل به** (الأحدثُ أوّلاً من الخلفية). */
export function byMonth<T>(items: T[], dateOf: (item: T) => string): { label: string; items: T[] }[] {
  const months: { label: string; items: T[] }[] = [];
  for (const item of items) {
    const label = monthOf(dateOf(item));
    const last = months[months.length - 1];
    if (last && last.label === label) last.items.push(item);
    else months.push({ label, items: [item] });
  }
  return months;
}
