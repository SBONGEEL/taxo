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
import { Pills } from "@/components/Table";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { arabicDigits, cn } from "@/lib/utils";

const CURRENCY_LABEL: Record<string, string> = { JOD: "د.أ", LYD: "د.ل" };

/** ألوانُ توزيع طرق الدفع كما في `DESIGN.md` §3.4 — لا اجتهادَ فيها. */
const METHOD_TONE: Record<string, string> = {
  cash: "bg-warn",
  wallet: "bg-ok",
  card: "bg-ink",
  cliq: "bg-muted",
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
    >
      <Pills
        value={period}
        onPick={(key) => setPeriod(key as StatsPeriod)}
        options={[
          { key: "today", label: "اليوم" },
          { key: "week", label: "الأسبوع" },
          { key: "month", label: "الشهر" },
        ]}
      />

      <ErrorNote message={error} />

      {data === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <>
          <div className="grid gap-12 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi
              label="الرحلات المكتملة"
              value={arabicDigits(String(data.completed_rides))}
            />
            <Kpi
              label="إجمالي الإيراد"
              value={`${arabicDigits(data.revenue)} ${currency}`}
            />
            <Kpi
              label="سائقون متصلون الآن"
              value={arabicDigits(String(data.online_drivers))}
              hint="من له حضورٌ حيّ — لا من رفع المفتاح ثم اختفى"
            />
            <Kpi
              label="اشتراكات فعّالة"
              value={arabicDigits(String(data.active_subscriptions))}
            />
            <Kpi
              label="نزاعات مفتوحة"
              value={arabicDigits(String(data.open_disputes))}
              tone={data.open_disputes > 0 ? "text-danger" : undefined}
            />
          </div>

          <div className="mt-14 grid gap-14 xl:grid-cols-[1.6fr_1fr]">
            <section className="rounded-16 border border-line bg-surface p-18">
              <h2 className="mb-14 text-14 font-bold text-ink">
                الرحلات على مدار اليوم
              </h2>
              <HourChart buckets={data.rides_by_hour} />
            </section>

            <section className="rounded-16 border border-line bg-surface p-18">
              <h2 className="mb-4 text-14 font-bold text-ink">
                توزيع طرق الدفع
              </h2>
              <p className="mb-14 text-11 leading-snug text-muted">
                عدداً لا مبلغاً: السؤال بأي شيء يدفع الناس. والكاش يُسوّى يدوياً
                من قسم المحافظ · البطاقة عبر Telr.
              </p>
              <MethodBars mix={data.payment_mix} />
            </section>
          </div>

          <div className="mt-14 grid gap-12 lg:grid-cols-3">
            <ActionCard
              title="وثائق بانتظار الاعتماد"
              body="سائقون جدد لا يمكنهم العمل قبل المراجعة"
              count={data.pending_documents}
              onOpen={() => navigate("/drivers")}
            />
            <ActionCard
              title="طلبات سحب معلّقة"
              body="تحويلات بانتظار موافقة المالية"
              count={data.pending_withdrawals}
              onOpen={() => navigate("/finance")}
            />
            <ActionCard
              title="نزاعات مفتوحة"
              body="حوالاتٌ لم تُؤكَّد بحاجة لقرار"
              count={data.open_disputes}
              onOpen={() => navigate("/disputes")}
            />
          </div>

          <p className="mt-14 text-11 text-muted">
            رحلاتٌ جارية الآن: {arabicDigits(String(data.active_rides))} ·
            ملغاةٌ في هذه الفترة: {arabicDigits(String(data.cancelled_rides))}
          </p>
        </>
      )}
    </Shell>
  );
}

function Kpi({
  label,
  value,
  hint,
  tone = "text-ink",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-16 border border-line bg-surface p-16">
      <div className="text-11 text-muted">{label}</div>
      <div className={cn("mt-4 text-24 font-bold", tone)}>{value}</div>
      {hint ? (
        <div className="mt-4 text-10 leading-snug text-muted">{hint}</div>
      ) : null}
    </div>
  );
}

/** أعمدةُ الساعات — `DESIGN.md` §3.4: ارتفاعٌ نسبيٌّ للأقصى، وذروةٌ بلون `--tx`. */
function HourChart({ buckets }: { buckets: number[] }) {
  const peak = Math.max(...buckets, 1);

  return (
    <div dir="ltr" className="flex h-150 items-end gap-4">
      {buckets.map((value, hour) => (
        <div key={hour} className="flex flex-1 flex-col items-center gap-4">
          <div
            className={cn(
              "w-full rounded-t-4",
              value === peak && value > 0 ? "bg-ink" : "bg-line",
            )}
            // كعبٌ صغير للصفر: صفٌّ من أعمدةٍ بلا ارتفاعٍ يقرأ «لم يُرسم»
            // لا «لا رحلات»، ويومٌ هادئ حقيقةٌ لا عطل
            style={{ height: `${Math.max((value / peak) * 120, 2)}px` }}
            title={`${value}`}
          />
          {hour % 3 === 0 ? (
            <span className="text-8.5 text-muted">
              {arabicDigits(String(hour))}
            </span>
          ) : (
            <span className="text-8.5 text-transparent">.</span>
          )}
        </div>
      ))}
    </div>
  );
}

/** أشرطةٌ أفقية — `DESIGN.md` §3.4، بألوان القنوات المحدَّدة فيه. */
function MethodBars({ mix }: { mix: Record<string, number> }) {
  const total = Object.values(mix).reduce((sum, value) => sum + value, 0);

  return (
    <ul className="flex flex-col gap-11">
      {Object.entries(mix).map(([method, count]) => (
        <li key={method}>
          <div className="mb-4 flex items-baseline justify-between text-11">
            <span className="text-muted">{METHOD_LABEL[method] ?? method}</span>
            <span className="font-semibold text-ink">
              {arabicDigits(String(count))}
            </span>
          </div>
          <div className="h-6 overflow-hidden rounded-full bg-surface-2">
            <div
              className={cn("h-full rounded-full", METHOD_TONE[method])}
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
  count,
  onOpen,
}: {
  title: string;
  body: string;
  count: number;
  onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex items-center gap-14 rounded-16 border border-line bg-surface p-16 text-start"
    >
      <span
        className={cn(
          "text-24 font-bold",
          count > 0 ? "text-warn" : "text-muted",
        )}
      >
        {arabicDigits(String(count))}
      </span>
      <span className="flex-1">
        <span className="block text-13 font-semibold text-ink">{title}</span>
        <span className="block text-11 leading-snug text-muted">{body}</span>
      </span>
    </button>
  );
}
