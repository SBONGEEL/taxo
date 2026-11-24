/** **«خصومُ عروض الركّاب هذا الشهر»** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-د) — ما تحمّله الكبتنُ رحلةً رحلة، وجملتُه.
 *
 * **الأرقامُ كما تصل** من `GET /drivers/me/offer-discounts` — والجملةُ تحسبها الخلفيّة. ولا يُرسم شيءٌ حيث لا رحلةَ بخصمٍ تحمّله.
 */

import { useEffect, useState } from "react";

import { getMyOfferDiscounts, type MyOfferDiscounts } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, digits, formatAmount } from "@/lib/utils";

export function OfferDiscountsT2() {
  const [data, setData] = useState<MyOfferDiscounts | null>(null);

  useEffect(() => {
    getMyOfferDiscounts()
      .then(setData)
      .catch(() => undefined);
  }, []);

  if (data === null || data.count === 0) return null;
  const currency = data.rides[0]?.currency ?? null;

  return (
    <section className="t2-wal-break" id="offer-discounts" aria-labelledby="offer-discounts-title">
      <h2 id="offer-discounts-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
        <span>{tr("خصوم عروض الركّاب هذا الشهر")}</span>
        <span>{formatAmount(data.total, currency)}</span>
      </h2>
      {data.rides.map((row) => (
        <div key={row.ride_id} className="t2-wal-line">
          <span>
            {row.label}
            {row.completed_at ? ` · ${digits(new Date(row.completed_at).toLocaleDateString(DISPLAY_LOCALE))}` : ""}
          </span>
          <span>{formatAmount(row.discount, row.currency)}</span>
        </div>
      ))}
      <p className="t2-wal-hint">{tr("خلال فترة الخدمة المجانية تتحمّل خصومات عروض الركاب كشريك TAXO للإطلاق.")}</p>
    </section>
  );
}
