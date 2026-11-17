/** أيقونةٌ **باسمها** — من مجموعة TAXO الجديدة (`glyphs.ts`) حين يشتعل `icons_v2`، **ومن Material Symbols Rounded كما كانت حين يُطفأ**.
 *
 * **والخطُّ مقتطعٌ بأسماء ما يُستعمل** في `index.html` كلِّ تطبيق — **فمن أضاف أيقونةً أضاف اسمَها هناك**، وإلا ظهر اسمُها نصّاً
 * والمجموعةُ مطفأة. و`fill` للممتلئة (التبويبُ النشط، والملاحظة). **وزينةٌ لا نصّ** (`aria-hidden`): المعنى في الكلمة التي بجانبها.
 *
 * **والمجموعةُ الجديدةُ هي النمطُ C** (قرارُ المالك ١٧/١١/٢٠٢٦: «معتمدة»): ٣٦ رسماً ملوّناً على شبكة ٤٨ من `glyphsC.ts`، **وما ليس فيها يبقى
 * من الخطّ كما كان** — فالمجموعةُ الخطّيّةُ الأولى (`glyphs.ts`) لا تُرسم بعد اليوم (رفضها المالك ١٦/١١)، ويبقى ملفُّها حتى يُقرَّر حذفُه.
 *
 * و`art` لأيقونة الفئة: **مركبةُ النمط C** بثلاثة أرباع حين تشتعل المجموعةُ ويكون للاسم مركبة، وإلا الأيقونةُ نفسُها.
 */
import { GLYPHS_C, VEHICLES_C } from "./glyphsC";
import { useIconSetV2 } from "./iconSet";
import "./glyphs.css";

/** **أيقوناتٌ لها اتّجاه** — رُسمت للعربيّة («رجوع» `arrow_forward`، و«تقدّم» `chevron_left`)، **فتنقلب في واجهةٍ من اليسار** (الفرنسيّة،
 *  §٧٦-ع/٢): كان سهمُ الرجوع يشير يميناً في الفرنسيّة. والقلبُ في `primitives.css` (`.t2-icon-dir`). */
const DIRECTIONAL = new Set(["arrow_forward", "arrow_back", "chevron_left", "chevron_right"]);

export function Icon({ name, fill = false, className, art = false }: { name: string; fill?: boolean; className?: string; art?: boolean }) {
  const v2 = useIconSetV2();
  const classes = ["t2-icon", fill ? "fill" : null, DIRECTIONAL.has(name) ? "t2-icon-dir" : null, className].filter(Boolean).join(" ");
  if (v2 && art && VEHICLES_C.has(name)) {
    return <svg className={`t2-car ixc ${className ?? ""}`.trim()} viewBox="0 8 48 34" aria-hidden="true" dangerouslySetInnerHTML={{ __html: GLYPHS_C[name] }} />;
  }
  if (v2 && GLYPHS_C[name]) {
    return (
      <svg className={`${classes} ixc g-${name}`} viewBox="0 0 48 48" aria-hidden="true" dangerouslySetInnerHTML={{ __html: GLYPHS_C[name] }} />
    );
  }
  return (
    <span className={classes} aria-hidden="true">
      {name}
    </span>
  );
}
