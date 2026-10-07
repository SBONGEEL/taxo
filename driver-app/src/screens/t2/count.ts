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

export function countHours(n: number, genitive = false): string {
  if (n === 1) return "ساعة";
  if (n === 2) return genitive ? "ساعتين" : "ساعتان";
  if (n <= 10) return `${digits(String(n))} ساعات`;
  return `${digits(String(n))} ساعة`;
}
