/** طبقةٌ كاملةٌ لمرحلةِ تأكيد — `DESIGN.md` §1.5 (z 60) وتصميمُ الراكب
 *  (`payShow` / `rateShow`).
 *
 * **وليست ورقةً سفلية.** قياسُ النموذج: `inset:0; background:var(--bg);
 * z-index:60; justify-content:center; animation:fadein` — خلفيةٌ معتمةٌ كاملةٌ
 * ومحتوىً **موسَّطٌ رأسياً**، بلا شريط عنوانٍ ولا تعتيمٍ خلفه. وهذا ما يفرّقها
 * عن `Sheet`: الورقةُ تُعلَّق فوق ما تنظر إليه فتبقى الشاشةُ حاضرةً وراءها،
 * والطبقةُ **تحلّ محلَّها** لأن اللحظةَ لحظةُ قرارٍ واحد.
 *
 * **وزرُّ الرجوع يبقى** خلافاً للنموذج (الذي يخرج بزرِّ الإجراء وحده): الدفعُ
 * ليس إلزامياً في هذا النظام — الخلفيةُ تقبل الدفعَ لاحقاً وسجلُّ الرحلات يحمل
 * «إكمال الدفع» — فشاشةٌ لا تُغادر إلا بالدفع تحبس من أراد المراجعة. والتقييمُ
 * له «تخطَّ» أصلاً، فالزرُّ فيه راحةٌ لا مخرجٌ وحيد.
 */

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export function Stage({
  onBack,
  children,
  className,
}: {
  onBack?: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-[60] flex flex-col justify-center bg-bg px-26 pb-16 pt-safe"
    >
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label="رجوع"
          className="absolute end-16 top-16 rounded-full p-8 text-muted transition hover:bg-surface-2"
        >
          <ChevronRight className="size-20" />
        </button>
      ) : null}
      <div className={cn("scr max-h-full", className)}>{children}</div>
    </motion.div>
  );
}
