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

/** **وجوهُ العملات من الخلفية لا من هنا** (SPEC §٧٣-ج/١٢) — علامتُها واسمُها وخاناتُها تُنشر مع كلِّ دولةٍ في `/config`
 *  (`core/currency.py`)، **ويُملأ هذا السجلُّ لحظةَ وصولها** قبل أن تُرسم شاشة (`registerCurrencies` في `lib/config.tsx` و`lib/countries.tsx`).
 *
 *  **كانت العلامةُ مكتوبةً هنا بالسوقين** (`{ JOD: "د.أ", LYD: "د.ل" }`) — **فسوقٌ ثالثٌ يُرسم رمزاً خاماً** ولا يفشل شيء. */
interface CurrencyFace {
  label: string;
  name: string;
  decimals: number;
}
const CURRENCY_FACES = new Map<string, CurrencyFace>();

export function registerCurrencies(
  countries: ReadonlyArray<{
    currency: string;
    currency_label: string;
    currency_name: string;
    currency_decimals: number;
  }>,
): void {
  for (const country of countries) {
    CURRENCY_FACES.set(country.currency, {
      label: country.currency_label,
      name: country.currency_name,
      decimals: country.currency_decimals,
    });
  }
}

/** **خاناتُ العملة** — وثلاثٌ لما لا يُعرف بعد، كما كانت الصياغةُ قبل §٧٣ حرفاً. */
export function currencyDecimals(currency: string | null | undefined): number {
  return (currency ? CURRENCY_FACES.get(currency)?.decimals : undefined) ?? 3;
}

/** **صفرُ العملة نصّاً** — «0.000» للأردنيّ والليبيّ و«0» للجزائريّ. **ولا `"0.000"` مكتوبةٌ في شاشة** (الحارس `check:market-literals`). */
export function zeroAmount(currency: string | null | undefined): string {
  const places = currencyDecimals(currency);
  return places > 0 ? `0.${"0".repeat(places)}` : "0";
}

/** **أصفرٌ هذا المبلغ؟** — نصّيّاً لا بعائم: «0» و«0.000» و«-0.000» صفرٌ بأيِّ خانات. */
export function isZeroAmount(amount: string | null | undefined): boolean {
  return /^-?0+(\.0+)?$/.test((amount ?? "").trim());
}

const COUNTRY_CURRENCY = new Map<string, Currency>();

/** **ويُسجَّل معها عملةُ كلِّ دولة** — من `/config` (الظاهرة) ومن `/admin/countries` (كلُّها، والمخفيّةُ منها). */
export function registerCountryCurrencies(countries: ReadonlyArray<{ country_code: string; currency: Currency }>): void {
  for (const country of countries) COUNTRY_CURRENCY.set(country.country_code, country.currency);
}

/** عملةُ الدولة — **من وصفها المنشور لا من شرطٍ بدولتين** (SPEC §٧٣-ج/١٢).
 *
 * وبيتٌ واحدٌ لها لا نسخةٌ في كل شاشة: النسخةُ المحلية في `PromoCodes.tsx` هي
 * ما جعل تمريرَ **التسمية** مكانَ **الرمز** ممكناً، فطُبعت المبالغُ بلا عملةٍ
 * أصلاً. والفرقُ بين `"JOD"` و`"د.أ"` لا يراه المصرِّف.
 *
 * **وكانت `country === "JO" ? "JOD" : "LYD"`** — فسوقٌ ثالثٌ يُرسم بعملة ليبيا ولا يفشل شيء. و`undefined` لدولةٍ لم يصل وصفُها بعد،
 * **لا عملةُ سوقٍ آخر تُخمَّن**. */
export function currencyOf(country: CountryCode): Currency | undefined {
  return COUNTRY_CURRENCY.get(country);
}

export function currencyLabel(currency: Currency | string | null | undefined) {
  return currency ? (CURRENCY_FACES.get(currency)?.label ?? currency) : "";
}

/** مبلغٌ بخاناتٍ عربية-هندية ورمزِ عملته — والقيمةُ تبقى نصّاً كما وصلت. */
export function money(value: string, currency?: Currency | string) {
  const label = currency ? ` ${currencyLabel(currency)}` : "";
  return `${digits(value)}${label}`;
}

/** يومٌ وشهرٌ ووقت — ما يُقرأ في صفوف الجداول.
 *
 * **`timeZone` اختياريّ — وبغيره يُقرأ الوقتُ بمِنطقة المتصفّح.** شاشةٌ تعرض حدودَ يوم سوقٍ بعينه (الملخّصاتُ المالية) تمرّر
 * مِنطقتَه كما أرسلتها الخلفية: عرضُ ليبيا من متصفّحٍ في عمّان كان يبدأ «اليوم» الساعةَ 01:00 تحت عنوان `Africa/Tripoli`،
 * **ويخالف الملفَّ المصدَّر بساعة** (`finance_export.py` يكتب بيوم السوق).
 */
export function moment(iso: string, timeZone?: string) {
  const at = new Date(iso);
  const zone = timeZone ? { timeZone } : {};
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, {
    day: "numeric",
    month: "long",
    ...zone,
  }))} ${digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit", ...zone }))}`;
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
