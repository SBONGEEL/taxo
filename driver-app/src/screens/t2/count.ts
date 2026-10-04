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

export function countHours(n: number, genitive = false): string {
  if (n === 1) return "ساعة";
  if (n === 2) return genitive ? "ساعتين" : "ساعتان";
  if (n <= 10) return `${digits(String(n))} ساعات`;
  return `${digits(String(n))} ساعة`;
}
