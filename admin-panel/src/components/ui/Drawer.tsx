/** **درجُ الملفّ** (A09 · A05) — من حافّة البداية، بالإسفلت وبطاقاتٍ عليه، **ورأسُه صاحبُ الملفّ**.
 *
 * **بيتٌ واحدٌ لدرجين** (الكباتن والركّاب): كانا يكتبان الغلافَ نفسَه بيدين — ظلٌّ ولوحٌ وعرضٌ ورأسٌ وزرُّ إغلاق — **ونسختان
 * تفترقان أوّلَ تعديل** (الشكلُ الثامن). **والمحتوى للشاشة**: الدرجُ لا يعرف أقسامَه ولا قراراتِه.
 *
 * **والنقرُ على الظلّ يُغلق، والنقرُ في اللوح لا يصعد** (`stopPropagation`) — كما كانا. **وEsc يُغلق** كالحوار.
 */

import { useEffect } from "react";
import type { ReactNode } from "react";

import { Icon } from "@/taxo2";

export function Drawer({
  name,
  phone,
  badges,
  onClose,
  children,
}: {
  /** اسمُ صاحب الملفّ — ومنه الحرفُ الأوّل في الدائرة. */
  name: string;
  phone?: string | null;
  /** حالُه في كلمات (`Badge`) تحت اسمه. */
  badges?: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="ad-drawer" onClick={onClose}>
      <aside
        className="ad-drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-label={name}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ad-drawer-head">
          <span className="ad-drawer-avatar" aria-hidden="true">
            {name.trim().slice(0, 1)}
          </span>
          <div className="ad-drawer-who">
            <p className="ad-drawer-name">{name}</p>
            {phone ? <p className="ad-drawer-sub">{phone}</p> : null}
            {badges ? <div className="ad-drawer-badges">{badges}</div> : null}
          </div>
          <button type="button" onClick={onClose} aria-label="إغلاق" className="ad-round">
            <Icon name="close" />
          </button>
        </div>
        <div className="ad-drawer-body">{children}</div>
      </aside>
    </div>
  );
}
