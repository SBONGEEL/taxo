/** أيقونةٌ من Material Symbols Rounded (الهوية) **باسمها**.
 *
 * **والخطُّ مقتطعٌ بأسماء ما يُستعمل** في `index.html` كلِّ تطبيق — **فمن أضاف أيقونةً أضاف اسمَها هناك**، وإلا ظهر اسمُها نصّاً.
 * و`fill` للممتلئة (التبويبُ النشط، والملاحظة). **وزينةٌ لا نصّ** (`aria-hidden`): المعنى في الكلمة التي بجانبها.
 */
/** **أيقوناتٌ لها اتّجاه** — رُسمت للعربيّة («رجوع» `arrow_forward`، و«تقدّم» `chevron_left`)، **فتنقلب في واجهةٍ من اليسار** (الفرنسيّة،
 *  §٧٦-ع/٢): كان سهمُ الرجوع يشير يميناً في الفرنسيّة. والقلبُ في `primitives.css` (`.t2-icon-dir`). */
const DIRECTIONAL = new Set(["arrow_forward", "arrow_back", "chevron_left", "chevron_right"]);

export function Icon({ name, fill = false, className }: { name: string; fill?: boolean; className?: string }) {
  const classes = ["t2-icon", fill ? "fill" : null, DIRECTIONAL.has(name) ? "t2-icon-dir" : null, className].filter(Boolean).join(" ");
  return (
    <span className={classes} aria-hidden="true">
      {name}
    </span>
  );
}
