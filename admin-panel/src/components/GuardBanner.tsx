/** شريطُ حارسٍ مطفأ — يُقرأ في الشاشة التي عُطّلت أزرارُها.
 *
 * **والزرُّ يُعطَّل ولا يُخفى** (قاعدةُ المشروع): زرٌّ يعمل ثم يردّ ٤٠٣ يعلّم
 * صاحبَه أن يعيد الضغط، **وزرٌّ يختفي يُقرأ عطباً في اللوحة** — فيُترك مكانَه
 * معطَّلاً وتُقال علّتُه فوقه.
 *
 * **وبيتٌ واحدٌ للشريطين** لأن نصَّهما واحدُ الشكل، والثاني يُنسخ عند ثالث.
 */
import type { ReactNode } from "react";

export function GuardBanner({
  on,
  title,
  children,
}: {
  /** `true` حين يكون الحارسُ **مطفأً** — أي حين يجب أن يظهر الشريط. */
  on: boolean;
  title: string;
  children: ReactNode;
}) {
  if (!on) return null;
  return (
    <div className="mb-16 rounded-13 border border-warn bg-surface-2 px-16 py-13">
      <p className="text-14 font-semibold text-ink">{title}</p>
      <p className="mt-6 text-13 leading-relaxed text-muted">{children}</p>
    </div>
  );
}
