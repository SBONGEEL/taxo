/** **«نقاطي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤) — رصيدُ النقاط ومستواه وما يبلغ به التالي، وأقربُ انتهاء،
 * **واستبدالُها رصيداً في المحفظة**. **لا حسابَ هنا** — قيمةُ الاستبدال والأرقامُ كما وصلت.
 */

import { useEffect, useState } from "react";

import { getMyLoyalty, redeemLoyalty, type MyLoyalty } from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, currencyLabel, digits, formatAmount } from "@/lib/utils";
import "./support.css";

const TIER: Record<MyLoyalty["tier"], string> = { bronze: "برونزيّ", silver: "فضّيّ", gold: "ذهبيّ" };

export function LoyaltyT2() {
  const goBack = useGoBack("/wallet");
  const [data, setData] = useState<MyLoyalty | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyLoyalty()
      .then(setData)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const blocks = data && data.redeem_points ? Math.floor(data.points / data.redeem_points) : 0;
  const redeem = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await redeemLoyalty(blocks));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sp-page">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={goBack}>
          <span className="t2-icon" aria-hidden="true">
            arrow_forward
          </span>
        </button>
        <h1 className="t2-title">{tr("نقاطي")}</h1>
      </div>
      <div className="sp-body">
        {error ? <p className="sp-hint" role="alert">{error}</p> : null}
        {data && data.enabled ? (
          <>
            <div className="sp-card">
              <span className="sp-label">
                {tr("المستوى")}: {tr(TIER[data.tier])}
              </span>
              <span className="sp-said" dir="ltr">
                {digits(String(data.points))}
              </span>
              <span className="sp-hint">
                {data.next_tier && data.to_next !== null
                  ? tr("{0} نقطة أخرى هذه السنة وتصير {1}", { 0: digits(String(data.to_next)), 1: tr(TIER[data.next_tier]) })
                  : tr("أعلى مستوى")}
                {data.bonus_percent ? ` · ${tr("تكسب {0}٪ زيادة", { 0: digits(String(data.bonus_percent)) })}` : ""}
              </span>
              {data.expiring_at && data.expiring_points ? (
                <span className="sp-hint">
                  {tr("{0} نقطة تنتهي في {1}", {
                    0: digits(String(data.expiring_points)),
                    1: new Date(data.expiring_at).toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }),
                  })}
                </span>
              ) : null}
            </div>
            {data.redeem_points && data.redeem_value ? (
              <div className="sp-card">
                <span className="sp-hint">
                  {tr("كلُّ {0} نقطة = ", { 0: digits(String(data.redeem_points)) })}
                  <span dir="ltr">{formatAmount(data.redeem_value, data.currency)}</span> {currencyLabel(data.currency)}{" "}
                  {tr("في محفظتك، تدفع به رحلاتك")}
                </span>
                <button type="button" className="t2-cta sp-cta" disabled={busy || blocks < 1} onClick={() => void redeem()}>
                  {busy ? "…" : tr("استبدل")}{" "}
                  <span dir="ltr">{formatAmount(data.redeemable_value, data.currency)}</span> {currencyLabel(data.currency)}
                </button>
              </div>
            ) : null}
          </>
        ) : data ? (
          <p className="sp-hint">{tr("نقاط الولاء غير متاحة في بلدك حالياً.")}</p>
        ) : null}
      </div>
    </div>
  );
}
