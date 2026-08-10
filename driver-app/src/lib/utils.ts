import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** يبدّل الخانات اللاتينية بالعربية-الهندية **نصّياً**.
 *
 * التصميم يعرض كل الأرقام عربيةً-هنديةً (DESIGN.md §4)، والنماذج تفعل ذلك
 * بـ`toLocaleString("ar-EG")` — أي بتمرير العدد عبر `Number`. وهذا ممنوع على
 * المال: `NUMERIC(12,3)` يصل الواجهةَ **نصّاً**، وتمريرُه عبر float يفقد
 * دقّته حيث لا يُلاحظ (قرار `DESIGN-DECISIONS.md` بند 17). فالتبديل هنا على
 * الخانات لا على القيمة، ويصلح للمال ولغيره سواءً.
 */
export function arabicDigits(value: string): string {
  return value.replace(/[0-9]/g, (digit) => ARABIC_DIGITS[Number(digit)]);
}
