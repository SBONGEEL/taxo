import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/** مقاساتُ الخط كما في `DESIGN.md` §6 — و`check:scale` يمنع افتراقها عنه.
 *
 * **لماذا تُذكر هنا أصلاً**: `tailwind-merge` يعرف سلالم Tailwind الافتراضية
 * لا سلّمنا. ومقاساتُنا **بالبكسل** (`text-14.5`) لا بمقاسات القُمصان
 * (`text-sm`)، فلا يتعرّف عليها كمقاسِ خطٍّ ويصنّفها **لوناً** — فتتصادم
 * `text-14` مع `text-ink` في نداءٍ واحد ويسقط أحدهما بصمت.
 *
 * وهذا وقع فعلاً مرتين قبل أن يُكتشف: تسميةُ الشريط السفلي خرجت بلا مقاس
 * (`cn("block text-9.5 text-ink")` أسقط 9.5)، وزرُّ «طلب سحب» خرج **بنصٍّ
 * غير مرئي** — `text-14` أسقط `text-accent-ink` فورث الزرُّ لونَ النص الفاتح
 * على تعبئةٍ فاتحة. البناءُ أخضر في الحالتين، و`check:scale` لا يراهما لأن
 * الصنفَ مكتوبٌ صحيحاً وموجودٌ في CSS — الذي يحذفه هو الدمج وقت التشغيل.
 */
// prettier-ignore
const FONT_SIZES = [
  "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "13.5",
  "14", "14.5", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
  "25", "26", "30", "32", "34", "38", "44",
];

const twMerge = extendTailwindMerge({
  override: { classGroups: { "font-size": [{ text: FONT_SIZES }] } },
});

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
