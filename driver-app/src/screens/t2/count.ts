/** **العددُ بالعربية في شاشات الكبتن** — بيتٌ واحدٌ لـC09 وC10 وC12.
 *
 * المثنّى بحالته (`genitive`: بعد حرف جرٍّ — «خلال يومين»، «منذ يومين»)، والتمييزُ جمعاً من ٣ إلى ١٠ ومفرداً منصوباً
 * فوقها («12 يوماً»)، **والخاناتُ لاتينية** (§20). */

import { digits } from "@/lib/utils";

export function countDays(n: number, genitive = false): string {
  if (n === 1) return "يوم";
  if (n === 2) return genitive ? "يومين" : "يومان";
  if (n <= 10) return `${digits(String(n))} أيام`;
  return `${digits(String(n))} يوماً`;
}

/** **«4:10»** — ساعاتٌ ودقائقُ كما رسمتها C04، من دقائقَ تصل من الخلفية (تنسيقٌ لا حساب). */
export function hoursClock(minutes: number): string {
  return digits(`${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`);
}

/** **«31 ساعة»** كما رسمتها C09 — ساعاتٌ تامّةٌ بعدِّ `countHours` نفسِه، و«أقلّ من ساعة» تحتها. */
export function workedHours(minutes: number): string {
  const n = Math.floor(minutes / 60);
  return n === 0 ? "أقلّ من ساعة" : countHours(n);
}

/** «42 رحلة» كما رسمتها C09 — و«رحلتان» و«3 رحلات»، والصفرُ «لا رحلات». */
export function countRides(n: number): string {
  if (n === 0) return "لا رحلات";
  if (n === 1) return "رحلة واحدة";
  if (n === 2) return "رحلتان";
  if (n <= 10) return `${digits(String(n))} رحلات`;
  return `${digits(String(n))} رحلة`;
}

/** «حجزٌ واحد» و«حجزان» و«3 حجوز» و«12 حجزاً» — عددُ الحجوز المضمونة على مدخل الرئيسية (§٦٣-ج/٣). */
export function countBookings(n: number): string {
  if (n === 1) return "حجزٌ واحد";
  if (n === 2) return "حجزان";
  if (n <= 10) return `${digits(String(n))} حجوز`;
  return `${digits(String(n))} حجزاً`;
}

/** «مشوارٌ واحد» و«مشواران» و«3 مشاوير» و«12 مشواراً» — عددُ المشاوير الثابتة على مدخل الرئيسية (§٦٣-ج/٦). */
export function countCommutes(n: number): string {
  if (n === 1) return "مشوارٌ واحد";
  if (n === 2) return "مشواران";
  if (n <= 10) return `${digits(String(n))} مشاوير`;
  return `${digits(String(n))} مشواراً`;
}

/** «مقعدٌ واحد» و«مقعدان» و«3 مقاعد» و«12 مقعداً» — مقاعدُ رحلة «بين المدن» وركّابِها (§٦٣-ج/٧). */
export function countSeats(n: number): string {
  if (n === 1) return "مقعدٌ واحد";
  if (n === 2) return "مقعدان";
  if (n <= 10) return `${digits(String(n))} مقاعد`;
  return `${digits(String(n))} مقعداً`;
}

export function countHours(n: number, genitive = false): string {
  if (n === 1) return "ساعة";
  if (n === 2) return genitive ? "ساعتين" : "ساعتان";
  if (n <= 10) return `${digits(String(n))} ساعات`;
  return `${digits(String(n))} ساعة`;
}
