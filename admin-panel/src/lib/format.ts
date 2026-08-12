/** صياغةُ ما يُعرض — تاريخٌ وعملةٌ ومبلغ، في مكانٍ واحد.
 *
 * كُتب حين صارت شاشاتُ المرحلة 11 اثنتَي عشرة: `CURRENCY_LABEL` ودالةُ الوقت
 * كانتا منسوختين في ثلاث شاشات، ونسخةٌ رابعةٌ تعني أربع صياغاتٍ تفترق يوم
 * تتغيّر واحدة.
 *
 * **ولا حسابَ هنا ولا تمريرَ مالٍ عبر `Number`.** المبالغ تصل نصّاً
 * (`NUMERIC(12,3)` يُسلسَل نصّاً)، والتعريبُ يقع على **الخانات** لا على
 * القيمة — `Intl.NumberFormat` يمرّ بـfloat فيفقد الدقة حيث لا تُلاحظ
 * (`DESIGN-DECISIONS.md` بند 17). أما الأعداد الصحيحة (عدد رحلات، نسبة
 * مئوية) فلا مانع من صياغتها، ومع ذلك تمر بنفس الباب كي لا يبقى بابان.
 */

import type { Currency } from "@/api/types";

import { arabicDigits } from "@/lib/utils";

/** العملةُ **بعد** الرقم وبمقاسٍ أصغر ولونٍ `--mut` (DESIGN.md §4). */
export const CURRENCY_LABEL: Record<Currency, string> = {
  JOD: "د.أ",
  LYD: "د.ل",
};

export function currencyLabel(currency: Currency | string | null | undefined) {
  return CURRENCY_LABEL[(currency ?? "JOD") as Currency] ?? "";
}

/** مبلغٌ بخاناتٍ عربية-هندية ورمزِ عملته — والقيمةُ تبقى نصّاً كما وصلت. */
export function money(value: string, currency?: Currency | string) {
  const label = currency ? ` ${currencyLabel(currency)}` : "";
  return `${arabicDigits(value)}${label}`;
}

/** يومٌ وشهرٌ ووقت — ما يُقرأ في صفوف الجداول. */
export function moment(iso: string) {
  const at = new Date(iso);
  return `${at.toLocaleDateString("ar-EG", {
    day: "numeric",
    month: "long",
  })} ${at.toLocaleTimeString("ar-EG", { hour: "numeric", minute: "2-digit" })}`;
}

/** يومٌ وشهرٌ بلا وقت — لتسميات الرسوم وصفوف الاشتراكات. */
export function day(iso: string) {
  return new Date(iso).toLocaleDateString("ar-EG", {
    day: "numeric",
    month: "long",
  });
}

/** يومٌ قصير (٥/٨) — تسميةٌ تحت عمودٍ في رسمٍ لا تتسع لأكثر. */
export function shortDay(iso: string) {
  const at = new Date(iso);
  return arabicDigits(`${at.getDate()}/${at.getMonth() + 1}`);
}

/** فرقُ الأيام حتى تاريخٍ في المستقبل — سالبٌ لما مضى. */
export function daysUntil(iso: string, now: number = Date.now()) {
  return Math.ceil((new Date(iso).getTime() - now) / 86_400_000);
}
