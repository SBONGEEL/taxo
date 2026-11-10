/** **«اشتراكي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣) — الخططُ بثمنها وخصمها وحدودها وشروطها، والشراءُ من المحفظة،
 * **وما وفّرته وتاريخُ الانتهاء** حين يكون الاشتراكُ سارياً. **لا حسابَ مالٍ هنا** — كلُّ رقمٍ كما وصل.
 */

import { useEffect, useState } from "react";

import { getMyPlans, subscribePlan, type MyPlans } from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, currencyLabel, digits, formatAmount } from "@/lib/utils";
import "./support.css";

function Money({ value, currency }: { value: string; currency: string }) {
  return (
    <>
      <span dir="ltr">{formatAmount(value, currency)}</span> {currencyLabel(currency)}
    </>
  );
}

export function PlansT2() {
  const goBack = useGoBack("/wallet");
  const [data, setData] = useState<MyPlans | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyPlans()
      .then(setData)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const buy = async (planId: string) => {
    setBusy(planId);
    setError(null);
    try {
      setData(await subscribePlan(planId));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const until = (iso: string) => new Date(iso).toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="sp-page">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={goBack}>
          <span className="t2-icon" aria-hidden="true">
            arrow_forward
          </span>
        </button>
        <h1 className="t2-title">{tr("اشتراكي")}</h1>
      </div>
      <div className="sp-body">
        {error ? <p className="sp-hint" role="alert">{error}</p> : null}
        {data?.current ? (
          <div className="sp-card">
            <span className="sp-label">{data.current.plan_name}</span>
            <span className="sp-said">
              {tr("وفّرت حتى الآن")} <Money value={data.current.saved} currency={data.currency} />
            </span>
            <span className="sp-hint">
              {tr("ينتهي في {0}", { 0: until(data.current.ends_at) })} ·{" "}
              {tr("بقي من خصم هذا الشهر")} <Money value={data.current.month_left} currency={data.currency} />
            </span>
          </div>
        ) : null}
        {data && data.enabled && (data.current === null || data.current.can_renew)
          ? data.plans.map((plan) => (
              <div key={plan.id} className="sp-card">
                <span className="sp-label">{plan.name}</span>
                <span className="sp-said">
                  <Money value={plan.price} currency={data.currency} /> · {tr("{0} يوماً", { 0: digits(String(plan.days)) })}
                </span>
                <span className="sp-hint">
                  {tr("خصم {0}٪ على كلِّ رحلة", { 0: digits(plan.discount_percent) })} · {tr("حتى")}{" "}
                  <Money value={plan.per_ride_cap} currency={data.currency} /> {tr("للرحلة")} · {tr("و")}
                  <Money value={plan.monthly_cap} currency={data.currency} /> {tr("لكلِّ 30 يوماً")}
                </span>
                {plan.terms ? <span className="sp-hint">{plan.terms}</span> : null}
                <span className="sp-hint">{tr("يُدفع من محفظتك، والخصمُ آليٌّ عند نهاية كلِّ رحلة، ولا يجتمع مع كوبون.")}</span>
                <button type="button" className="t2-cta sp-cta" disabled={busy !== null} onClick={() => void buy(plan.id)}>
                  {busy === plan.id ? "…" : data.current ? tr("جدّد من محفظتي") : tr("اشترك من محفظتي")}
                </button>
              </div>
            ))
          : null}
        {data && !data.enabled && !data.current ? <p className="sp-hint">{tr("الاشتراكات غير متاحة في بلدك حالياً.")}</p> : null}
      </div>
    </div>
  );
}
