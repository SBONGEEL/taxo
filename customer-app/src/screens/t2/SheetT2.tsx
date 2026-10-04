/** **ورقةُ TAXO 2.0 فوق الخريطة** — حجرٌ بمقبض، ومنطقةٌ تُمرَّر، وقدمٌ ثابتة (R06–R09).
 *
 * **والسلوكُ سلوكُ الورقة القائمة بعينه** (`components/ui/Sheet`): تنزلق من أسفل وتغادر إليه، **وسقفُها محجوزٌ من
 * الأعلى بالمرئيّ** (`--vvh`، لا `dvh` الذي يمتدّ تحت لوحة المفاتيح)، **وتُرفع بالمحجوب** (`--vv-bottom`)، **والقدمُ
 * خارج التمرير** — فالمبلغُ وزرُّ الالتزام لا يغيبان عن العين مهما طال ما فوقهما (إذنُ المالك ٢٠٢٦-٠٨-٢٣).
 *
 * **وملتصقةٌ بأسفل الشاشة بلا شريط تبويب كما رُسمت** (R06، §٦١-د) — أطوارُ الطلب تغطّي الشريط (`lib/navCover`)،
 * ولكلِّ طورٍ مخرجُه إلى الرئيسية (السهمُ و«إلغاء»). **و`floating` لما يبقى الشريطُ تحته**: «إلى أين؟» حين لا يُعرف
 * الانطلاق — لا سهمَ فيها يعيد، فالشريطُ مخرجُها.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { DURATION, EASE } from "@/lib/motion";

export function SheetT2({
  children,
  footer,
  floating = false,
}: {
  children: ReactNode;
  footer?: ReactNode;
  floating?: boolean;
}) {
  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={{ duration: DURATION.med, ease: EASE.standard }}
      className={floating ? "t2 t2-sheet floating" : "t2 t2-sheet"}
    >
      <div className="t2-sheet-grab" aria-hidden="true" />
      <div className="t2-sheet-body">{children}</div>
      {footer ? <div className="t2-sheet-foot">{footer}</div> : null}
    </motion.div>
  );
}
