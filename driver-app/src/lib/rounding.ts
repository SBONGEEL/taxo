/** **التقريبُ في الواجهة: خطواتُ الوحدة وفحصُ ما يكتبه الكبتنُ بيده — لا حسابَ مال** (SPEC §٧٠-ج/٦ و§١٤).
 *
 * القاعدةُ في الخلفية (`services/rounding.py`): **ما يُحسب يُقرَّب هناك ويصل جاهزاً** — «كلُّ المتاح» للسحب أكبرُ مضاعفٍ للوحدة
 * (`available_for_withdrawal`، المثال ج)، و«سدّد كلَّه» الدَّينُ مقرَّباً للأعلى (`pay_all_amount`). **وما يكتبه الكبتنُ بيده**
 * (مبلغُ السحب ودفعةُ الدَّين) **مضاعفٌ للوحدة وإلا رُدّ** بـ`amount_not_multiple` ورسالةٍ عربيّة. فهذا الملفُّ يقول شيئين لا ثالثَ لهما:
 *
 * 1. **الوحدة** من `GET /config` (`rounding_unit`) حين يكون التقريبُ مشتعلاً، و`null` مطفأً — **فلا خطوات ولا فحص، كما كان حرفاً**.
 * 2. **«أهذا الرقمُ الذي كتبتَه مضاعفٌ لها؟»** — سؤالُ نعم/لا يمنع الوصولَ إلى الرفض ولا يستبدله: **الخلفيةُ تبقى الحاكمة**،
 *    ورسالتُها تُعرض كما وصلت إن ردّت.
 *
 * **ولا يُشتقّ هنا مبلغٌ يُعرض** (§١٤) — **والفحصُ بأجزاء الألف أعداداً صحيحة** لا بعائم. ونسختُه في تطبيق الراكب بالمنطق نفسِه،
 * والفرقُ صياغةُ العملة وحدَها (`digits` وتسميةٌ محلولة هنا، و`formatMoney` هناك).
 */

import type { CountryConfig } from "@/api/types";
import { digits } from "@/lib/utils";

/** **وحدةُ السوق حين يكون التقريبُ مشتعلاً**، و`null` مطفأً — والمطفأُ هو الحالُ القائمُ في كلِّ سوقٍ حتى يُشعَل من اللوحة. */
export function roundingUnit(country: CountryConfig | null | undefined): string | null {
  return country?.rounding_enabled ? country.rounding_unit : null;
}

/** أجزاءُ الألف عدداً صحيحاً — و`null` لنصٍّ ليس رقماً بثلاث خاناتٍ كسريّةٍ أو أقلّ: **لا يُحكم عليه هنا**، والخلفيةُ تردّه بسببه. */
function thousandths(text: string): number | null {
  const match = /^(\d+)(?:\.(\d{0,3}))?$/.exec(text.trim());
  if (!match) return null;
  return Number(match[1]) * 1000 + Number((match[2] ?? "").padEnd(3, "0"));
}

/** **سطرُ الخطوات تحت حقل المبلغ** — و`null` مطفأً. `label` تسميةُ العملة محلولةً («د.أ»). */
export function unitHint(unit: string | null, label: string): string | null {
  return unit === null ? null : `المبالغُ بخطواتِ ${digits(unit)} ${label} في بلدك`;
}

/** **«ليس مضاعفاً للوحدة»** — الرسالةُ أو `null`.
 *
 * `null` في كلِّ ما ليس حكماً: تقريبٌ مطفأ، أو حقلٌ فارغٌ أو صفر (الزرُّ معطَّلٌ له أصلاً)، أو نصٌّ لا يُقرأ رقماً. **وبلفظ رسالة
 * الخلفية** («المبلغُ يكون من مضاعفات…») — فلا يقرأ صاحبُه جملتين لقاعدةٍ واحدة.
 */
export function notMultipleMessage(typed: string, unit: string | null, label: string): string | null {
  if (unit === null) return null;
  const value = thousandths(typed);
  const step = thousandths(unit);
  if (value === null || step === null || value === 0 || step === 0) return null;
  return value % step === 0 ? null : `المبلغُ يكون من مضاعفات ${digits(unit)} ${label}`;
}
