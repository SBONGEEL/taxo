/** **دقّةُ وقت الوصول** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٢) — المتوقَّعُ مقابل الفعليّ لكلِّ اقترابٍ إلى الراكب.
 *
 * **ما يُقرأ هنا**: كم اقتراباً قِيس، **ومتوسّطُ الخطأ بالدقائق** فيما عُرض للطرفين (بعد التصحيح بالساعة واليوم)، **وما كان سيكون بلا
 * تصحيح** — فيُرى أثرُه — ونسبةُ ما وقع خلال دقيقتين، والانحياز (موجبٌ = يصل متأخّراً عمّا قيل)، ولكلِّ ساعةٍ من اليوم. **والأرقامُ
 * كلُّها من الخلفية** (`GET /admin/eta/accuracy`)؛ لا قسمةَ هنا.
 */

import { useEffect, useState } from "react";

import { getEtaAccuracy } from "@/api/endpoints";
import type { EtaAccuracy } from "@/api/types";
import { Shell } from "@/components/Shell";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { useCountry } from "@/lib/country";
import { digits } from "@/lib/utils";

type EtaWindow = "7" | "28" | "90";

function minutes(value: number | null): string {
  return value === null ? "—" : `${digits(String(value))} د`;
}

export function EtaAccuracyScreen() {
  const { country } = useCountry();
  const [days, setDays] = useState<EtaWindow>("28");
  const [data, setData] = useState<EtaAccuracy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    getEtaAccuracy(country, Number(days))
      .then(setData)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر التحميل"));
  }, [country, days]);

  return (
    <Shell title="دقّة وقت الوصول" subtitle="ما قيل للراكب والكبتن مقابل ما وقع — لكلِّ اقترابٍ إلى الراكب">
      <ErrorNote message={error} />
      <Segmented<EtaWindow>
        label="المدى"
        value={days}
        onPick={setDays}
        options={[
          { key: "7", label: "7 أيام" },
          { key: "28", label: "28 يوماً" },
          { key: "90", label: "90 يوماً" },
        ]}
      />
      {data === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : data.samples === 0 ? (
        <div className="ad-reports-empty">
          <p className="ad-empty-title">لا قياسَ بعد.</p>
          <p className="mt-6 text-11 leading-note text-muted">
            يُقاس كلُّ اقترابٍ حين يضغط الكبتنُ «وصلت»، ما دام «وقت الوصول» مشتعلاً في هذه الدولة.
          </p>
        </div>
      ) : (
        <div className="ad-reports">
          <article className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">{digits(String(data.samples))} اقتراباً مقيساً</p>
              <p className="ad-report-line">متوسّط الخطأ فيما عُرض: {minutes(data.mean_abs_error_min)}</p>
              <p className="ad-report-line">ولو عُرض ما قاله المزوّد بلا تصحيح: {minutes(data.raw_mean_abs_error_min)}</p>
              <p className="ad-report-line">
                خلال دقيقتين مما قيل: {data.within_two_min_percent === null ? "—" : `${digits(String(data.within_two_min_percent))}%`}
              </p>
              <p className="ad-report-line">
                الانحياز: {minutes(data.bias_min)} {data.bias_min !== null && data.bias_min > 0 ? "(يصل متأخّراً عمّا قيل)" : ""}
              </p>
            </div>
          </article>
          <article className="ad-report">
            <div className="ad-report-body">
              <p className="ad-report-name">بساعة الدولة</p>
              {data.by_hour.map((row) => (
                <p key={row.hour} className="ad-report-line">
                  <span dir="ltr" className="ad-ltr">{digits(`${String(row.hour).padStart(2, "0")}:00`)}</span> —{" "}
                  {minutes(row.mean_abs_error_min)} خطأً في {digits(String(row.samples))} اقتراب
                </p>
              ))}
            </div>
          </article>
          <p className="mt-6 text-11 leading-note text-muted">
            التصحيحُ آليّ: وسيطُ «الفعليّ ÷ ما قاله المزوّد» آخرَ 28 يوماً لساعة الدولة ويومها، بعد 20 اقتراباً على الأقل، وبين 0.8 و1.6.
            لا إعدادَ له؛ يُطفأ مع «وقت الوصول» نفسه.
          </p>
        </div>
      )}
    </Shell>
  );
}
