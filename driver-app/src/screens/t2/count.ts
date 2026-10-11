/** **العددُ بالعربية في شاشات الكبتن** — بيتٌ واحدٌ لـC09 وC10 وC12.
 *
 * المثنّى بحالته (`genitive`: بعد حرف جرٍّ — «خلال يومين»، «منذ يومين»)، والتمييزُ جمعاً من ٣ إلى ١٠ ومفرداً منصوباً
 * فوقها («12 يوماً»)، **والخاناتُ لاتينية** (§20). */

import { digits } from "@/lib/utils"; import { tr } from "@/lib/i18n";

export function countDays(n: number, genitive = false): string {
  if (n === 1) return tr("يوم");
  if (n === 2) return genitive ? tr("يومين") : tr("يومان");
  if (n <= 10) return tr("{0} أيام", { 0: digits(String(n)) });
  return tr("{0} يوماً", { 0: digits(String(n)) });
}

/** **«4:10»** — ساعاتٌ ودقائقُ كما رسمتها C04، من دقائقَ تصل من الخلفية (تنسيقٌ لا حساب). */
export function hoursClock(minutes: number): string {
  return digits(`${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`);
}

/** **«31 ساعة»** كما رسمتها C09 — ساعاتٌ تامّةٌ بعدِّ `countHours` نفسِه، و«أقلّ من ساعة» تحتها. */
export function workedHours(minutes: number): string {
  const n = Math.floor(minutes / 60);
  return n === 0 ? tr("أقلّ من ساعة") : countHours(n);
}

/** «42 رحلة» كما رسمتها C09 — و«رحلتان» و«3 رحلات»، والصفرُ «لا رحلات». */
export function countRides(n: number): string {
  if (n === 0) return tr("لا رحلات");
  if (n === 1) return tr("رحلة واحدة");
  if (n === 2) return tr("رحلتان");
  if (n <= 10) return tr("{0} رحلات", { 0: digits(String(n)) });
  return tr("{0} رحلة", { 0: digits(String(n)) });
}

/** «حجزٌ واحد» و«حجزان» و«3 حجوز» و«12 حجزاً» — عددُ الحجوز المضمونة على مدخل الرئيسية (§٦٣-ج/٣). */
export function countBookings(n: number): string {
  if (n === 1) return tr("حجزٌ واحد");
  if (n === 2) return tr("حجزان");
  if (n <= 10) return tr("{0} حجوز", { 0: digits(String(n)) });
  return tr("{0} حجزاً", { 0: digits(String(n)) });
}

/** «مشوارٌ واحد» و«مشواران» و«3 مشاوير» و«12 مشواراً» — عددُ المشاوير الثابتة على مدخل الرئيسية (§٦٣-ج/٦). */
export function countCommutes(n: number): string {
  if (n === 1) return tr("مشوارٌ واحد");
  if (n === 2) return tr("مشواران");
  if (n <= 10) return tr("{0} مشاوير", { 0: digits(String(n)) });
  return tr("{0} مشواراً", { 0: digits(String(n)) });
}

/** «مقعدٌ واحد» و«مقعدان» و«3 مقاعد» و«12 مقعداً» — مقاعدُ رحلة «بين المدن» وركّابِها (§٦٣-ج/٧). */
export function countSeats(n: number): string {
  if (n === 1) return tr("مقعدٌ واحد");
  if (n === 2) return tr("مقعدان");
  if (n <= 10) return tr("{0} مقاعد", { 0: digits(String(n)) });
  return tr("{0} مقعداً", { 0: digits(String(n)) });
}

export function countHours(n: number, genitive = false): string {
  if (n === 1) return tr("ساعة");
  if (n === 2) return genitive ? tr("ساعتين") : tr("ساعتان");
  if (n <= 10) return tr("{0} ساعات", { 0: digits(String(n)) });
  return tr("{0} ساعة", { 0: digits(String(n)) });
}
