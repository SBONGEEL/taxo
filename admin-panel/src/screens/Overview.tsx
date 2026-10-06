/** نظرة عامة — SPEC القسم 13/1، و`DESIGN.md` §3.2/3.4.
 *
 * **كلُّ رقمٍ هنا يصل جاهزاً.** لا تجمع هذه الشاشة صفّاً ولا تقسم مبلغاً: العدُّ
 * والمجموع في `services/stats.py`، وما تفعله الواجهة أن ترسم. ولو جمعت هنا
 * لعرضت رقماً لا يطابق القاعدة حين تُقصّ الصفحة، ولا يطابق نفسه بين متصفحين.
 *
 * **واليومُ يومُ الدولة**: النافذة تُحسب بمِنطقتها في الخلفية، وأعمدةُ الساعات
 * أربعٌ وعشرون بترتيب ساعاتها — فعمودُ الثامنة يحمل رحلات الثامنة عندهم.
 *
 * **والرسمُ بلا شبكةٍ ولا محورٍ ولا مفتاح** (`DESIGN.md` §3.4): التسمية تحت
 * العمود والقيمة فوقه، وهذا مقصودٌ وجزءٌ من مزاج النظام — لا نقصٌ يُستكمل.
 * **وبلغة TAXO 2.0** (A02 — `design/t2-new/admin/A02-overview.dc.html`): أعمدةُ C09 بالحافّة لوناً والذروةُ بالجمر، والأرقامُ
 * بخطّ Unbounded وعملتُها بعدها بالخافت، ومبدّلُ المدى مقطَّعٌ في رأس الصفحة.
 *
 * **وبطاقاتُ الإجراء تفتح شاشتها** لا تعرض رقماً وحسب: «وثائق بانتظار
 * الاعتماد» بلا طريقٍ إلى المراجعة عدّادٌ يُقلق ولا يُعين.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getOverview } from "@/api/endpoints";
import type { Overview, StatsPeriod } from "@/api/types";
import { Shell } from "@/components/Shell";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { digits, cn } from "@/lib/utils";
import { Icon } from "@/taxo2";

const CURRENCY_LABEL: Record<string, string> = { JOD: "د.أ", LYD: "د.ل" };

/** ألوانُ توزيع طرق الدفع كما في `DESIGN.md` §3.4 — لا اجتهادَ فيها: الكاشُ تنبيه، والمحفظةُ نجاح، والبطاقةُ نصّ، وكليكُ خافت
 *  (`t2/screens.css` — `.ad-mix-fill.ad-pay-*`). */
const METHOD_TONE: Record<string, string> = {
  cash: "ad-pay-cash",
  wallet: "ad-pay-wallet",
  card: "ad-pay-card",
  cliq: "ad-pay-cliq",
};

const METHOD_LABEL: Record<string, string> = {
  cash: "كاش",
  wallet: "محفظة",
  card: "بطاقة",
  cliq: "كليك",
};

export function OverviewScreen() {
  const navigate = useNavigate();
  const { country } = useCountry();
  const countryConfig = useCountryConfig(country);
  const currency = CURRENCY_LABEL[countryConfig?.currency ?? "JOD"] ?? "";

  const [period, setPeriod] = useState<StatsPeriod>("today");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setData(null);
    setData(await getOverview(country, period));
  }, [country, period]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإحصاءات",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="نظرة عامة"
      subtitle="أرقامُ السوق المعروض — محسوبةً بتوقيته لا بتوقيت الخادم"
      actions={
        <Segmented
          label="المدى"
          value={period}
          onPick={setPeriod}
          options={[
            { key: "today", label: "اليوم" },
            { key: "week", label: "الأسبوع" },
            { key: "month", label: "الشهر" },
          ]}
        />
      }
    >
      <ErrorNote message={error} />

      {data === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : (
        <>
          <div className="ad-kpis">
            <Kpi
              label="الرحلات المكتملة"
              value={digits(String(data.completed_rides))}
            />
            <Kpi
              label="إجمالي الإيراد"
              value={digits(data.revenue)}
              unit={currency}
            />
            <Kpi
              label="سائقون متصلون الآن"
              value={digits(String(data.online_drivers))}
              hint="من له حضورٌ حيّ — لا من رفع المفتاح ثم اختفى"
            />
            <Kpi
              label="اشتراكات فعّالة"
              value={digits(String(data.active_subscriptions))}
            />
            <Kpi
              label="نزاعات مفتوحة"
              value={digits(String(data.open_disputes))}
              danger={data.open_disputes > 0}
            />
          </div>

          <div className="ad-charts">
            <section className="ad-panel">
              <h2 className="ad-panel-title">الرحلات على مدار اليوم</h2>
              <HourChart buckets={data.rides_by_hour} />
            </section>

            <section className="ad-panel">
              <h2 className="ad-panel-title">توزيع طرق الدفع</h2>
              <p className="ad-panel-sub">
                عدداً لا مبلغاً: السؤال بأي شيء يدفع الناس. والكاش يُسوّى يدوياً
                من قسم المحافظ · البطاقة عبر Telr.
              </p>
              <MethodBars mix={data.payment_mix} />
            </section>
          </div>

          <div className="ad-waits">
            <ActionCard
              title="وثائق بانتظار الاعتماد"
              body="سائقون جدد لا يمكنهم العمل قبل المراجعة"
              icon="description"
              count={data.pending_documents}
              onOpen={() => navigate("/drivers")}
            />
            <ActionCard
              title="طلبات سحب معلّقة"
              body="تحويلات بانتظار موافقة المالية"
              icon="account_balance_wallet"
              count={data.pending_withdrawals}
              onOpen={() => navigate("/finance")}
            />
            <ActionCard
              title="نزاعات مفتوحة"
              body="حوالاتٌ لم تُؤكَّد بحاجة لقرار"
              icon="gavel"
              count={data.open_disputes}
              onOpen={() => navigate("/disputes")}
            />
          </div>

          <p className="ad-foot">
            رحلاتٌ جارية الآن: {digits(String(data.active_rides))} ·
            ملغاةٌ في هذه الفترة: {digits(String(data.cancelled_rides))}
          </p>
        </>
      )}
    </Shell>
  );
}

function Kpi({
  label,
  value,
  unit,
  hint,
  danger = false,
}: {
  label: string;
  value: string;
  /** العملةُ بعد الرقم وبالخافت (الهوية: «3.750 د.أ») */
  unit?: string;
  hint?: string;
  danger?: boolean;
}) {
  return (
    <div className={danger ? "ad-kpi danger" : "ad-kpi"}>
      <div className="ad-kpi-label">{label}</div>
      <div className="ad-amount">
        <span className="ad-num">{value}</span>
        {unit ? <span className="ad-cur">{unit}</span> : null}
      </div>
      {hint ? <div className="ad-kpi-hint">{hint}</div> : null}
    </div>
  );
}

/** أعمدةُ الساعات — ارتفاعٌ نسبيٌّ للأقصى، **والذروةُ بالجمر وقيمتُها فوقها** (C09). */
function HourChart({ buckets }: { buckets: number[] }) {
  const peak = Math.max(...buckets, 1);

  return (
    <>
      <div className="ad-bars">
        {buckets.map((value, hour) => {
          const top = value === peak && value > 0;
          return (
            <div key={hour} className={top ? "ad-bar peak" : "ad-bar"}>
              {top ? (
                <span className="ad-bar-value">{digits(String(value))}</span>
              ) : null}
              <span
                className="ad-bar-fill"
                // كعبٌ صغير للصفر: صفٌّ من أعمدةٍ بلا ارتفاعٍ يقرأ «لم يُرسم»
                // لا «لا رحلات»، ويومٌ هادئ حقيقةٌ لا عطل
                style={{ height: `${Math.max((value / peak) * 132, 3)}px` }}
                title={`${value}`}
              />
            </div>
          );
        })}
      </div>
      <div className="ad-bar-labels" aria-hidden="true">
        {buckets.map((_, hour) => (
          <span key={hour} className={hour % 3 === 0 ? undefined : "off"}>
            {digits(String(hour))}
          </span>
        ))}
      </div>
    </>
  );
}

/** أشرطةٌ أفقية بألوان القنوات. */
function MethodBars({ mix }: { mix: Record<string, number> }) {
  const total = Object.values(mix).reduce((sum, value) => sum + value, 0);

  return (
    <ul className="ad-mix">
      {Object.entries(mix).map(([method, count]) => (
        <li key={method}>
          <div className="ad-mix-top">
            <span className="ad-mix-name">{METHOD_LABEL[method] ?? method}</span>
            <span className="ad-mix-count">{digits(String(count))}</span>
          </div>
          <div className="ad-mix-track">
            <div
              className={cn("ad-mix-fill", METHOD_TONE[method])}
              style={{ width: total ? `${(count / total) * 100}%` : "0%" }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function ActionCard({
  title,
  body,
  icon,
  count,
  onOpen,
}: {
  title: string;
  body: string;
  icon: string;
  count: number;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={count > 0 ? "ad-wait due" : "ad-wait"}
    >
      <span className={count > 0 ? "ad-tile warn" : "ad-tile"}>
        <Icon name={icon} />
      </span>
      <span className="ad-wait-text">
        <span className="ad-wait-title">{title}</span>
        <span className="ad-wait-body">{body}</span>
      </span>
      <span className="ad-num">{digits(String(count))}</span>
      <Icon name="chevron_left" className="ad-wait-chev" />
    </button>
  );
}
