/** «الشروط والخصوصية» (R15، §٦١-ط/٣) — صفحةٌ بصفّين يفتحان صفحتي الموقع، **بلغة صفوف «حسابي»**.
 *
 * **لم تُرسم بعد** (`TAXO2-DESIGN-REQUESTS.md` §٤/٤) — فبُنيت من مفردات R15 نفسِها: الرأسُ بسهمه، وصفوفُ «حسابي». **ولا
 * `t2-day`**: تتبع المظهرَ القائم، فتُفتح من «حسابي» الليليّ بإسفلت العائلة نفسِها.
 */

import { useNavigate } from "react-router-dom";

import { LEGAL_PAGES, openLegal } from "@/lib/legal";

import "@/taxo2";
import "./t2.css";

export function LegalT2Screen() {
  const navigate = useNavigate();
  return (
    <div className="t2 t2-page t2-account pb-nav">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={() => navigate(-1)}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">الشروط والخصوصية</h1>
      </div>
      <div className="t2-list t2-arows">
        {LEGAL_PAGES.map((page) => (
          <button key={page.key} type="button" className="t2-arow" onClick={() => openLegal(page.url)}>
            <span className="t2-icon" aria-hidden="true">{page.key === "privacy" ? "shield" : "gavel"}</span>
            <span className="t2-arow-label">{page.label}</span>
            <span className="t2-icon t2-chev" aria-hidden="true">open_in_new</span>
          </button>
        ))}
      </div>
      <p className="t2-legal-note">تُفتحان على موقع TAXO — النصُّ المنشورُ نفسُه الذي وافقتَ عليه عند التسجيل.</p>
    </div>
  );
}
