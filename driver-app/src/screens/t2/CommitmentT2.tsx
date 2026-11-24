/** **«نقاط الالتزام»** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-ب) — بطاقةُ التقدّم في الرئيسيّة، وقواعدُها بالعربيّة تحتها.
 *
 * **الأرقامُ كما تصل** من `GET /drivers/me/commitment`: الساعاتُ والاستراحاتُ والرصيدان وقيمةُ النقاط بعملة الدولة. **ولا تُرسم البطاقةُ
 * حيث المفتاحُ مطفأ** — فلا يرى الكبتنُ وعداً لم يُشعله المالك. والتحويلُ زرٌّ يرسل عددَ النقاط وحدَه، **والقيمةُ تحسبها الخلفيّة**.
 */

import { useCallback, useEffect, useState } from "react";

import { convertCommitmentPoints, getMyCommitment, type MyCommitment } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { digits, formatAmount } from "@/lib/utils";

function hm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return digits(`${h}:${String(m).padStart(2, "0")}`);
}

function clock(value: string): string {
  return digits(value.slice(0, 5));
}

const STATE_LINE: Record<MyCommitment["today"]["state"], string> = {
  before_window: "يبدأ احتسابُ اليوم من {0}",
  idle: "اتّصل لتبدأ مدّةَ اليوم",
  running: "مدّتُك جارية",
  met: "تحقّق يومُك — تُضاف النقاطُ بعد منتصف الليل",
  broken: "انقطعت مدّتُك",
  after_window: "انتهت نافذةُ اليوم",
};

/** **يُعيد حالَ الالتزام كلَّ دقيقة** — ويُستعمل لإشعال إشارات الجهاز حين يكون مفعّلاً. */
export function useCommitment(): [MyCommitment | null, () => void] {
  const [data, setData] = useState<MyCommitment | null>(null);
  const load = useCallback(() => {
    getMyCommitment()
      .then(setData)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, [load]);
  return [data, load];
}

export function CommitmentCardT2({ data, onChanged }: { data: MyCommitment | null; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);

  if (data === null || !data.enabled) return null;
  const { today } = data;
  const share = Math.min(1, today.elapsed_minutes / data.span_minutes);
  const convertible = data.convertible_points;

  const convert = async () => {
    setBusy(true);
    setError(null);
    try {
      await convertCommitmentPoints(convertible);
      onChanged();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : tr("تعذّر التحويل"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="t2-wal-break" id="commitment" aria-labelledby="commitment-title" data-testid="commitment-card">
      <h2 id="commitment-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
        <span>{tr("نقاط الالتزام")}</span>
        <span dir="ltr">{digits(String(data.points_balance))}</span>
      </h2>
      <div className="t2-wal-line">
        <span>{tr(STATE_LINE[today.state], { 0: clock(data.window_start) })}</span>
        <span dir="ltr">{`${hm(today.elapsed_minutes)} / ${hm(data.span_minutes)}`}</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={data.span_minutes}
        aria-valuenow={today.elapsed_minutes}
        style={{ height: 6, borderRadius: 3, background: "var(--t2-line, rgba(0,0,0,0.1))", overflow: "hidden" }}
      >
        <div style={{ width: `${share * 100}%`, height: "100%", background: "var(--t2-accent, #ff6a00)" }} />
      </div>
      {today.state === "running" ? (
        <p className="t2-wal-hint">
          {tr("استراحاتُك {0} من {1} — بقي {2}", {
            0: hm(today.breaks_used_minutes),
            1: hm(data.max_total_break_minutes),
            2: hm(today.remaining_minutes),
          })}
          {today.current_break_minutes > 0
            ? ` · ${tr("استراحةٌ الآن {0} من {1}", { 0: hm(today.current_break_minutes), 1: hm(data.max_break_minutes) })}`
            : ""}
        </p>
      ) : null}
      {today.reason && today.state !== "met" ? (
        <p className="t2-wal-hint">
          {today.reason}
          {today.can_restart ? ` · ${tr("يمكنك أن تبدأ مدّةً جديدة الآن")}` : ""}
        </p>
      ) : null}
      <div className="t2-wal-line">
        <span>{tr("رصيد الاشتراك")}</span>
        <span>{formatAmount(data.credit_balance, data.currency)}</span>
      </div>
      {convertible > 0 && data.credit_value_of_points ? (
        <button type="button" className="t2-hm-row" disabled={busy} onClick={() => void convert()}>
          <span className="t2-hm-row-main">
            <span className="t2-hm-row-title">
              {tr("حوّل {0} نقطة إلى رصيد اشتراك", { 0: digits(String(convertible)) })}
            </span>
          </span>
        </button>
      ) : null}
      {error ? <p className="t2-wal-hint" role="alert">{error}</p> : null}
      <button type="button" className="t2-wal-hint" style={{ textDecoration: "underline" }} onClick={() => setRulesOpen(!rulesOpen)}>
        {rulesOpen ? tr("إخفاء القواعد") : tr("القواعد")}
      </button>
      {rulesOpen ? (
        <ul className="t2-wal-hint" data-testid="commitment-rules">
          <li>
            {tr("اليومُ يُحتسب إن عملت {0} ساعات متّصلةً بين {1} و{2}.", {
              0: digits(String(data.span_minutes / 60)),
              1: clock(data.window_start),
              2: clock(data.window_end),
            })}
          </li>
          <li>
            {tr("الاستراحةُ الواحدة {0} دقيقةً على الأكثر، ومجموعُها {1} دقيقة، ولا تُؤخذ دفعةً واحدة.", {
              0: digits(String(data.max_break_minutes)),
              1: digits(String(data.max_total_break_minutes)),
            })}
          </li>
          <li>{tr("يُحتسب اليومُ ولو لم تصلك رحلة.")}</li>
          <li>{tr("النقاطُ تتحوّل إلى «رصيد اشتراك» يدفع اشتراك TAXO وحدَه — لا يُسحب ولا يُحوَّل ولا يُصرف نقداً.")}</li>
          <li>{tr("تُحتسب من هاتفٍ حقيقيّ داخل منطقة الخدمة، بلا محاكٍ ولا موقعٍ وهميّ، ولحسابٍ واحدٍ في الجهاز.")}</li>
        </ul>
      ) : null}
      {data.recent.length > 0 ? (
        <div data-testid="commitment-recent">
          {data.recent.slice(0, 7).map((day) => (
            <div key={day.day} className="t2-wal-line">
              <span dir="ltr">{digits(day.day)}</span>
              <span>{day.status === "met" ? tr("تحقّق") : day.reason ?? tr("لم يتحقّق")}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
