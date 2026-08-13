/** بدائيّاتُ الحركة — `DESIGN.md` §8.
 *
 * **مكوّناتٌ لا أنماطٌ منسوخة**: الحركةُ التي تُكتب في كلِّ شاشةٍ بيدها تصير
 * عشرين حركةً لا يجمعها شيء، فيُقرأ التطبيقُ مضطرباً بلا أن يخطئ أحد.
 *
 * **و`prefers-reduced-motion` يُعطَّل من مكانٍ واحد**: `MotionConfig` في `App`
 * بـ`reducedMotion="user"` — فتصير كلُّ حركةٍ في Framer فوريةً بلا أن يفحص
 * مكوّنٌ واحدٌ التفضيل. وما يبقى من انتقالات CSS يُلغى بـ`motion-reduce:`.
 */

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

import { DURATION, EASE, SLIDE_PX, STAGGER_STEP } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** انتقالُ الشاشات **باتجاه التنقّل** لا باتجاهٍ ثابت.
 *
 * `useNavigationType()` يميّز `POP` (رجوعٌ بزرِّ النظام أو بسهم الشاشة) من
 * `PUSH`. والاتجاهُ **منطقيٌّ لا فيزيائي**: التطبيقُ عربيٌّ RTL، فالتقدّمُ
 * يدخل من جهة البداية (اليسار بصرياً) والرجوعُ يعكسه — وشاشةٌ تدخل من الجهة
 * الخطأ تُقرأ رجوعاً وهي تقدّم.
 */
export function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const back = useNavigationType() === "POP";
  const from = back ? SLIDE_PX : -SLIDE_PX;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        className="h-full"
        initial={{ opacity: 0, x: from }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -from }}
        transition={{ duration: DURATION.med, ease: EASE.standard }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/** ظهورُ عناصر القائمة بتتابع — الحاويةُ تحمل التوقيت والعنصرُ يحمل الشكل. */
export function Stagger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="shown"
      variants={{
        shown: { transition: { staggerChildren: STAGGER_STEP } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 8 },
        shown: { opacity: 1, y: 0 },
      }}
      transition={{ duration: DURATION.med, ease: EASE.outSoft }}
    >
      {children}
    </motion.div>
  );
}

/** هيكلٌ عظميٌّ بدل شاشةٍ فارغة (§8).
 *
 * **ولماذا لا دوّامة؟** الدوّامةُ تقول «انتظر» ولا تقول ماذا يأتي؛ والهيكلُ
 * يرسم **شكلَ ما سيصل**، فتستقرّ العينُ على مواضعه قبل أن يصل المحتوى ولا
 * تقفز حين يصل. وتفاصيلُ الرحلة تنتظر ثلاثةَ نداءاتٍ متتابعة — ثوانٍ كانت
 * سواداً كاملاً.
 *
 * والنبضُ `animate-pulse` من Tailwind، ويُلغيه `motion-reduce`.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-12 bg-surface-2 motion-reduce:animate-none",
        className,
      )}
    />
  );
}
