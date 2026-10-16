/** **شريطُ «وضع تجريبي» في كلِّ شاشة** (أمرُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-ن/٢).
 *
 * فوق كلِّ شيء ولا يُغلق — **من في العرض يعرف أنه في العرض أينما كان**، ومنه يخرج: الخروجُ يمحو العرضَ كلَّه ويعيد الترحيب، والتسجيلُ
 * بعده هو التسجيلُ المعتاد بالتحقّق من الرقم.
 */

import { tokens } from "@/api/client";
import { demoReset } from "@/demo/engine";
import { demoActive, leaveDemo } from "@/demo/mode";
import { tr } from "@/lib/i18n";

import "./demo-banner.css";

export function DemoBanner() {
  if (!demoActive()) return null;
  return (
    <div className="demo-banner" role="status" data-demo-banner>
      <span className="demo-banner-dot" aria-hidden="true" />
      <span className="demo-banner-text">{tr("وضع تجريبي")}</span>
      <button
        type="button"
        className="demo-banner-exit"
        onClick={() => {
          leaveDemo();
          demoReset();
          tokens.clear();
          window.location.replace("/");
        }}
      >
        {tr("خروج")}
      </button>
    </div>
  );
}
