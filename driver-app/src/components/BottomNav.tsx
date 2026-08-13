/** الشريط السفلي — `DESIGN.md` §1.4/§5.3 والقرار 22.
 *
 * **نسخةٌ من `customer-app/src/components/BottomNav.tsx` بتسميةٍ واحدة مختلفة**،
 * لا اشتقاقٌ جديد: التطبيقان يتقاسمان نظامَ التصميم نفسَه، وشريطان مبنيّان
 * مرتين يفترقان في أوّل قيمةٍ تُعدَّل في أحدهما. الارتفاع 66 والحشوة
 * `8px 6px 12px`، وتسميةٌ 9.5px بوزن 700 للنشط و500 لغيره.
 *
 * **وأيقوناتُ lucide لا مربّعاتٌ صمّاء** (2026-08-13): كان المربّعُ نقلاً حرفياً
 * عن النموذج الذي رسمه شكلاً لا رمزاً، والقرارُ 19 يستبدل محارفَ النموذج
 * بـlucide **حيث كانت رموزاً** — والتبويبُ رمزٌ يُقرأ قبل نصِّه.
 *
 * **والنشطُ بـ`--brand` والخاملُ بـ`--mut`**، فيتبعان الوضعَ والسِمة بلا شرطٍ في
 * المكوّن: `--brand` قيمتُها `--tx` والسِمةُ مطفأة، فلا يتغيّر شيءٌ اليوم
 * ويتلوّن الشريطُ وحدَه حين تُشعَل (§1.1-ب).
 *
 * **والمؤشِّرُ ينزلق ولا يقفز**: عنصرٌ **واحد** يُنقل بـ`translate` بين المواضع
 * لا أربعةٌ يظهر أحدُها ويختفي الآخر — وأربعةٌ تعني وميضاً في مكانين، لا انتقالاً
 * بينهما. وموضعُه محسوبٌ من ترتيب التبويب لا من قياسٍ في المتصفح: أربعةٌ
 * متساويةٌ بعرض `100% / 4`.
 *
 * **والحركةُ المخفَّضة توقفه**: `transition` وحدها هي ما يُلغى، فيبقى المؤشِّرُ
 * في موضعه الصحيح فوراً (`DESIGN.md` §8).
 */

import { Home, Clock, Wallet, User } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { to: "/", label: "الرئيسية", icon: Home },
  { to: "/rides", label: "الرحلات", icon: Clock },
  { to: "/wallet", label: "المحفظة", icon: Wallet },
  { to: "/account", label: "حسابي", icon: User },
];

/** أيُّ تبويبٍ يملك هذا المسار — و«حسابي» يملك كلَّ ما تحته (`/account/*`). */
function activeIndex(pathname: string): number {
  const found = TABS.findIndex(
    (tab) => tab.to !== "/" && pathname.startsWith(tab.to),
  );
  return found === -1 ? 0 : found;
}

export function BottomNav() {
  const { pathname } = useLocation();
  const index = activeIndex(pathname);

  return (
    <nav className="absolute inset-x-0 bottom-0 z-30 h-nav border-t border-line bg-surface pb-12 pt-8">
      {/* المؤشِّر: عنصرٌ واحد ينزلق. و`start` لا `left` — الشريطُ في RTL */}
      <span
        aria-hidden
        className="absolute top-0 h-2 rounded-full bg-brand transition-[inset-inline-start] duration-med ease-standard motion-reduce:transition-none"
        // العرضُ والموضعُ كلاهما مشتقٌّ من **عدد التبويبات**، فيُكتبان هنا معاً:
        // صنفٌ كسريٌّ ثابت يكذب أوّلَ ما يُضاف تبويبٌ خامس، ويقرؤه `check:scale`
        // مقاساً خارج السلّم (يمسح النصَّ كلَّه لا الأصنافَ وحدها)
        style={{ width: `${100 / TABS.length}%`, insetInlineStart: `${index * (100 / TABS.length)}%` }}
      />
      <div className="flex h-full px-6">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end={tab.to === "/"} className="pressable flex-1">
            {({ isActive }) => (
              <span className="block text-center">
                <tab.icon
                  className={cn(
                    "mx-auto mb-4 size-20 transition-transform duration-med ease-standard motion-reduce:transition-none",
                    isActive ? "scale-110 text-brand" : "text-muted",
                  )}
                />
                <span
                  className={cn(
                    "block text-9.5",
                    isActive ? "font-bold text-brand" : "font-medium text-muted",
                  )}
                >
                  {tab.label}
                </span>
              </span>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
