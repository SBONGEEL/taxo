/** **قاعدةُ نقاط الولاء** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٤، SPEC §٩٧/١٤) — يضعها المالكُ لكلِّ دولة.
 *
 * **والأرقامُ الثلاثةُ تحتها من الخلفية** (من لهم نقاط، وما بقي، وما استُبدل رصيداً) — لا حسابَ هنا.
 */

import { useCallback, useEffect, useState } from "react";

import { getLoyaltyRule, saveLoyaltyRule } from "@/api/endpoints";
import type { LoyaltyRule } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { currencyOf, money } from "@/lib/format";
import { digits } from "@/lib/utils";

const FIELDS: { key: keyof Omit<LoyaltyRule, "country_code" | "holders" | "open_points" | "redeemed_value">; label: string }[] = [
  { key: "points_per_ride", label: "نقاط لكلِّ رحلة مكتملة" },
  { key: "expiry_days", label: "تنتهي النقاط بعد (أيام)" },
  { key: "silver_threshold", label: "الفضّيّ من (نقاط آخر سنة)" },
  { key: "gold_threshold", label: "الذهبيّ من (نقاط آخر سنة)" },
  { key: "silver_bonus_percent", label: "زيادة الفضّيّ على ما يُكسب (بالمئة)" },
  { key: "gold_bonus_percent", label: "زيادة الذهبيّ على ما يُكسب (بالمئة)" },
  { key: "redeem_points", label: "الاستبدال: كلُّ كم نقطة" },
  { key: "redeem_value", label: "الاستبدال: بكم من الرصيد" },
];

export function LoyaltyRules({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const currency = currencyOf(country);
  const [rule, setRule] = useState<LoyaltyRule | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getLoyaltyRule(country)
      .then((found) => {
        setRule(found);
        setForm(found ? Object.fromEntries(FIELDS.map(({ key }) => [key, String(found[key])])) : {});
      })
      .catch((caught: Error) => onError(caught.message));
  }, [country, onError]);

  useEffect(load, [load]);

  const complete = FIELDS.every(({ key }) => (form[key] ?? "").trim() !== "");
  const save = () => {
    setBusy(true);
    saveLoyaltyRule(country, {
      points_per_ride: Number(form.points_per_ride),
      expiry_days: Number(form.expiry_days),
      silver_threshold: Number(form.silver_threshold),
      gold_threshold: Number(form.gold_threshold),
      silver_bonus_percent: Number(form.silver_bonus_percent),
      gold_bonus_percent: Number(form.gold_bonus_percent),
      redeem_points: Number(form.redeem_points),
      redeem_value: form.redeem_value,
    })
      .then(load)
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="loyalty-title">
      <h2 id="loyalty-title" className="text-15 font-bold text-ink">
        نقاط الولاء
      </h2>
      <p className="mt-4 max-w-prose text-11 leading-snug text-muted">
        يكسب الراكبُ نقاطاً عن كلِّ رحلةٍ مكتملة (خلال دقائق من نهايتها) — لا ملغاة، ولا حساب تجربة، ولا كبتن ركب رحلتَه. والمستوى
        بنقاط آخر سنة: برونزيّ ثمّ فضّيّ ثمّ ذهبيّ، وكلٌّ يزيد ما يُكسب بنسبته. والنقاطُ تنتهي بعد مدّتها، والأقدمُ يُستبدل أوّلاً رصيداً
        في المحفظة يدفع به الراكبُ رحلاته. وتعمل حين يشتعل مفتاحُ «نقاط الولاء» في الإعدادات.
      </p>
      <div className="mt-12 grid grid-cols-2 gap-10 lg:grid-cols-4">
        {FIELDS.map(({ key, label }) => (
          <Field
            key={key}
            name={`loyalty_${key}`}
            label={label}
            dir="ltr"
            inputMode={key === "redeem_value" ? "decimal" : "numeric"}
            disabled={!isAdmin}
            value={form[key] ?? ""}
            onChange={(e) => setForm({ ...form, [key]: e.target.value.replace(/[^0-9.]/g, "") })}
          />
        ))}
      </div>
      {isAdmin ? (
        <div className="mt-12">
          <Button size="sm" loading={busy} disabled={!complete} onClick={save}>
            {rule ? "حفظ القاعدة" : "وضع القاعدة"}
          </Button>
        </div>
      ) : null}
      {rule ? (
        <p className="mt-10 text-11 text-muted">
          ركّابٌ لهم نقاطٌ سارية {digits(String(rule.holders))} · نقاطٌ لم تُستبدل {digits(String(rule.open_points))} · استُبدل رصيداً{" "}
          {money(rule.redeemed_value, currency)}
        </p>
      ) : null}
    </section>
  );
}
