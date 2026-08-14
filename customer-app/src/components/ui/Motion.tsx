/** بدائيّاتُ الحركة — `DESIGN.md` §8.
 *
 * **مكوّناتٌ لا أنماطٌ منسوخة**: الحركةُ التي تُكتب في كلِّ شاشةٍ بيدها تصير
 * عشرين حركةً لا يجمعها شيء، فيُقرأ التطبيقُ مضطرباً بلا أن يخطئ أحد.
 *
 * **و`prefers-reduced-motion` يُعطَّل من مكانٍ واحد**: `MotionConfig` في `App`
 * بـ`reducedMotion="user"` — فتصير كلُّ حركةٍ في Framer فوريةً بلا أن يفحص
 * مكوّنٌ واحدٌ التفضيل. وما يبقى من انتقالات CSS يُلغى بـ`motion-reduce:`.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Suspense, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

import { Spinner } from "@/components/ui/Feedback";
import { DURATION, EASE, SLIDE_PX, STAGGER_STEP } from "@/lib/motion";
import { isBackward } from "@/lib/nav-order";
import { cn } from "@/lib/utils";

/** انتقالُ الشاشات — **باتجاه التنقّل، ومقيساً في المتصفح لا مفترضاً**.
 *
 * ثلاثةُ أشياء يجب أن تجتمع، وكان اثنان منها ناقصَين حتى قِيست الحركةُ في
 * المتصفح فتبيّن أنها **لا تعمل على أيِّ مسار**: لا `transform` ولا `opacity`
 * يتغيّران في أيِّ إطار، والشاشةُ تُستبدل استبدالاً.
 *
 * ١. **`Suspense` تحت الحركة لا فوقها.** المساراتُ كسولةٌ (`lazy`)، فأوّلُ
 *    انتقالٍ إلى شاشةٍ لم تُحمَّل يُعلِّق الشجرةَ — و`Suspense` فوق
 *    `AnimatePresence` يستبدل **الشجرةَ كلَّها** ببديله، فيموت الخروجُ قبل أن
 *    يبدأ ويولد الدخولُ بلا أبٍ يتحرك. قِيس: مؤشّرُ تحميلٍ يظهر في منتصف كلِّ
 *    انتقال. فصار البديلُ **داخل** العنصر المتحرك: الورقةُ تنزلق وفيها مؤشّرُها.
 * ٢. **`Routes` مُثبَّتةٌ على موقعها.** بلا `location` تقرأ `Routes` الموقعَ
 *    الحاليَّ من السياق، فتُعيد النسخةُ **الخارجة** رسمَ الشاشة **الداخلة** —
 *    أي أن ما يخرج مسحوباً هو الشاشةُ الجديدة نفسُها. حركةٌ تقول عكسَ ما يقع.
 * ٣. **الاتجاهُ من رتبة المسار** (`lib/nav-order.ts`) لا من نوع التنقّل وحدَه:
 *    `navigate("/account")` بعد حفظٍ رجوعٌ يقرؤه السجلُّ تقدّماً.
 *
 * **و`prefers-reduced-motion` يُعطَّل من مكانٍ واحد**: `MotionConfig` في `App`
 * بـ`reducedMotion="user"` — فتصير كلُّ حركةٍ في Framer فوريةً بلا أن يفحص
 * مكوّنٌ واحدٌ التفضيل. وما يبقى من انتقالات CSS يُلغى بـ`motion-reduce:`.
 *
 * والاتجاهُ **منطقيٌّ لا فيزيائي**: التطبيقُ عربيٌّ RTL، فالتقدّمُ يدخل من جهة
 * البداية والرجوعُ يعكسه — وشاشةٌ تدخل من الجهة الخطأ تُقرأ رجوعاً وهي تقدّم.
 */
export function RouteTransition({
  children,
}: {
  /** دالةٌ تأخذ الموقعَ المُثبَّت وتعيد `Routes` — انظر (٢) أعلاه. */
  children: (location: ReturnType<typeof useLocation>) => ReactNode;
}) {
  const location = useLocation();
  // **`MotionConfig` يُلغي الحركةَ لا نقطةَ البدء**، وقِيس: مع تقليل الحركة كانت
  // الورقةُ تُرسم إطاراً واحداً على `-24` ثم تستقر — قفزةٌ لمن طلب ألّا يرى حركة.
  // فالمكوّنُ الذي **يصرّح** بإزاحةٍ هو من يلغيها؛ وما يلغيه `MotionConfig` هو
  // الانتقالُ بينهما لا القيمةُ الأولى نفسُها
  const reduce = useReducedMotion();
  const popped = useNavigationType() === "POP";
  const previous = useRef(location.pathname);
  const back = isBackward(previous.current, location.pathname, popped);
  useEffect(() => {
    previous.current = location.pathname;
  }, [location.pathname]);
  const from = reduce ? 0 : back ? SLIDE_PX : -SLIDE_PX;

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
        {/* **البديلُ يملأ الورقةَ ويتوسّط** (البند ٤، قِيس على الجهاز): `Spinner`
            عارياً `flex justify-center py-32` — فيجلس في **أعلى** الورقة بلا
            ارتفاع، وينزلق معها فيُقرأ أيقونةً تائهةً في الزاوية. قِيس قبله:
            `x=-8, y=72, w=352` من إطارٍ عرضُه 384. */}
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center">
              <Spinner />
            </div>
          }
        >
          {children(location)}
        </Suspense>
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
