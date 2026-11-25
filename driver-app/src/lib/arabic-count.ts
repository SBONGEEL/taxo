/** **العددُ مع معدوده بالعربيّة** (أمرُ المالك ٢٠٢٦-١١-٢٥: «يتبقّى 1 أيام» ⇒ «يتبقّى يوم واحد») — بيتٌ واحدٌ للتطبيقين، **ونسخةٌ
 * واحدةٌ فيهما حرفاً** (`customer-app/src/lib/arabic-count.ts`).
 *
 * ١ «يوم واحد» · ٢ «يومان» (و«يومين» بعد حرف جرٍّ أو مضاف: `after`) · ٣–١٠ «3 أيام» · ١١–٩٩ «11 يوماً» · ١٠٠ و١٠١ و١٠٢ «100 يوم»
 * · والصفرُ «0 يوم». **وفوق المئة بآخر خانتين** (١٠٣ «أيام»، ١١١ «يوماً»)، والكسرُ بصيغة المفرد («1.5 ساعة»).
 * **والخاناتُ لاتينيّة** (§20). **وفي الفرنسيّة** العددُ ثمّ المفردُ للصفر والواحد والجمعُ لما فوقهما («1 jour» · «3 jours») —
 * لا من `fr.json`: «يومان» فيه «Deux jours» بحرفٍ كبيرٍ لموضعٍ آخر، وصيغُ المثنّى لا مقابلَ لها.
 *
 * **ولمَ لا يُكتب العددُ في القالب** («يتبقّى {0} أيام»): القالبُ يثبّت صيغةً واحدةً لكلِّ عدد، فيصدق على ٣–١٠ ويكذب على غيرها —
 * **وكان يُرى «يتبقّى 1 أيام» على هاتف كبتن**. فالقالبُ يحمل المعدودَ كاملاً («يتبقّى {0}») وهذا يصوغه.
 */
import { language, tr } from "@/lib/i18n";
import { digits } from "@/lib/utils";

export interface CountUnit {
  /** «يوم واحد» */
  one: string;
  /** «يومان» — رفعاً */
  two: string;
  /** «يومين» — بعد حرف جرٍّ أو مضاف («بعد يومين»، «أكمل رحلتين») */
  twoAfter: string;
  /** «{0} أيام» — من ٣ إلى ١٠ */
  few: string;
  /** «{0} يوماً» — من ١١ إلى ٩٩ */
  many: string;
  /** «{0} يوم» — الصفرُ والمئاتُ التامّةُ والكسور */
  base: string;
  /** الفرنسيّة: [المفرد، الجمع] */
  fr: readonly [string, string];
}

export const DAYS: CountUnit = { one: "يوم واحد", two: "يومان", twoAfter: "يومين", few: "{0} أيام", many: "{0} يوماً", base: "{0} يوم", fr: ["jour", "jours"] };
export const HOURS: CountUnit = { one: "ساعة واحدة", two: "ساعتان", twoAfter: "ساعتين", few: "{0} ساعات", many: "{0} ساعةً", base: "{0} ساعة", fr: ["heure", "heures"] };
export const MINUTES: CountUnit = { one: "دقيقة واحدة", two: "دقيقتان", twoAfter: "دقيقتين", few: "{0} دقائق", many: "{0} دقيقةً", base: "{0} دقيقة", fr: ["minute", "minutes"] };
export const RIDES: CountUnit = { one: "رحلة واحدة", two: "رحلتان", twoAfter: "رحلتين", few: "{0} رحلات", many: "{0} رحلةً", base: "{0} رحلة", fr: ["course", "courses"] };
export const POINTS: CountUnit = { one: "نقطة واحدة", two: "نقطتان", twoAfter: "نقطتين", few: "{0} نقاط", many: "{0} نقطةً", base: "{0} نقطة", fr: ["point", "points"] };

/** «يوم واحد» · «يومان» · «3 أيام» · «11 يوماً» · «100 يوم» — والعددُ بخاناتٍ لاتينيّة. */
export function countOf(value: number | string, unit: CountUnit, after = false): string {
  const n = Number(value);
  const shown = { 0: digits(String(value)) };
  if (language === "fr") return `${shown[0]} ${Math.abs(n) < 2 ? unit.fr[0] : unit.fr[1]}`;
  if (!Number.isFinite(n) || !Number.isInteger(n)) return tr(unit.base, shown);
  const whole = Math.abs(n);
  if (whole === 1) return tr(unit.one);
  if (whole === 2) return tr(after ? unit.twoAfter : unit.two);
  const tail = whole % 100;
  if (whole === 0 || tail <= 2) return tr(unit.base, shown);
  if (tail <= 10) return tr(unit.few, shown);
  return tr(unit.many, shown);
}
