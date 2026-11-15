/**
 * **ورقةُ طلب الراكب الجديدة** (SPEC §١٠٢، أمرُ المالك ٢٠٢٦-١١-١٥/١٦) — مفتاحُها وما يُحسب لعرضها **بلا React**،
 * فيُقاس بـ`node --test` (`tests/order-sheet.test.ts`).
 *
 * **لا مالَ يُحسب هنا** (§14): السعرُ يصل من الخلفية نصّاً مقرَّباً، وهذا **يقرّر كيف يُكتب** وحدَه —
 * «12 د.أ» إن كانت خاناتُه الكسريّةُ أصفاراً، و«12.500 د.أ» إن لم تكن. فلا رقمَ يتغيّر، تسقط الأصفارُ وحدَها.
 */

export const ORDER_SHEET_V2 = "rider_order_sheet_v2";

/** «12.000» ⇐ «12»، و«12.500» ⇐ «12.500»، و«1,250.000» ⇐ «1,250» — **قصٌّ لأصفارٍ لا تقريب**. */
export function compactAmount(formatted: string): string {
  const match = /^(.*?)\.(\d+)$/.exec(formatted);
  if (!match) return formatted;
  return /^0+$/.test(match[2]) ? match[1] : formatted;
}

/** **الخياراتُ المشتعلة رقاقاتٍ تحت الفئات** — مفاتيحُ بترتيبٍ ثابت، والتسميةُ عند الشاشة (`tr`)؛ وما لم يُشعَل لا رقاقةَ له. */
export type OptionKey = "bargain" | "share" | "forOther" | "schedule";

export function activeChips(options: { bargain: boolean; share: boolean; forOther: boolean; scheduling: boolean }): OptionKey[] {
  const keys: OptionKey[] = [];
  if (options.bargain) keys.push("bargain");
  if (options.share) keys.push("share");
  if (options.forOther) keys.push("forOther");
  if (options.scheduling) keys.push("schedule");
  return keys;
}

/** **سطرُ العنوان الواحد** — «،،» و«، ،» والفاصلةُ في الطرفين تسقط (ممّا يكتبه المزوّدون)، والاسمُ كما هو. */
export function oneLine(address: string | null | undefined): string {
  if (!address) return "";
  return address
    .replace(/\s*[،,]\s*(?=[،,])/g, "")
    .replace(/^[\s،,]+|[\s،,]+$/g, "")
    .replace(/\s*[،,]\s*/g, "، ")
    .replace(/\s+/g, " ")
    .trim();
}
