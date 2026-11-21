/** **«التحويل بين الدول»** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`).
 *
 * **سعرُ صرفٍ لكلِّ اتّجاه** (ستّة: كلُّ عملتين بالاتّجاهين — مقلوبُ السعر ليس سعرَ الشراء) **ورسمُه** نسبةً من المبلغ المرسَل (0 افتراضاً)،
 * **وتاريخُ ضبطه ومن ضبطه**؛ **وحدّا كلِّ دولة مرسلٍ** يوميّاً وشهريّاً بعملتها. **وما لم يُضبط يُعرض فارغاً** — والتحويلُ في اتّجاهٍ بلا سعرٍ
 * أو من دولةٍ بلا حدٍّ يُردّ.
 *
 * **والمفتاحُ ليس هنا**: «التحويل بين الدول» في «الإعدادات ← المفاتيح»، **مطفأٌ ويُشعله المالكُ بعد مراجعة الجانب القانونيّ** — وضبطُ هذه
 * الصفحة لا يُشعل شيئاً. **والحسابُ كلُّه في الخلفية** (§14): هذه تكتب ما يقرّره المشرفُ وتعرضه.
 */

import { useEffect, useState } from "react";

import { getCrossLimits, getFxRates, putCrossLimits, putFxRate } from "@/api/endpoints";
import type { CrossLimit, FxRate } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import type { CountryCode } from "@/api/types";
import { currencyLabel, day } from "@/lib/format";
import { digits } from "@/lib/utils";

const COUNTRY_LABEL: Record<CountryCode, string> = { LY: "ليبيا", JO: "الأردن", DZ: "الجزائر" };

function RateRow({ row, onSaved }: { row: FxRate; onSaved: (next: FxRate) => void }) {
  const [rate, setRate] = useState(row.rate ?? "");
  const [fee, setFee] = useState(row.fee_percent ?? "0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = rate !== (row.rate ?? "") || fee !== (row.fee_percent ?? "0");
  return (
    <article className="ad-report">
      <div className="ad-report-body">
        <p className="ad-report-name">
          1 {currencyLabel(row.from_currency)} ← {currencyLabel(row.to_currency)}
        </p>
        <p className="ad-report-line">
          {row.rate === null
            ? "لم يُضبط — التحويلُ في هذا الاتّجاه يُردّ"
            : `ضُبط ${day(row.set_at ?? "")}${row.set_by_name ? ` · ${row.set_by_name}` : ""}`}
        </p>
        <div className="mt-6 flex flex-wrap items-end gap-8">
          <Field
            label={`كم ${currencyLabel(row.to_currency)} مقابل 1 ${currencyLabel(row.from_currency)}`}
            inputMode="decimal"
            dir="ltr"
            value={rate}
            onChange={(event) => setRate(digits(event.target.value))}
          />
          <Field
            label="رسم التحويل ٪ (0–20)"
            inputMode="decimal"
            dir="ltr"
            value={fee}
            onChange={(event) => setFee(digits(event.target.value))}
          />
          <Button
            size="md"
            disabled={busy || !dirty || rate.trim() === ""}
            onClick={() => {
              setBusy(true);
              setError(null);
              putFxRate({ from_currency: row.from_currency, to_currency: row.to_currency, rate, fee_percent: fee || "0" })
                .then(onSaved)
                .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر الحفظ"))
                .finally(() => setBusy(false));
            }}
          >
            حفظ
          </Button>
        </div>
        <ErrorNote message={error} />
      </div>
    </article>
  );
}

function LimitRow({ row, onSaved }: { row: CrossLimit; onSaved: (next: CrossLimit) => void }) {
  const [daily, setDaily] = useState(row.daily_limit);
  const [monthly, setMonthly] = useState(row.monthly_limit);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unset = Number(row.daily_limit) <= 0 || Number(row.monthly_limit) <= 0;
  return (
    <article className="ad-report">
      <div className="ad-report-body">
        <p className="ad-report-name">
          من {COUNTRY_LABEL[row.country_code]} ({currencyLabel(row.currency)})
        </p>
        <p className="ad-report-line">{unset ? "لم يُضبط — التحويلُ إلى دولةٍ أخرى من هنا يُردّ" : "حدّا كلِّ مرسل"}</p>
        <div className="mt-6 flex flex-wrap items-end gap-8">
          <Field label="الحدّ اليوميّ" inputMode="decimal" dir="ltr" value={daily} onChange={(e) => setDaily(digits(e.target.value))} />
          <Field label="الحدّ الشهريّ" inputMode="decimal" dir="ltr" value={monthly} onChange={(e) => setMonthly(digits(e.target.value))} />
          <Button
            size="md"
            disabled={busy || (daily === row.daily_limit && monthly === row.monthly_limit)}
            onClick={() => {
              setBusy(true);
              setError(null);
              putCrossLimits(row.country_code, { daily_limit: daily || "0", monthly_limit: monthly || "0" })
                .then(onSaved)
                .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر الحفظ"))
                .finally(() => setBusy(false));
            }}
          >
            حفظ
          </Button>
        </div>
        <ErrorNote message={error} />
      </div>
    </article>
  );
}

export function CrossTransferScreen() {
  const [rates, setRates] = useState<FxRate[] | null>(null);
  const [limits, setLimits] = useState<CrossLimit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getFxRates(), getCrossLimits()])
      .then(([r, l]) => {
        setRates(r);
        setLimits(l);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر التحميل"));
  }, []);

  return (
    <Shell
      title="التحويل بين الدول"
      subtitle="أسعارُ الصرف ورسومُها وحدودُ المرسل — والمفتاحُ في «الإعدادات»، مطفأٌ حتى يُشعله المالك"
    >
      <ErrorNote message={error} />
      {rates === null || limits === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : (
        <div className="ad-reports">
          <p className="text-11 leading-note text-muted">
            ما يصل المستلمَ = المبلغُ × السعر، مقرَّباً للأسفل إلى أصغر وحدةٍ في عملته؛ والرسمُ يُضاف على المرسل بعملته. والراكبُ يرى الأرقامَ
            كلَّها في ورقة التأكيد قبل الإرسال، ولا يُرسَل غيرُ ما رآه إن تغيّر السعرُ بينهما.
          </p>
          {rates.map((row) => (
            <RateRow
              key={`${row.from_currency}-${row.to_currency}`}
              row={row}
              onSaved={(next) => setRates((all) => (all ?? []).map((item) =>
                item.from_currency === next.from_currency && item.to_currency === next.to_currency ? next : item))}
            />
          ))}
          {limits.map((row) => (
            <LimitRow
              key={row.country_code}
              row={row}
              onSaved={(next) => setLimits((all) => (all ?? []).map((item) => (item.country_code === next.country_code ? next : item)))}
            />
          ))}
        </div>
      )}
    </Shell>
  );
}
