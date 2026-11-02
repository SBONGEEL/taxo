/** **طبقاتُ الرجوع** — زرُّ الرجوع يغلق الطبقةَ العليا خطوةً خطوة (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩٣-ب).
 *
 * **العطبُ الذي أنشأ هذا الملف**: الأوراقُ (`vaul`) والطبقاتُ المرسومةُ بيدٍ لا تدخل تاريخَ الملاح، فزرُّ الجهاز كان يقرأ التاريخَ
 * وحده — **ورقةٌ مفتوحةٌ على الرئيسية والتاريخُ صفرٌ ⇒ يُغلق التطبيقُ كلُّه** بدل أن تُغلق الورقة. وما دخل التاريخَ بيدٍ
 * (`useExpandable`) دخله بلا `idx` فقرأه الزرُّ صفراً وأغلق التطبيقَ كذلك.
 *
 * **فالقاعدة**: كلُّ طبقةٍ تُفتح تسجّل مُغلِقَها هنا ما دامت مفتوحة، والزرُّ يسأل هذا المكدَّسَ **قبل** التاريخ — آخرُ ما فُتح أوّلُ
 * ما يُغلق. **وما لا يُغلق بالرجوع لا يسجّل**: بوّابةُ التحديث الإلزاميّ وإعادةُ الموافقة وعرضُ الطلب على الكبتن (رفضُه فعلٌ
 * يُقصد لا رجوعٌ يقع).
 *
 * **ونسختُه في تطبيق الكبتن حرفاً.**
 */

import { useEffect, useRef } from "react";

type Layer = { close: () => void };

const stack: Layer[] = [];

/** يسجّل طبقةً مفتوحة ويعيد نزعَها. */
export function pushBackLayer(close: () => void): () => void {
  const layer: Layer = { close };
  stack.push(layer);
  return () => {
    const at = stack.indexOf(layer);
    if (at >= 0) stack.splice(at, 1);
  };
}

/** يغلق الطبقةَ العليا إن وُجدت — `true` إن أغلق شيئاً. */
export function closeTopLayer(): boolean {
  const top = stack.pop();
  if (!top) return false;
  top.close();
  return true;
}

/** **الطبقةُ ما دامت مفتوحة** — والمُغلِقُ الأحدثُ يُنادى، فلا يُغلق بقيمةٍ قديمة. */
export function useBackLayer(open: boolean, close: () => void): void {
  const latest = useRef(close);
  latest.current = close;
  useEffect(() => {
    if (!open) return;
    return pushBackLayer(() => latest.current());
  }, [open]);
}
