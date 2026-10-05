/** شريطُ التبويب — TAXO 2.0 «TaxoTabs» للكبتن (Claude Design، C04)، **في المظهرين** (§٦٢/٣ و/٨).
 *
 * **الوجهاتُ هي هي** (`lib/tabs.ts`): الرئيسية · الرحلات · المحفظة · حسابي — **والتغييرُ طبقةُ عرضٍ وحدَها**: حبّةُ الجمر للنشط
 * (C04: ١١١×٤٨، اسمُها ١٣/٧٠٠ بنصِّ الإسفلت) والخاملُ أيقونةٌ فوق اسمٍ صغير، والشريطُ عائمٌ بحافّةٍ في الداكن (`primitives.css`).
 * **وكان الشريطُ القديمُ يُرسم في المظهرين** — حبّةٌ بيضاءُ بلغةٍ سابقة — فرأى المالكُ القديمَ حتى في الداكن.
 *
 * **وتبويباتُ C04 الجديدة** (الأرباح · المستوى) **لا تُبنى قبل سجلّ الرحلات** — بابُ الاعتراض على الدفعة فيه (§٦١-ب/٣) — فتبقى
 * الوجهاتُ كما هي حتى يُرسم السجلّ (§٦٢/٦).
 */

import { NavLink } from "react-router-dom";

import { TABS } from "@/lib/tabs";

import "@/taxo2";

/** أيقونةُ كلِّ وجهةٍ (Material Symbols) — بالمسار لا بالترتيب، **ومن C04 حيث رُسمت**. */
const TAB_ICON: Record<string, string> = {
  "/": "home",
  "/rides": "receipt_long",
  "/wallet": "payments",
  "/account": "person",
};

export function BottomNavT2() {
  return (
    // **الحاويةُ لا تلتقط اللمس** كي تمرّ إيماءاتُ الخريطة من حولها — كالشريط السابق
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
