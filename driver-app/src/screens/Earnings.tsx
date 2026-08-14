/** أرباحي — SPEC القسم 9 و12/7 (`FUTURE-FEATURES` بند 17).

**والقسم 9 يفصل ما يمر بالمحفظة عمّا يُقبض باليد، وهذه الشاشة تفصلهما بصرياً**:
رقمان في بطاقتين لا رقمٌ واحد. فالكاش وكليك لا يزيدان الرصيد — الكبتن قبضهما
فعلاً — لكنهما دخلٌ، وكشفٌ يخفي نصف دخله كشفٌ لا يُصدَّق.

**والصافي قد يكون سالباً ولا يُقصّ عند الصفر**: يومٌ كلُّه كاش ونطاقُ العمولة
`all_rides` يترك عليه عمولةً بلا أرباحَ تقابلها — وإخفاءُ ذلك يجعله يكتشف
نقصان رصيده بلا سبب ظاهر.

**ولا حسابَ هنا**: الأرقام الخمسة تصل مجموعةً من `GET /drivers/me/earnings`
(القسم 14) — ولا يُطرح رقمٌ من رقمٍ في هذه الشاشة.
*/

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getEarnings } from "@/api/endpoints";
import type { Earnings } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { arabicDigits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

type Period = Earnings["period"];

const PERIOD_LABEL: Record<Period, string> = {
  today: "اليوم",
  week: "الأسبوع",
  month: "الشهر",
};

export function EarningsScreen() {
  const goBack = useGoBack();
  const [period, setPeriod] = useState<Period>("today");
  const [data, setData] = useState<Earnings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setData(null);
    setData(await getEarnings(period));
  }, [period]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الأرباح"),
    );
  }, [load]);

  const currency = data ? CURRENCY_LABEL[data.currency] : "";
  const negative = data ? data.net.trimStart().startsWith("-") : false;

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">أرباحي</h1>
      </div>

      <div className="flex gap-8">
        {(Object.keys(PERIOD_LABEL) as Period[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setPeriod(key)}
            className={cn(
              "pressable flex-1 rounded-13 border py-10 text-12.5 font-semibold",
              key === period
                ? "border-ink text-ink"
                : "border-line text-muted",
            )}
          >
            {PERIOD_LABEL[key]}
          </button>
        ))}
      </div>

      <ErrorNote message={error} />

      {data === null ? (
        error ? null : <Spinner className="mx-auto my-38" />
      ) : (
        <div className="mt-14 space-y-10">
          <div className="card p-16">
            <div className="text-11.5 text-muted">صافي ما دخل محفظتك</div>
            <div
              className={cn(
                "mt-4 text-30 font-bold",
                negative ? "text-danger" : "text-ink",
              )}
            >
              {arabicDigits(data.net)}{" "}
              <span className="text-15 text-muted">{currency}</span>
            </div>
            <div className="mt-8 flex items-center justify-between text-11.5">
              <span className="text-muted">
                أرباح الرحلات {arabicDigits(data.wallet_earnings)}
              </span>
              <span className="text-muted">
                عمولة {arabicDigits(data.commission)}
              </span>
            </div>
            {/* **سطرٌ ثالثٌ مستقل** (12-و): البقشيشُ دخلَ المحفظة **بلا عمولةٍ
                عليه** وهو الوحيد كذلك — فبغير سطرِه لا يتّسق «أرباح الرحلات»
                مع «عمولة» لمن يجمعهما بيده. ويظهر حين يوجد فقط: صفرٌ دائمٌ في
                سوقٍ لا بقشيشَ فيه سطرٌ يشغل الشاشة بلا معنى */}
            {Number(data.tips) > 0 ? (
              <div className="mt-4 text-11.5 text-ok">
                بقشيش {arabicDigits(data.tips)} — كاملاً بلا عمولة
              </div>
            ) : null}
            {/* **وسطرٌ خامسٌ منذ البند ١٥**: ما اقتُطع سداداً للسلفة —
                رقمٌ ينقص من الأرباح بلا سببٍ مكتوبٍ يُقرأ عطباً، ويُسأل عنه
                الدعمُ مرةً لكلِّ كبتن. ولا يظهر لمن لا سلفةَ له */}
            {Number(data.advance_repaid) > 0 ? (
              <div className="mt-4 text-11.5 text-muted">
                سدادُ سلفة {arabicDigits(data.advance_repaid)}
              </div>
            ) : null}
            {negative ? (
              <p className="mt-8 text-11 leading-note text-warn">
                العمولة تجاوزت أرباح المحفظة في هذه الفترة — عمولةُ الرحلات
                النقدية تُخصم من رصيدك ولو لم يمرّ مالُها به.
              </p>
            ) : null}
          </div>

          <div className="card p-16">
            <div className="flex items-baseline justify-between">
              <span className="text-11.5 text-muted">مُحصَّل مباشرة</span>
              <span className="text-15 font-bold text-ink">
                {arabicDigits(data.directly_collected)}{" "}
                <span className="text-11.5 text-muted">{currency}</span>
              </span>
            </div>
            <p className="mt-6 text-11 leading-note text-muted">
              كاش وكليك قبضتَهما من الركّاب مباشرةً — لا تدخل رصيد محفظتك،
              وتظهر هنا لأنها من دخلك.
            </p>
          </div>

          <div className="card p-16">
            <div className="flex items-baseline justify-between">
              <span className="text-11.5 text-muted">رحلات مكتملة</span>
              <span className="text-15 font-bold text-ink">
                {arabicDigits(String(data.completed_rides))}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
