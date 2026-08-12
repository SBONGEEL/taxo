/** حوارٌ مركزيّ — `DESIGN.md` §2.4 بالقياسات نفسها التي كانت في `Campaigns`.
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="max-h-[86vh] w-modal max-w-full overflow-auto rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-16 text-16 font-bold text-ink">{title}</h2>
        {children}
      </div>
    </div>
  );
}
