/** أيقونةٌ من Material Symbols Rounded (الهوية) **باسمها**.
 *
 * **والخطُّ مقتطعٌ بأسماء ما يُستعمل** في `index.html` كلِّ تطبيق — **فمن أضاف أيقونةً أضاف اسمَها هناك**، وإلا ظهر اسمُها نصّاً.
 * و`fill` للممتلئة (التبويبُ النشط، والملاحظة). **وزينةٌ لا نصّ** (`aria-hidden`): المعنى في الكلمة التي بجانبها.
 */
export function Icon({ name, fill = false, className }: { name: string; fill?: boolean; className?: string }) {
  const classes = ["t2-icon", fill ? "fill" : null, className].filter(Boolean).join(" ");
  return (
    <span className={classes} aria-hidden="true">
      {name}
    </span>
  );
}
