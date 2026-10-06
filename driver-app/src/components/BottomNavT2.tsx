/** شريطُ التبويب — TAXO 2.0 «TaxoTabs» للكبتن (Claude Design، C04)، **في المظهرين** (§٦٢/٣ و/٨).
 *
 * **الوجهاتُ من `lib/tabs.ts`**: الرئيسية · الأرباح · المستوى · حسابي (C04 كما رُسمت، §٦٢-ب/٢٦) — حبّةُ الجمر للنشط
 * (C04: ١١١×٤٨، اسمُها ١٣/٧٠٠ بنصِّ الإسفلت) والخاملُ أيقونةٌ فوق اسمٍ صغير، والشريطُ عائمٌ بحافّةٍ في الداكن (`primitives.css`).
 * **وكان الشريطُ القديمُ يُرسم في المظهرين** — حبّةٌ بيضاءُ بلغةٍ سابقة — فرأى المالكُ القديمَ حتى في الداكن.
 *
 * **وتبويباتُ C04 الجديدة انتظرت سجلَّ الرحلات** — بابُ الاعتراض على الدفعة فيه (§٦١-ب/٣) — **فلمّا بُني (C16) بُدّلت**، وصار
 * السجلُّ باباً في «الأرباح».
 */

import { NavLink } from "react-router-dom";

import { TABS } from "@/lib/tabs";

import "@/taxo2";

/** أيقونةُ كلِّ وجهةٍ (Material Symbols) — بالمسار لا بالترتيب، **ومن C04 حيث رُسمت**. */
const TAB_ICON: Record<string, string> = {
  "/": "home",
  "/wallet": "payments",
  "/account/missions": "workspace_premium",
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
            // **و«حسابي» لا يُضاء على «المستوى»** — مسارُه يبدأ به
            end={tab.to === "/" || tab.to === "/account"}
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
