/** الشريط السفلي — `DESIGN.md` §1.4/§5.3: ارتفاع 66، حشوة `8px 6px 12px`.
 *
 * أربعةُ تبويبات: مربّعٌ 19×19 نصف قطر 6 بلون `--tx` للنشط و`--brd` لغيره،
 * وتسميةٌ 9.5px بوزن 700 للنشط و500 لغيره، وشفافيةٌ 0.65 لغير النشط.
 *
 * **الأيقونات مربّعاتٌ صمّاء كما في التصميم** لا أيقونات lucide: النموذج
 * يرسمها كذلك عمداً — رموزُه اليونيكودية استُبدلت بـlucide حيث كانت رموزاً
 * (قرار 19)، وهذه ليست رموزاً بل عناصرُ شكلٍ لم يُرسم لها بديل.
 */

import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { to: "/", label: "الرئيسية" },
  { to: "/rides", label: "الرحلات" },
  { to: "/wallet", label: "المحفظة" },
  { to: "/account", label: "حسابي" },
];

export function BottomNav() {
  return (
    <nav className="absolute inset-x-0 bottom-0 z-30 flex h-nav border-t border-line bg-surface px-6 pb-12 pt-8">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === "/"}
          className="flex-1"
        >
          {({ isActive }) => (
            <span
              className={cn(
                "block text-center",
                isActive ? "opacity-100" : "opacity-65",
              )}
            >
              <span
                className={cn(
                  "mx-auto mb-4 block size-19 rounded-6",
                  isActive ? "bg-ink" : "bg-line",
                )}
              />
              <span
                className={cn(
                  "block text-9.5 text-ink",
                  isActive ? "font-bold" : "font-medium",
                )}
              >
                {tab.label}
              </span>
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
