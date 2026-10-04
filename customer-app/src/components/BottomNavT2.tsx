/** شريطُ التبويب — TAXO 2.0 «TaxoTabs» للراكب (Claude Design)، **في النهاريّ المرسوم وحدَه**.
 *
 * **الوجهاتُ هي هي** (`lib/tabs.ts` — بيتٌ واحدٌ للتبويبات وترتيبها): الرئيسية · رحلاتي · المحفظة ·
 * حسابي، **ومطابقةٌ لتبويبات اللوحة حرفاً** — فالتغييرُ طبقةُ عرضٍ وحدَها: النشطُ حبّةٌ أعرضُ
 * بالحبر فيها الأيقونةُ ممتلئةً واسمُها جنباً إلى جنب، والخاملُ أيقونةٌ فوق اسمٍ صغير.
 * **والموضعُ موضعُ الشريط القائم** (`pb-float`) — فالمساحةُ التي تحجزها الشاشاتُ له لم تتغيّر.
 * **والليليُّ لم يُرسم بعد** (§61-ب): الشريطُ القائمُ فيه كما هو (`App.tsx::NavBar`).
 */

import { NavLink } from "react-router-dom";

import { TABS } from "@/lib/tabs";

import "@/screens/t2/t2.css";

/** أيقونةُ كلِّ وجهةٍ في اللوحة (Material Symbols) — بالمسار لا بالترتيب. */
const TAB_ICON: Record<string, string> = {
  "/": "home",
  "/rides": "receipt_long",
  "/wallet": "account_balance_wallet",
  "/account": "person",
};

export function BottomNavT2() {
  return (
    // **الحاويةُ لا تلتقط اللمس** كي تمرّ إيماءاتُ الخريطة من حولها — كالشريط القائم
    <nav className="t2 t2-tabs pointer-events-none absolute inset-x-0 bottom-0 z-30 px-16 pb-float">
      <div className="t2-tabs-bar pointer-events-auto mx-auto max-w-lg">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === "/"}
            className={({ isActive }) => (isActive ? "t2-tab on" : "t2-tab")}
          >
            <span className="t2-icon" aria-hidden="true">{TAB_ICON[tab.to] ?? "circle"}</span>
            <span className="t2-tab-label">{tab.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
