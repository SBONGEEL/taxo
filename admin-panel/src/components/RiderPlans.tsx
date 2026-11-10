/** **خططُ اشتراك الركّاب** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٣، SPEC §٩٧/١٣).
 *
 * **المبالغُ يضعها المالك** بعملة الدولة، **ومن يتحمّل الخصم** إعدادٌ لكلِّ خطّة. **وبعد الإنشاء الإيقافُ والتشغيلُ وحدَهما** — من اشترى
 * اشترى شروطاً مجمَّدة. والمشتركون والإيرادُ والخصمُ من الخلفية؛ لا حسابَ هنا.
 */

import { useCallback, useEffect, useState } from "react";

import { createRiderPlan, listRiderPlans, setRiderPlanActive } from "@/api/endpoints";
import type { RiderPlan } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { currencyOf, money } from "@/lib/format";
import { digits } from "@/lib/utils";

export function RiderPlans({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const currency = currencyOf(country);
  const [rows, setRows] = useState<RiderPlan[] | null>(null);
  const [name, setName] = useState("");
  const [days, setDays] = useState("30");
  const [price, setPrice] = useState("");
  const [percent, setPercent] = useState("");
  const [rideCap, setRideCap] = useState("");
  const [monthCap, setMonthCap] = useState("");
  const [terms, setTerms] = useState("");
  const [bearer, setBearer] = useState<"taxo" | "captain">("taxo");
  const [busy, setBusy] = useState(false);
  const numeric = (value: string) => value.replace(/[^0-9.]/g, "");

  const load = useCallback(() => {
    listRiderPlans(country)
      .then(setRows)
      .catch((caught: Error) => onError(caught.message));
  }, [country, onError]);

  useEffect(load, [load]);

  const create = () => {
    setBusy(true);
    createRiderPlan(country, {
      name: name.trim(),
      days: Number(days),
      price,
      discount_percent: percent,
      per_ride_cap: rideCap,
      monthly_cap: monthCap,
      terms: terms.trim() || null,
      bearer,
    })
      .then(() => {
        setName("");
        setPrice("");
        setPercent("");
        setRideCap("");
        setMonthCap("");
        setTerms("");
        load();
      })
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="rider-plans-title">
      <h2 id="rider-plans-title" className="text-15 font-bold text-ink">
        اشتراكات الركّاب
      </h2>
      <p className="mt-4 max-w-prose text-11 leading-snug text-muted">
        يشتري الراكبُ الخطّةَ من محفظته، فيُخصم من كلِّ رحلةٍ يُنهيها نسبتُها بحدٍّ للرحلة وحدٍّ لكلِّ ثلاثين يوماً، ويرى ما وفّره وتاريخَ
        انتهائه ويجدّد في أيّامه الثلاثة الأخيرة. ولا يجتمع خصمُ الاشتراك مع كوبون. «TAXO تتحمّله»: يقبض الكبتنُ أجرتَه كاملة.
        «الكبتن يتحمّله»: تنقص الأجرةُ بالخصم فيقبض أقلّ. وتعمل حين يشتعل مفتاحُ «اشتراكات الركّاب» في الإعدادات.
      </p>
      {isAdmin ? (
        <div className="mt-12 grid grid-cols-2 gap-10 lg:grid-cols-4">
          <Field name="plan_name" label="اسم الخطّة" value={name} onChange={(e) => setName(e.target.value)} />
          <Field name="plan_days" label="المدّة (أيام)" dir="ltr" inputMode="numeric" value={days} onChange={(e) => setDays(numeric(e.target.value))} />
          <Field name="plan_price" label="الثمن" dir="ltr" inputMode="decimal" value={price} onChange={(e) => setPrice(numeric(e.target.value))} />
          <Field name="plan_percent" label="نسبة الخصم على الرحلة" dir="ltr" inputMode="decimal" value={percent} onChange={(e) => setPercent(numeric(e.target.value))} />
          <Field name="plan_ride_cap" label="حدّ الخصم للرحلة" dir="ltr" inputMode="decimal" value={rideCap} onChange={(e) => setRideCap(numeric(e.target.value))} />
          <Field name="plan_month_cap" label="حدّ الخصم لكلِّ 30 يوماً" dir="ltr" inputMode="decimal" value={monthCap} onChange={(e) => setMonthCap(numeric(e.target.value))} />
          <label className="flex flex-col gap-4 text-12 text-ink">
            من يتحمّل الخصم
            <select
              name="plan_bearer"
              className="rounded-field border border-line bg-surface px-10 py-8 text-13"
              value={bearer}
              onChange={(e) => setBearer(e.target.value === "captain" ? "captain" : "taxo")}
            >
              <option value="taxo">TAXO</option>
              <option value="captain">الكبتن</option>
            </select>
          </label>
          <Field name="plan_terms" label="الشروط (اختياري)" value={terms} onChange={(e) => setTerms(e.target.value)} />
          <div className="flex items-end">
            <Button size="sm" loading={busy} disabled={!name.trim() || !days || !price || !percent || !rideCap || !monthCap} onClick={create}>
              إنشاء الخطّة
            </Button>
          </div>
        </div>
      ) : null}
      <ul className="mt-14 space-y-8">
        {(rows ?? []).map((plan) => (
          <li key={plan.id} className="flex flex-wrap items-center justify-between gap-8 border-t border-line pt-8 text-13">
            <span className="min-w-0">
              <span className="font-semibold text-ink">{plan.name}</span>{" "}
              <Badge tone={plan.is_active ? "ok" : "muted"}>{plan.is_active ? "تُباع" : "موقوفة"}</Badge>
              <span className="block text-11 text-muted">
                {money(plan.price, currency)} لـ{digits(String(plan.days))} يوماً · خصم <span dir="ltr">{digits(plan.discount_percent)}</span>
                ٪ حتى {money(plan.per_ride_cap, currency)} للرحلة و{money(plan.monthly_cap, currency)} لكلِّ 30 يوماً ·{" "}
                {plan.bearer === "taxo" ? "TAXO تتحمّله" : "الكبتن يتحمّله"}
              </span>
              <span className="block text-11 text-muted">
                مشتركون الآن {digits(String(plan.active_subscribers))} · الإيراد {money(plan.revenue, currency)} · الخصم المصروف{" "}
                {money(plan.discounts, currency)}
              </span>
            </span>
            {isAdmin ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  setRiderPlanActive(plan.id, !plan.is_active)
                    .then(load)
                    .catch((caught: Error) => onError(caught.message))
                }
              >
                {plan.is_active ? "أوقف البيع" : "أعِد البيع"}
              </Button>
            ) : null}
          </li>
        ))}
        {rows !== null && rows.length === 0 ? <li className="text-12 text-muted">لا خططَ بعد.</li> : null}
      </ul>
    </section>
  );
}
