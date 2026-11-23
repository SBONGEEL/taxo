/** **«أضف عنوان كليك»** (أمرُ المالك ٢٠٢٦-١١-٢٣، البند ٢) — بطاقةٌ هادئةٌ في الرئيسيّة لمن لا عنوانَ كليك له، **حيث كليك مشتعلٌ لدولته**.
 *
 * **لماذا**: كليك يعمل في الأردن واستُعمل صفراً — والراكبُ لا يرى «ادفع بكليك» إلا لكبتنٍ له عنوان (`accepts_cliq`). فالبطاقةُ تشرح
 * السببَ بسطرٍ وتفتح الإعدادات حيث يُكتب العنوان. **ولا نافذةَ تحجب**، و«ليس الآن» يُخفيها أسبوعاً. **ولا مالَ يتحرّك من هنا**.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { tr } from "@/lib/i18n";
import { Icon } from "@/taxo2";

import "./add-widget.css";

const KEY = "taxo.cliq_card_snooze_until";
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function snoozed(): boolean {
  try {
    return Number(localStorage.getItem(KEY) ?? 0) > Date.now();
  } catch {
    return false;
  }
}

export function CliqAliasCard({ show }: { /** مشتعلٌ لدولته، والملفُّ مقروءٌ وبلا عنوان */ show: boolean }) {
  const navigate = useNavigate();
  const [hidden, setHidden] = useState(snoozed);
  if (!show || hidden) return null;

  function later() {
    try {
      localStorage.setItem(KEY, String(Date.now() + WEEK_MS));
    } catch {
      /* التخزينُ محجوبٌ: تُخفى في هذه الجلسة وحدَها */
    }
    setHidden(true);
  }

  return (
    <section className="aw-card" aria-label={tr("أضف عنوان كليك")}>
      <span className="aw-icon" aria-hidden="true">
        <Icon name="smartphone" fill />
      </span>
      <span className="aw-text">
        <span className="aw-title">{tr("أضف عنوان كليك")}</span>
        <span className="aw-body">
          {tr("ليدفع لك الركّابُ بكليك مباشرةً إلى حسابك البنكيّ — يظهر لهم «ادفع بكليك» حين يكون لك عنوان.")}
        </span>
      </span>
      <button type="button" className="aw-add" onClick={() => navigate("/account/settings")}>
        {tr("أضف")}
      </button>
      <button type="button" className="aw-close" onClick={later} aria-label={tr("ليس الآن")}>
        <Icon name="close" />
      </button>
    </section>
  );
}
