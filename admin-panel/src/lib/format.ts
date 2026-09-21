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

import type { CountryCode, Currency } from "@/api/types";

import { counted, digits, DISPLAY_LOCALE } from "@/lib/utils";

/** العملةُ **بعد** الرقم وبمقاسٍ أصغر ولونٍ `--mut` (DESIGN.md §4). */
export const CURRENCY_LABEL: Record<Currency, string> = {
  JOD: "د.أ",
  LYD: "د.ل",
};

/** عملةُ الدولة — **الخلفيةُ لا تُرسلها مع كل إعدادٍ per-country**، فتُشتق هنا.
 *
 * وبيتٌ واحدٌ لها لا نسخةٌ في كل شاشة: النسخةُ المحلية في `PromoCodes.tsx` هي
 * ما جعل تمريرَ **التسمية** مكانَ **الرمز** ممكناً، فطُبعت المبالغُ بلا عملةٍ
 * أصلاً. والفرقُ بين `"JOD"` و`"د.أ"` لا يراه المصرِّف.
 */
export function currencyOf(country: CountryCode): Currency {
  return country === "JO" ? "JOD" : "LYD";
}

export function currencyLabel(currency: Currency | string | null | undefined) {
  return CURRENCY_LABEL[(currency ?? "JOD") as Currency] ?? "";
}

/** مبلغٌ بخاناتٍ عربية-هندية ورمزِ عملته — والقيمةُ تبقى نصّاً كما وصلت. */
export function money(value: string, currency?: Currency | string) {
  const label = currency ? ` ${currencyLabel(currency)}` : "";
  return `${digits(value)}${label}`;
}

/** يومٌ وشهرٌ ووقت — ما يُقرأ في صفوف الجداول. */
export function moment(iso: string) {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, {
    day: "numeric",
    month: "long",
  }))} ${digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }))}`;
}

/** **متى كان ذلك** — «منذ 5 دقائق»، والدقيقُ يبقى في تلميح التمرير.
 *
 * **ولمَ نسبيٌّ على الشاشة ودقيقٌ في التلميح**: من يقرأ لوحةَ أعطالٍ يسأل
 * «أما زال يقع الآن؟» — و«3:07 م» تحتاج منه أن يحسب، **والحسابُ في رأس
 * القارئ هو ما تُبنى الشاشاتُ لتغنيَه عنه**. والدقيقُ يبقى لمن يطابق سطرَ
 * سجلٍّ بوقته، فلا يضيع.
 *
 * **والأشكالُ مصرَّحةٌ لا مخترعة** (`counted`): «منذ دقيقتين» لا «منذ 2 دقيقة».
 */
const MINUTE_FORMS = {
  one: "دقيقة",
  two: "دقيقتين",
  few: "دقائق",
  many: "دقيقة",
  bare: "دقيقة",
};
const HOUR_FORMS = {
  one: "ساعة",
  two: "ساعتين",
  few: "ساعات",
  many: "ساعة",
  bare: "ساعة",
};
const DAY_FORMS = {
  one: "يوم",
  two: "يومين",
  few: "أيام",
  many: "يوماً",
  bare: "يوم",
};

export function sinceNow(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "الآن";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `منذ ${counted(minutes, MINUTE_FORMS)}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `منذ ${counted(hours, HOUR_FORMS)}`;
  return `منذ ${counted(Math.floor(hours / 24), DAY_FORMS)}`;
}

/** الوقتُ الدقيقُ لتلميح التمرير — **ما يُطابَق به سطرُ سجلّ**. */
export function exactMoment(iso: string): string {
  const at = new Date(iso);
  return digits(
    at.toLocaleString(DISPLAY_LOCALE, {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    }),
  );
}

/** يومٌ وشهرٌ بلا وقت — لتسميات الرسوم وصفوف الاشتراكات. */
export function day(iso: string) {
  return new Date(iso).toLocaleDateString(DISPLAY_LOCALE, {
    day: "numeric",
    month: "long",
  });
}

/** يومٌ قصير (٥/٨) — تسميةٌ تحت عمودٍ في رسمٍ لا تتسع لأكثر. */
export function shortDay(iso: string) {
  const at = new Date(iso);
  return digits(`${at.getDate()}/${at.getMonth() + 1}`);
}

/** فرقُ الأيام حتى تاريخٍ في المستقبل — سالبٌ لما مضى. */
export function daysUntil(iso: string, now: number = Date.now()) {
  return Math.ceil((new Date(iso).getTime() - now) / 86_400_000);
}

/** «يوم» مع عددها بتمييزٍ عربيٍّ صحيح.
 *
 * العددُ في العربية يغيّر تمييزَه: واحدٌ واثنان بلا عدد، ومن ثلاثةٍ إلى عشرة
 * جمعٌ (**أيام**)، ومن أحدَ عشرَ فصاعداً مفردٌ منصوب (**يوماً**). و«٣٠ يوم»
 * تُقرأ ركيكةً في شاشةٍ كلُّ نصِّها عربيٌّ مضبوط — والرقمُ نفسه لا يتغيّر،
 * فالتمييزُ وحده ما يُصحَّح.
 */
export function days(count: number): string {
  const n = Math.abs(count);
  const shown = digits(String(n));
  if (n === 1) return "يوم واحد";
  if (n === 2) return "يومان";
  if (n >= 3 && n <= 10) return `${shown} أيام`;
  return `${shown} يوماً`;
}
