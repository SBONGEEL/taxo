/** شروطُ الحقل قائمةً تُعلَّم **لحظةَ الكتابة** — SPEC القسم ١٧.٧.
 *
 * **ولا نصَّ عربيٌّ يُكتب هنا**: البنودُ تصل من `GET /config` (`conditions`)
 * مولَّدةً من المخطط نفسِه، وهذا المكوّنُ يرسمها ويقرّر أيُّها محقَّق. فبندٌ
 * يصوغه التطبيقُ يحتاج تصريفَ العدد العربيِّ مرةً ثانية («محرفٌ واحد» ·
 * «محرفان» · «٨ محارف» · «١٢٨ محرفاً»)، وصياغتان لشرطٍ واحدٍ تفترقان.
 *
 * **ولماذا قائمةٌ لا رسالةٌ بعد الضغط**: من كتب سبعَ خاناتٍ ورأى زراً معطَّلاً
 * يخمّن ما نقص. والقائمةُ تجيبه قبل أن يسأل — وتبقى ظاهرةً بعد التحقّق، فيرى
 * ما استوفاه لا ما أخطأ فيه فقط.
 *
 * **وغيابُ القاعدة يعني ألّا تُرسم قائمةٌ أصلاً** — لا قائمةٌ فارغةٌ ولا
 * افتراضاتٌ محلية: أوّلُ إقلاعٍ بلا شبكةٍ ولا نسخةٍ مخزَّنة يترك الحكمَ
 * للخلفية، وقائمةٌ نخترعها حينئذٍ قد تخالف ما تفرضه فعلاً.
 */

import type { FieldRule } from "@/api/types";
import { cn } from "@/lib/utils";

interface Props {
  rule: FieldRule | null | undefined;
  value: string;
}

/** هل استوفى النصُّ هذا الشرط؟ — يُقاس على القاعدة نفسِها لا على نصِّ البند. */
function satisfied(key: string, rule: FieldRule, value: string): boolean {
  switch (key) {
    case "min_length":
      return rule.min_length === undefined || value.length >= rule.min_length;
    case "max_length":
      return rule.max_length === undefined || value.length <= rule.max_length;
    case "min":
      return rule.min === undefined || Number(value) >= rule.min;
    case "max":
      return rule.max === undefined || Number(value) <= rule.max;
    default:
      return false;
  }
}

export function FieldConditions({ rule, value }: Props) {
  if (!rule?.conditions?.length) return null;

  return (
    <ul className="mt-6 flex flex-col gap-4">
      {rule.conditions.map((condition) => {
        const ok = satisfied(condition.key, rule, value);
        return (
          <li
            key={condition.key}
            className={cn(
              "flex items-center gap-6 text-11.5",
              ok ? "text-ok" : "text-muted",
            )}
          >
            {/* علامةٌ لا لونٌ وحدَه: من لا يميّز الألوان يقرأ الحالةَ كذلك */}
            <span aria-hidden>{ok ? "✓" : "•"}</span>
            <span>{condition.label}</span>
          </li>
        );
      })}
    </ul>
  );
}
