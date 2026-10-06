/** حوارٌ مركزيّ — **ورقةُ سطحٍ بزاويةٍ ٢٤ فوق ظلّ `--t2-scrim`** (TAXO 2.0؛ كان `DESIGN.md` §2.4).
 *
 * **استُخرج من `screens/Campaigns.tsx` لا كُتب من جديد** (12-ز): جدولُ رموز
 * الخصم يحتاج الحوارَ نفسه، ونسخُه ملفَّين يجعل حوارين يفترقان في أول تعديلٍ
 * على الظل أو نصف القطر — وذاك أثرٌ يراه المستخدم ولا يراه المُصرِّف.
 *
 * والنقرُ على الخارج يُغلق، والنقرُ في الداخل لا يصعد (`stopPropagation`) —
 * بغيره يغلق كلُّ نقرٍ على حقلٍ الحوارَ كلَّه.
 */

import type { ReactNode } from "react";

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="ad-modal" onClick={onClose}>
      <div
        className="ad-modal-box"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="ad-modal-title">{title}</h2>
        {children}
      </div>
    </div>
  );
}
