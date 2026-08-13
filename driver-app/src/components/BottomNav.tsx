/** الشريط السفلي — **حبّةٌ عائمة** (`DESIGN.md` §10.1، مرجعُ المالك البصري).
 *
 * **نسخةٌ من `customer-app/src/components/BottomNav.tsx` بتسمياتٍ أخرى**،
 * لا اشتقاقٌ جديد: التطبيقان يتقاسمان نظامَ التصميم نفسَه، وشريطان مبنيّان
 * مرتين يفترقان في أوّل قيمةٍ تُعدَّل في أحدهما.
 *
 * **عائمٌ لا ملتصق**: هامشٌ ١٦ من الجانبين و`max(14px, safe-area)` تحته، وارتفاعٌ
 * ٦٢ — ومجموعُ الاثنين هو `spacing.nav` (٧٦) الذي يحجزه `pb-nav` للمحتوى، فلا
 * ينزلق سطرٌ تحت الشريط. **وأُخذ الشكلُ من المرجع لا أسلوبُه**: المرجعُ
 * neumorphic بظلالٍ بارزة، وهذا نظامٌ مسطّح — فالعَوَمُ والحبّةُ الممتلئة نُقلا،
 * والظلالُ والتدرّجاتُ لا.
 *
 * **والنشطُ حبّةٌ ممتلئةٌ بـ`--brand`** ونصُّها `--brand-ink`، والخاملُ `--mut`:
 * يتبعان الوضعَ والسِمةَ الورديةَ بلا شرطٍ في المكوّن — `--brand` قيمتُها `--tx`
 * والسِمةُ مطفأة، فلا يتغيّر شيءٌ للحساب المحايد.
 *
 * **والحبّةُ تنزلق بـ`layoutId`** لا بحساب `translate` يدويّ: Framer يقيس
 * الموضعين ويحرّك بينهما، فيبقى صحيحاً مهما تغيّر عددُ التبويبات أو عرضُ
 * الشاشة — والحسابُ اليدويُّ `100% / n` كان يفترض تبويباتٍ متساويةً بالضبط.
 * و`prefers-reduced-motion` يوقفها من `MotionConfig` في `App` وحدَه (§8).
 *
 * **والضبابيةُ فوق الخريطة**: `backdrop-blur` يجعل الشريطَ طبقةً يمرّ اللونُ من
 * تحتها لا حاجزاً — والخلفيةُ سطحٌ معتمٌ فيبقى النصُّ مقروءاً في الوضعين.
 */

import { motion } from "framer-motion";
import { NavLink } from "react-router-dom";

import { DURATION, EASE } from "@/lib/motion";
import { TABS } from "@/lib/tabs";
import { cn } from "@/lib/utils";

export function BottomNav() {
  return (
    // **الحاويةُ لا تلتقط اللمس** كي تمرّ إيماءاتُ الخريطة من حولها، والحبّةُ
    // وحدَها تُعيد تمكينَه — نفسُ قاعدةِ أزرار الخريطة في `Home`
    <nav className="pointer-events-none absolute inset-x-0 bottom-0 z-30 px-16 pb-float">
      <div className="pointer-events-auto mx-auto flex h-62 max-w-lg items-center gap-4 rounded-full border border-line bg-surface px-6 shadow-sheet backdrop-blur">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === "/"}
            className="pressable relative flex h-48 flex-1 items-center justify-center rounded-full"
          >
            {({ isActive }) => (
              <>
                {isActive ? (
                  <motion.span
                    layoutId="taxo-tab"
                    aria-hidden
                    className="absolute inset-0 rounded-full bg-brand"
                    transition={{ duration: DURATION.med, ease: EASE.standard }}
                  />
                ) : null}
                {/* النصُّ فوق الحبّة: بلا `relative` يرسمها Framer فوقه */}
                <span className="relative block text-center">
                  <tab.icon
                    className={cn(
                      "mx-auto mb-2 size-19",
                      isActive ? "text-brand-ink" : "text-muted",
                    )}
                  />
                  <span
                    className={cn(
                      "block text-9.5",
                      isActive
                        ? "font-bold text-brand-ink"
                        : "font-medium text-muted",
                    )}
                  >
                    {tab.label}
                  </span>
                </span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
