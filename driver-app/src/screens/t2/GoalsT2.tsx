/** **«أهدافي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٦) — تحت «أرباحي»، وإليها يفتح «اقتربت من هدفك» و«وصلت مكافأتُك».
 *
 * **الأرقامُ كما تصل** من `GET /drivers/me/goals`، والمكافأةُ بعملة الدولة. **ولا تُرسم حيث المفتاحُ مطفأ أو لا هدف.**
 */

import { useEffect, useState } from "react";

import { getMyGoals, type MyGoals } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { digits, formatAmount } from "@/lib/utils";

export function GoalsT2() {
  const [data, setData] = useState<MyGoals | null>(null);

  useEffect(() => {
    getMyGoals()
      .then(setData)
      .catch(() => undefined);
  }, []);

  if (data === null || !data.enabled || data.goals.length === 0) return null;

  return (
    <section className="t2-wal-break" id="my-goals" aria-labelledby="my-goals-title">
      <h2 id="my-goals-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
        <span>{tr("أهدافي")}</span>
      </h2>
      {data.goals.map((goal) => {
        const share = Math.min(1, goal.done / goal.target);
        return (
          <div key={goal.id} style={{ marginBottom: 10 }}>
            <div className="t2-wal-line">
              <span>{goal.title}</span>
              <span dir="ltr">{digits(`${Math.min(goal.done, goal.target)} / ${goal.target}`)}</span>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={goal.target}
              aria-valuenow={Math.min(goal.done, goal.target)}
              style={{ height: 6, borderRadius: 3, background: "var(--t2-line, rgba(0,0,0,0.1))", overflow: "hidden" }}
            >
              <div style={{ width: `${share * 100}%`, height: "100%", background: "var(--t2-accent, #ff6a00)" }} />
            </div>
            <p className="t2-wal-hint">
              {goal.rewarded
                ? tr("وصلت المكافأة {0} إلى محفظتك", { 0: formatAmount(goal.reward_amount, data.currency) })
                : tr("المكافأة {0} — تُضاف إلى محفظتك حين تبلغ الهدف", { 0: formatAmount(goal.reward_amount, data.currency) })}
            </p>
          </div>
        );
      })}
    </section>
  );
}
