/** أيقونةٌ **باسمها** — من مجموعة TAXO الجديدة (`glyphs.ts`) حين يشتعل `icons_v2`، **ومن Material Symbols Rounded كما كانت حين يُطفأ**.
 *
 * **والخطُّ مقتطعٌ بأسماء ما يُستعمل** في `index.html` كلِّ تطبيق — **فمن أضاف أيقونةً أضاف اسمَها هناك**، وإلا ظهر اسمُها نصّاً
 * والمجموعةُ مطفأة. و`fill` للممتلئة (التبويبُ النشط، والملاحظة). **وزينةٌ لا نصّ** (`aria-hidden`): المعنى في الكلمة التي بجانبها.
 *
 * و`art` لأيقونة الفئة: **رسمُ سيّارةٍ** من `CAR_ART` حين تشتعل المجموعةُ ويكون للاسم رسم، وإلا الأيقونةُ نفسُها.
 */
import { CAR_ART, GLYPHS } from "./glyphs";
import { useIconSetV2 } from "./iconSet";
import "./glyphs.css";

/** **أيقوناتٌ لها اتّجاه** — رُسمت للعربيّة («رجوع» `arrow_forward`، و«تقدّم» `chevron_left`)، **فتنقلب في واجهةٍ من اليسار** (الفرنسيّة،
 *  §٧٦-ع/٢): كان سهمُ الرجوع يشير يميناً في الفرنسيّة. والقلبُ في `primitives.css` (`.t2-icon-dir`). */
const DIRECTIONAL = new Set(["arrow_forward", "arrow_back", "chevron_left", "chevron_right"]);

export function Icon({ name, fill = false, className, art = false }: { name: string; fill?: boolean; className?: string; art?: boolean }) {
  const v2 = useIconSetV2();
  const classes = ["t2-icon", fill ? "fill" : null, DIRECTIONAL.has(name) ? "t2-icon-dir" : null, className].filter(Boolean).join(" ");
  if (v2 && art && CAR_ART[name]) {
    return <svg className={`t2-car ${className ?? ""}`.trim()} viewBox="0 0 48 28" aria-hidden="true" dangerouslySetInnerHTML={{ __html: CAR_ART[name] }} />;
  }
  if (v2 && GLYPHS[name]) {
    return (
      <svg className={`${classes} t2-glyph g-${name}`} viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: GLYPHS[name] }} />
    );
  }
  return (
    <span className={classes} aria-hidden="true">
      {name}
    </span>
  );
}
