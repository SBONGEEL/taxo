/** **بحثُ القوائم الكاملة في اللوحة** — يستعمله `Table` (`search`)، ونقيٌّ بلا React فيُختبر وحدَه (`tests/table-search.test.ts`). */

/** **نصُّ الصفّ من قيمه نفسِها** (`search` بلا دالّة) — النصوصُ والأرقامُ في الصفّ وفي كائناته المتداخلة إلى عمقين:
 * الاسمُ والهاتفُ والمرجعُ والمبلغُ كما وصلت من الخادم. **ولا يطابق تسميةً تُرسم ولا تُخزَّن** (اسمُ حالٍ عربيٌّ لرمزٍ لاتينيّ) —
 * فلذلك حبّاتُ الفلترة، أو دالّةُ `text` صريحة. */
export function rowText(row: unknown, depth = 0): string {
  if (row === null || row === undefined) return "";
  if (typeof row === "string" || typeof row === "number") return String(row);
  if (depth > 2 || typeof row !== "object") return "";
  return Object.values(row as Record<string, unknown>)
    .map((value) => rowText(value, depth + 1))
    .filter(Boolean)
    .join(" ");
}

/** **طيُّ النصّ للمطابقة**: حالةُ الحروف اللاتينيّة، والهمزاتُ والتاءُ المربوطةُ والألفُ المقصورة، والتشكيلُ والتطويل، والخاناتُ العربيّة-الهنديّة إلى لاتينيّة. */
export function foldSearch(value: string): string {
  return value
    .toLowerCase()
    .replace(/[\u064B-\u0652\u0640]/g, "")
    .replace(/[\u0623\u0625\u0622\u0671]/g, "\u0627")
    .replace(/\u0629/g, "\u0647")
    .replace(/\u0649/g, "\u064A")
    .replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/\s+/g, " ")
    .trim();
}
