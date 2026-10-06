/** شريطُ حارسٍ مطفأ — يُقرأ في الشاشة التي عُطّلت أزرارُها.
 *
 * **والزرُّ يُعطَّل ولا يُخفى** (قاعدةُ المشروع): زرٌّ يعمل ثم يردّ ٤٠٣ يعلّم
 * صاحبَه أن يعيد الضغط، **وزرٌّ يختفي يُقرأ عطباً في اللوحة** — فيُترك مكانَه
 * معطَّلاً وتُقال علّتُه فوقه.
 *
 * **وبيتٌ واحدٌ للشريطين** لأن نصَّهما واحدُ الشكل، والثاني يُنسخ عند ثالث.
 */
import type { ReactNode } from "react";

import { Icon } from "@/taxo2";

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
  // **بلاغُ الهوية بنغمة التنبيه** (`kit.css` — `.ad-banner`): حالٌ قائمةٌ لا حدث
  return (
    <div className="ad-banner" role="status">
      <Icon name="warning" fill />
      <div>
        <p className="ad-banner-title">{title}</p>
        <p className="ad-banner-body">{children}</p>
      </div>
    </div>
  );
}
