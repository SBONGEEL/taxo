/** **ورقةُ TAXO 2.0 فوق الخريطة** — حجرٌ بمقبض، ومنطقةٌ تُمرَّر، وقدمٌ ثابتة (R06–R09).
 *
 * **والسلوكُ سلوكُ الورقة القائمة بعينه** (`components/ui/Sheet`): تنزلق من أسفل وتغادر إليه، **وسقفُها محجوزٌ من
 * الأعلى بالمرئيّ** (`--vvh`، لا `dvh` الذي يمتدّ تحت لوحة المفاتيح)، **وتُرفع بالمحجوب** (`--vv-bottom`)، **والقدمُ
 * خارج التمرير** — فالمبلغُ وزرُّ الالتزام لا يغيبان عن العين مهما طال ما فوقهما (إذنُ المالك ٢٠٢٦-٠٨-٢٣).
 *
 * **وتطفو فوق شريط التبويب لا تحته**: اللوحةُ ترسمها ملتصقةً بأسفل الشاشة بلا شريط، **والشريطُ باقٍ في أطوار الطلب**
 * — فبه يبلغ الراكبُ محفظتَه ورحلاتِه وهو في رحلة (`TAXO2-DESIGN-CORRECTIONS.md` §٢٣).
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { DURATION, EASE } from "@/lib/motion";

export function SheetT2({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={{ duration: DURATION.med, ease: EASE.standard }}
      className="t2 t2-sheet"
    >
      <div className="t2-sheet-grab" aria-hidden="true" />
      <div className="t2-sheet-body">{children}</div>
      {footer ? <div className="t2-sheet-foot">{footer}</div> : null}
    </motion.div>
  );
}
