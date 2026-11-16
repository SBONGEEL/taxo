/** **«حول التطبيق والتراخيص»** (SPEC §١٠٥/٤) — نسبةُ بيانات الخرائط كاملةً، **ونسبةُ الخريطة نفسِها زرُّ ⓘ مطويّ**.
 *  بلغة صفوف «حسابي» (`t2-arow`)، وكلُّ صفٍّ يفتح صفحةَ رخصته خارج التطبيق. منسوخةٌ في التطبيقين.
 */

import { useNavigate } from "react-router-dom";

import { openLegal } from "@/lib/legal";
import { MAP_CREDITS } from "@/lib/map-credits";

import "@/taxo2";
import "./t2.css";
import { tr } from "@/lib/i18n";

export function LicensesT2Screen() {
  const navigate = useNavigate();
  const version = import.meta.env.VITE_APP_VERSION as string | undefined;
  return (
    <div className="t2 t2-page t2-account pb-nav">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => navigate(-1)}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">{tr("حول التطبيق والتراخيص")}</h1>
      </div>
      {version ? (
        <p className="t2-legal-note" dir="ltr">
          TAXO {version}
        </p>
      ) : null}
      <h2 className="t2-legal-note">{tr("بياناتُ الخرائط والبحث")}</h2>
      <div className="t2-list t2-arows">
        {MAP_CREDITS.map((credit) => (
          <button key={credit.key} type="button" className="t2-arow" onClick={() => openLegal(credit.url)}>
            <span className="t2-icon" aria-hidden="true">map</span>
            <span className="t2-arow-label">
              <span dir="ltr">{credit.name}</span>
              <span className="t2-arow-sub">{tr(credit.what)}</span>
            </span>
            <span className="t2-icon t2-chev" aria-hidden="true">chevron_left</span>
          </button>
        ))}
      </div>
      <p className="t2-legal-note">
        {tr("تظهر هذه النسبةُ مختصرةً على الخريطة نفسِها — المس ⓘ في زاويتها لتراها.")}
      </p>
    </div>
  );
}
