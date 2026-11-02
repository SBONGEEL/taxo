/** **زرُّ «كن سائقاً» العريض** — أعلى «حسابي»، تحت الاسم مباشرةً (أمرُ المالك ٢٠٢٦-١١-٠٢).
 *
 * **ولمَ هنا**: «حسابي» تبويبٌ في الشريط السفليّ يُبلغ بلمسةٍ من أيِّ شاشة، **وأعلاه أوّلُ ما يُرى فيه** — فالزرُّ ظاهرٌ لمن
 * يبحث عنه دون أن يقف في طريق من جاء ليطلب مشواراً (الرئيسيةُ للطلب وحدَه). **وكان قبله صفّاً صغيراً قبل الخروج** («تبديل إلى
 * تطبيق السائق») لا يجده إلا من يعرف مكانه — فحلّ هذا محلَّه، ومعه صفحةُ «غير مثبَّت» التي صار التنزيلُ المباشرُ يغني عنها.
 *
 * **والشكلُ بطاقةُ الحبر بدائرة الجمر** — لغةُ R28 التي رُسمت لهذا الفعل نفسِه، فلا لونَ جديد. **والمنطقُ كلُّه في `useBecomeDriver`**.
 */

import { useBecomeDriver } from "@/lib/switch-app";
import { Icon } from "@/taxo2";

import "./become.css";

/** `compact` ⇒ **شريطُ الرئيسية** (أمرُ المالك ٢٠٢٦-١١-٠٢، الثاني): الزرُّ نفسُه بمنطقه بارتفاعٍ أقلّ وسطرٍ واحد — ظاهرٌ
 *  تحت ما جاء له صاحبُ الرئيسية لا فوقه. والعريضُ يبقى أعلى «حسابي». */
export function BecomeDriverButton({ compact = false }: { compact?: boolean } = {}) {
  const become = useBecomeDriver();
  if (!become.visible) return null;
  return (
    <div className={compact ? "t2-become-wrap compact" : "t2-become-wrap"}>
      <button type="button" className={compact ? "t2-become compact" : "t2-become"} disabled={become.busy} onClick={() => void become.press()}>
        <span className="t2-become-stripe" aria-hidden="true" />
        <span className="t2-become-icon" aria-hidden="true">
          <Icon name="local_taxi" />
        </span>
        <span className="t2-become-main">
          <span className="t2-become-title">{become.label}</span>
          <span className="t2-become-sub">{become.sub}</span>
        </span>
        <Icon name="arrow_back" className="t2-become-go" />
      </button>
      {become.blocked ? (
        <p className="t2-become-note" role="status">
          {become.blocked}
        </p>
      ) : null}
    </div>
  );
}
