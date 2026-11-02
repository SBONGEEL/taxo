/** **زرُّ «كن راكباً» العريض** — أعلى «حسابي»، تحت الاسم مباشرةً (أمرُ المالك ٢٠٢٦-١١-٠٢).
 *
 * **ولمَ هنا**: «حسابي» تبويبٌ في الشريط السفليّ يُبلغ بلمسةٍ من أيِّ شاشة، **وأعلاه أوّلُ ما يُرى فيه** — فالزرُّ ظاهرٌ لمن
 * يبحث عنه، **والرئيسيةُ تبقى للعمل**: بطاقةُ الطلب والرحلة الجارية لا يزاحمهما زرٌّ يُخرج الكبتنَ من تطبيقه. **وكان قبله صفّاً
 * صغيراً قبل الخروج** («تبديل إلى تطبيق الراكب») — فحلّ هذا محلَّه، ومعه صفحةُ «غير مثبَّت» التي صار التنزيلُ المباشرُ يغني عنها.
 *
 * **والشكلُ بطاقةُ الحبر بدائرة الجمر** — نسخةُ تطبيق الراكب بلغة TAXO 2.0 نفسِها. **والمنطقُ كلُّه في `useBecomeRider`**.
 */

import { useBecomeRider } from "@/lib/switch-app";
import { Icon } from "@/taxo2";

import "./become.css";

/** `compact` ⇒ **شريطُ الرئيسية** (أمرُ المالك ٢٠٢٦-١١-٠٢، الثاني): الزرُّ نفسُه بمنطقه بارتفاعٍ أقلّ وسطرٍ واحد — ظاهرٌ
 *  تحت ما جاء له صاحبُ الرئيسية لا فوقه. والعريضُ يبقى أعلى «حسابي». */
export function BecomeRiderButton({ compact = false }: { compact?: boolean } = {}) {
  const become = useBecomeRider();
  if (!become.visible) return null;
  return (
    <div className={compact ? "t2-become-wrap compact" : "t2-become-wrap"}>
      <button type="button" className={compact ? "t2-become compact" : "t2-become"} disabled={become.busy} onClick={() => void become.press()}>
        <span className="t2-become-stripe" aria-hidden="true" />
        <span className="t2-become-icon" aria-hidden="true">
          {/* **من الأسماء المقتطعة في `index.html`** — `hail` ليس منها، وأيقونةٌ خارج القائمة تُرسم اسمَها نصّاً */}
          <Icon name="person" />
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
