/** **أهدافُ الكبتن بمكافأة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٦، SPEC §٩٧/١٦).
 *
 * **المبالغُ يضعها المالك**: المكافأةُ وسقفُ الميزانيّة بعملة الدولة. **والمصروفُ وعددُ المكافآت من الخلفية** — لا طرحَ هنا.
 * **وبعد الإنشاء الإيقافُ وحدَه**: مبلغٌ أو هدفٌ يتغيّر تحت كباتنَ يعملون عليه وعدٌ يُنقض؛ يُوقف ويُنشأ غيرُه.
 * والصرفُ كلَّ عشر دقائق حيث مفتاحُ «أهداف الكبتن بمكافأة» مشتعل.
 */

import { useCallback, useEffect, useState } from "react";

import { createDriverGoal, listDriverGoals, updateDriverGoal } from "@/api/endpoints";
import type { DriverGoal } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { currencyOf, money, moment } from "@/lib/format";
import { digits } from "@/lib/utils";

const DAY_MS = 86_400_000;

export function DriverGoals({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const [rows, setRows] = useState<DriverGoal[] | null>(null);
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [days, setDays] = useState("7");
  const [reward, setReward] = useState("");
  const [cap, setCap] = useState("");
  const [busy, setBusy] = useState(false);
  const currency = currencyOf(country);
  const numeric = (value: string) => value.replace(/[^0-9.]/g, "");

  const load = useCallback(() => {
    listDriverGoals(country)
      .then(setRows)
      .catch((caught: Error) => onError(caught.message));
  }, [country, onError]);

  useEffect(load, [load]);

  const create = () => {
    setBusy(true);
    const now = new Date();
    createDriverGoal(country, {
      title: title.trim(),
      target: Number(target),
      starts_at: now.toISOString(),
      ends_at: new Date(now.getTime() + Number(days) * DAY_MS).toISOString(),
      reward_amount: reward,
      budget_cap: cap,
    })
      .then(() => {
        setTitle("");
        setTarget("");
        setReward("");
        setCap("");
        load();
      })
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="driver-goals-title">
      <h2 id="driver-goals-title" className="text-15 font-bold text-ink">
        أهداف الكبتن بمكافأة
      </h2>
      <p className="mt-4 text-11 leading-snug text-muted">
        عددُ رحلاتٍ مكتملةٍ في مدّة، ومكافأةٌ تُصرف إلى محفظة الكبتن آليّاً حين يبلغه — مرّةً لكلِّ هدف، ولا تتجاوز المكافآتُ مجتمعةً سقفَ
        الميزانيّة. يبدأ الهدفُ لحظةَ إنشائه. ويعمل حين يشتعل مفتاحُ «أهداف الكبتن بمكافأة» في الإعدادات.
      </p>
      {isAdmin ? (
        <div className="mt-12 grid grid-cols-2 gap-10">
          <Field name="goal_title" label="اسم الهدف" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Field name="goal_target" label="رحلات مكتملة" dir="ltr" inputMode="numeric" value={target} onChange={(e) => setTarget(numeric(e.target.value))} />
          <Field name="goal_days" label="المدّة (أيام)" dir="ltr" inputMode="numeric" value={days} onChange={(e) => setDays(numeric(e.target.value))} />
          <Field name="goal_reward" label="المكافأة" dir="ltr" inputMode="decimal" value={reward} onChange={(e) => setReward(numeric(e.target.value))} />
          <Field name="goal_cap" label="سقف الميزانيّة" dir="ltr" inputMode="decimal" value={cap} onChange={(e) => setCap(numeric(e.target.value))} />
          <div className="flex items-end">
            <Button
              size="sm"
              loading={busy}
              disabled={!title.trim() || !target || !days || !reward || !cap}
              onClick={create}
            >
              إنشاء الهدف
            </Button>
          </div>
        </div>
      ) : null}
      <ul className="mt-14 space-y-8">
        {(rows ?? []).map((goal) => (
          <li key={goal.id} className="flex flex-wrap items-center justify-between gap-8 border-t border-line pt-8 text-13">
            <span className="min-w-0">
              <span className="font-semibold text-ink">{goal.title}</span>{" "}
              <Badge tone={goal.is_active ? "ok" : "muted"}>{goal.is_active ? "يعمل" : "موقوف"}</Badge>
              <span className="block text-11 text-muted">
                {digits(String(goal.target))} رحلة · المكافأة {money(goal.reward_amount, currency)} · صُرف{" "}
                {money(goal.spent, currency)} من {money(goal.budget_cap, currency)} لـ{digits(String(goal.awards))} كبتن ·
                حتى {moment(goal.ends_at)}
              </span>
            </span>
            {isAdmin && goal.is_active ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  updateDriverGoal(goal.id, { is_active: false })
                    .then(load)
                    .catch((caught: Error) => onError(caught.message))
                }
              >
                إيقاف
              </Button>
            ) : null}
          </li>
        ))}
        {rows !== null && rows.length === 0 ? <li className="text-12 text-muted">لا أهدافَ بعد.</li> : null}
      </ul>
    </section>
  );
}
