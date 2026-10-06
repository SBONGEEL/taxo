/** أرباحي — TAXO 2.0 «C19» (`design/t2-new/captain/C19-earnings.dc.html`) — SPEC القسم 9 و12/7 (`FUTURE-FEATURES` بند 17).

**والقسم 9 يفصل ما يمر بالمحفظة عمّا يُقبض باليد، وهذه الشاشة تفصلهما**: الرقمُ الكبيرُ صافي ما دخل المحفظة **ويُقال اسمُه تحته**،
والمُحصَّلُ مباشرةً سطرٌ بشرحه. فالكاش وكليك لا يزيدان الرصيد — الكبتن قبضهما فعلاً — لكنهما دخلٌ، وكشفٌ يخفي نصف دخله كشفٌ لا يُصدَّق.

**والصافي قد يكون سالباً ولا يُقصّ عند الصفر**: يومٌ كلُّه كاش ونطاقُ العمولة `all_rides` يترك عليه عمولةً بلا أرباحَ تقابلها —
وإخفاءُ ذلك يجعله يكتشف نقصان رصيده بلا سبب ظاهر.

**ولا حسابَ هنا**: الأرقام الخمسة تصل مجموعةً من `GET /drivers/me/earnings` (القسم 14) — ولا يُطرح رقمٌ من رقمٍ في هذه الشاشة.

**ولغتُها لغةُ C09 حرفاً** — الفترةُ والصافي وتفصيلُه بأصناف «الأرباح» نفسِها (`screens/t2/t2.css`)، **وبرأسٍ برجوعٍ** لأنها صفحةٌ داخلية:
وجهٌ واحدٌ لأرقامٍ واحدة في الشاشتين، **ومن بيتٍ واحد** (`useEarningsScreen`).
*/

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getEarnings } from "@/api/endpoints";
import type { Earnings } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import { countRides } from "./t2/count";

import "./t2/t2.css";
import "./t2/money.css";

type Period = Earnings["period"];

export const PERIOD_LABEL: Record<Period, string> = {
  today: "اليوم",
  week: "الأسبوع",
  month: "الشهر",
};

/** **حالُ «أرباحي» — بيتٌ واحدٌ للشاشتين** (هذه وC09 في `screens/t2`): الفترةُ وأرقامُها الخمسة
 * من `GET /drivers/me/earnings` كما تصل. */
export function useEarningsScreen() {
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

  return {
    goBack,
    period,
    setPeriod,
    data,
    error,
  };
}

export function EarningsScreen() {
  const { goBack, period, setPeriod, data, error } = useEarningsScreen();

  // **الإشارةُ من النصّ** — لا طرحَ ولا مقارنةَ بصفر
  const negative = data ? data.net.trimStart().startsWith("-") : false;

  return (
    <div className="t2 t2-ern scr">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => goBack()}
        >
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">أرباحي</h1>
        <div className="t2-wal-period" role="tablist" aria-label="الفترة">
          {(Object.keys(PERIOD_LABEL) as Period[]).map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={key === period}
              className={
                key === period ? "t2-wal-period-opt on" : "t2-wal-period-opt"
              }
              onClick={() => setPeriod(key)}
            >
              {PERIOD_LABEL[key]}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}

      {data === null ? (
        error ? null : (
          <div className="t2-wal-wait">
            <Spinner />
          </div>
        )
      ) : (
        <>
          <div className={negative ? "t2-wal-net negative" : "t2-wal-net"}>
            <span className="t2-wal-net-num" dir="ltr">
              {digits(data.net)}
            </span>
            <span className="t2-wal-net-cur">
              {CURRENCY_LABEL[data.currency]}
            </span>
          </div>
          <div className="t2-wal-sub">
            <span>صافي ما دخل محفظتك</span>
            <span>{countRides(data.completed_rides)}</span>
          </div>

          <div className="t2-wal-break">
            <div className="t2-wal-line">
              <span>أرباح الرحلات</span>
              <span dir="ltr">{digits(data.wallet_earnings)}</span>
            </div>
            <div className="t2-wal-line">
              <span>عمولة</span>
              <span dir="ltr">{digits(data.commission)}</span>
            </div>
            {/* **سطرٌ مستقل** (12-و): البقشيشُ دخلَ المحفظة **بلا عمولةٍ عليه** وهو الوحيد كذلك — فبغير سطرِه لا يتّسق «أرباح
                الرحلات» مع «عمولة» لمن يجمعهما بيده. ويظهر حين يوجد فقط */}
            {Number(data.tips) > 0 ? (
              <div className="t2-wal-line ok">
                <span>بقشيش — كاملاً بلا عمولة</span>
                <span dir="ltr">{digits(data.tips)}</span>
              </div>
            ) : null}
            {/* **ما اقتُطع سداداً للسلفة** (البند ١٥) — رقمٌ ينقص من الأرباح بلا سببٍ مكتوبٍ يُقرأ عطباً. ولا يظهر لمن لا سلفةَ له */}
            {Number(data.advance_repaid) > 0 ? (
              <div className="t2-wal-line">
                <span>سدادُ سلفة</span>
                <span dir="ltr">{digits(data.advance_repaid)}</span>
              </div>
            ) : null}
            <div className="t2-wal-line">
              <span>مُحصَّل مباشرة</span>
              <span>
                <span dir="ltr">{digits(data.directly_collected)}</span>{" "}
                {CURRENCY_LABEL[data.currency]}
              </span>
            </div>
            <p className="t2-wal-hint">
              كاش وكليك قبضتَهما من الركّاب مباشرةً — لا تدخل رصيد محفظتك،
              وتظهر هنا لأنها من دخلك.
            </p>
            {negative ? (
              <p className="t2-wal-hint warn">
                العمولة تجاوزت أرباح المحفظة في هذه الفترة — عمولةُ الرحلات
                النقدية تُخصم من رصيدك ولو لم يمرّ مالُها به.
              </p>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
