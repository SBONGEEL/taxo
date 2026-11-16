/** **ورقةُ TAXO 2.0 فوق الخريطة** — حجرٌ بمقبض، ومنطقةٌ تُمرَّر، وقدمٌ ثابتة (R06–R09).
 *
 * **والسلوكُ سلوكُ الورقة القائمة بعينه** (`components/ui/Sheet`): تنزلق من أسفل وتغادر إليه، **وسقفُها محجوزٌ من
 * الأعلى بالمرئيّ** (`--vvh`، لا `dvh` الذي يمتدّ تحت لوحة المفاتيح)، **وتُرفع بالمحجوب** (`--vv-bottom`)، **والقدمُ
 * خارج التمرير** — فالمبلغُ وزرُّ الالتزام لا يغيبان عن العين مهما طال ما فوقهما (إذنُ المالك ٢٠٢٦-٠٨-٢٣).
 *
 * **وملتصقةٌ بأسفل الشاشة بلا شريط تبويب كما رُسمت** (R06، §٦١-د) — أطوارُ الطلب تغطّي الشريط (`lib/navCover`)،
 * ولكلِّ طورٍ مخرجُه إلى الرئيسية (السهمُ و«إلغاء»). **و`floating` لما يبقى الشريطُ تحته**: «إلى أين؟» حين لا يُعرف
 * الانطلاق — لا سهمَ فيها يعيد، فالشريطُ مخرجُها.
 *
 * **و`snap` ارتفاعان يُسحبان بالإصبع** (قرارُ المالك ٢٠٢٦-١١-١٦، SPEC §١٠٥/١): تُفتح بنصف الشاشة فيبقى المسارُ ظاهراً،
 * وسحبُ المقبض للأعلى (أو لمسُه) يملؤها وللأسفل يعيدها. **لا يُحذف شيء**: ما زاد على النصف يُمرَّر داخلها، والقدمُ ثابتة.
 */

import { motion } from "framer-motion";
import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";

import { tr } from "@/lib/i18n";
import { DURATION, EASE } from "@/lib/motion";
import { SNAP_PX, snapAfterDrag, type SheetSnap } from "@/lib/sheet-snap";

export function SheetT2({
  children,
  footer,
  floating = false,
  snap = false,
}: {
  children: ReactNode;
  footer?: ReactNode;
  floating?: boolean;
  /** ارتفاعان بالسحب — نصفٌ عند الفتح وملءٌ بالسحب */
  snap?: boolean;
}) {
  const [height, setHeight] = useState<SheetSnap>("half");
  const [dragging, setDragging] = useState<number | null>(null);
  const start = useRef<{ y: number; h: number } | null>(null);
  const sheet = useRef<HTMLDivElement>(null);

  function down(event: ReactPointerEvent<HTMLElement>) {
    if (!snap) return;
    start.current = { y: event.clientY, h: sheet.current?.getBoundingClientRect().height ?? 0 };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function move(event: ReactPointerEvent<HTMLElement>) {
    if (!start.current) return;
    const delta = start.current.y - event.clientY;
    if (Math.abs(delta) < 4) return;
    setDragging(Math.max(120, start.current.h + delta));
  }
  function up(event: ReactPointerEvent<HTMLElement>) {
    if (!start.current) return;
    const delta = start.current.y - event.clientY;
    start.current = null;
    setDragging(null);
    // **لمسةٌ بلا سحبٍ تبدّل** — والسحبُ يقرّر باتّجاهه بعد عتبةٍ صغيرة
    setHeight((current) => (Math.abs(delta) < SNAP_PX ? (current === "half" ? "full" : "half") : snapAfterDrag(current, delta)));
  }

  const classes = ["t2", "t2-sheet"];
  if (floating) classes.push("floating");
  if (snap) classes.push("snap", height);
  return (
    <motion.div
      ref={sheet}
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: 24, opacity: 0 }}
      transition={{ duration: DURATION.med, ease: EASE.standard }}
      className={classes.join(" ")}
      style={dragging !== null ? { maxHeight: dragging, height: dragging, transition: "none" } : undefined}
    >
      {snap ? (
        <button
          type="button"
          className="t2-sheet-grab-zone"
          aria-label={height === "half" ? tr("وسّع الورقة") : tr("صغّر الورقة")}
          aria-expanded={height === "full"}
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setHeight((current) => (current === "half" ? "full" : "half"));
            }
          }}
          onPointerCancel={() => {
            start.current = null;
            setDragging(null);
          }}
        >
          <span className="t2-sheet-grab" aria-hidden="true" />
        </button>
      ) : (
        <div className="t2-sheet-grab" aria-hidden="true" />
      )}
      <div className="t2-sheet-body">{children}</div>
      {footer ? <div className="t2-sheet-foot">{footer}</div> : null}
    </motion.div>
  );
}
