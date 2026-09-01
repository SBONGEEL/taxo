/** التقارير والإحصاءات — SPEC القسم 13/5، و`DESIGN.md` §3.4/§5.4.
 *
 * **كلُّ رقمٍ هنا نزل محسوباً.** «متوسط قيمة الرحلة» و«معدّل الإلغاء» كلاهما
 * قسمةُ مجموعٍ على عدد، والمجموعُ والعددُ يخرجان من الجدول كلِّه لا من صفحةٍ
 * مسقوفة. فلو قُسما في الواجهة لقرأت الشاشةُ متوسطَ الخمسين صفاً الأولى
 * وسمّته متوسط الشهر — وهو نفس ما يحصر القسم 14 الحسابَ في الخلفية لأجله.
 *
 * **وما ليس في الشاشة مقصودٌ كما ما فيها**، والتصميم يرسم اثنين منه:
 *
 * - **«أعلى المناطق طلباً» غير موجود**: لا جدولَ مناطق في هذا المخطط ولا عمودَ
 *   منطقةٍ على الرحلة، ورسمُها من الإحداثيات اختراعُ تقسيمٍ لم يقله أحد.
 * - **و«معدّل قبول الطلبات» محذوفٌ صراحةً** (`FUTURE-FEATURES` بند 24-أ): لا
 *   `ride_offers` يُسجّل العروض، وحسابُه من الرحلات وحدها يقيس شيئاً آخر
 *   ويسمّيه باسمه.
 *
 * **و«سائقٌ نشط» من أنهى رحلةً في الفترة** لا من رفع مفتاح الاتصال مرةً:
 * الحضورُ نيّةٌ والرحلةُ عمل — وعدُّ المتصلين الآن مكانُه «نظرة عامة».
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getReports } from "@/api/endpoints";
import type { Reports, StatsPeriod } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { money, shortDay } from "@/lib/format";
import { digits, cn } from "@/lib/utils";

const PERIOD_LABEL: Record<StatsPeriod, string> = {
  today: "اليوم",
  week: "الأسبوع",
  month: "الشهر",
};

export function ReportsScreen() {
  const { country } = useCountry();

  const [period, setPeriod] = useState<StatsPeriod>("month");
  const [data, setData] = useState<Reports | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setData(null);
    setData(await getReports(country, period));
  }, [country, period]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة التقارير",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="التقارير والإحصاءات"
      subtitle="نِسَبٌ ومتوسطاتٌ محسوبةٌ على الفترة كلِّها — لا على ما ظهر في الصفحة"
      actions={
        <div className="flex items-center gap-3 rounded-full bg-surface-2 p-3">
          {(["today", "week", "month"] as StatsPeriod[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setPeriod(key)}
              className={cn(
                "rounded-full px-13 py-6 text-12 font-semibold",
                period === key ? "bg-surface text-ink" : "text-muted",
              )}
            >
              {PERIOD_LABEL[key]}
            </button>
          ))}
        </div>
      }
    >
      <ErrorNote message={error} />

      {data === null ? (
        error ? null : <Spinner className="mx-auto my-38" />
      ) : (
        <>
          <div className="grid gap-14 md:grid-cols-2 xl:grid-cols-4">
            <Kpi
              label="متوسط قيمة الرحلة"
              value={money(data.avg_ride_fare, data.currency)}
              hint="مجموعُ أجور المكتملة ÷ عددها"
            />
            <Kpi
              label="معدّل الإلغاء"
              value={`${digits(data.cancellation_rate)}٪`}
              hint="الملغاة ÷ (المكتملة + الملغاة)"
            />
            <Kpi
              label="سائقون نشطون"
              value={digits(String(data.active_drivers))}
              hint="من أنهى رحلةً في الفترة — لا من كان متصلاً"
            />
            <Kpi
              label="إيراد الاشتراكات"
              value={money(data.subscription_revenue, data.currency)}
              hint={`${digits(String(data.subscriptions_sold))} اشتراكاً بيع في الفترة`}
            />
          </div>

          <section className="mt-18 rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-14 text-14 font-bold text-ink">
              الإيراد اليومي · {PERIOD_LABEL[period]}
            </h2>
            <RevenueBars data={data} />
          </section>

          <div className="mt-18 grid gap-16 lg:grid-cols-2">
            <section>
              <h2 className="mb-12 text-14 font-bold text-ink">أفضل السائقين</h2>
              <Table
                height="compact"
                columns="1.4fr 0.8fr 1fr 0.7fr"
                headers={["السائق", "الرحلات", "الإيراد", "التقييم"]}
                rows={data.top_drivers}
                keyOf={(row) => row.driver_id}
                empty={{
                  title: "لا رحلات مكتملة في الفترة",
                  hint: "بدّل الفترة أو الدولة من الرأس.",
                }}
                render={(row) => (
                  <>
                    <span className="min-w-0 truncate font-semibold text-ink">
                      {row.name}
                    </span>
                    <span className="text-muted">
                      {digits(String(row.completed_rides))}
                    </span>
                    <span className="text-ink">
                      {money(row.revenue, data.currency)}
                    </span>
                    <span className="text-ink">
                      {row.rating_avg === "0.00"
                        ? "—"
                        : `★ ${digits(row.rating_avg)}`}
                    </span>
                  </>
                )}
              />
            </section>

            <section>
              <h2 className="mb-12 text-14 font-bold text-ink">
                مبيعات الباقات
              </h2>
              <Table
                height="compact"
                columns="1.6fr 0.7fr 1fr"
                headers={["الباقة", "بيعت", "الإيراد"]}
                rows={data.sales_by_plan}
                keyOf={(row) => row.plan_id}
                empty={{
                  title: "لا اشتراكات بيعت في الفترة",
                  hint: "القناتان اليدويتان تُسجَّلان من شاشة الاشتراكات بعد القبض.",
                }}
                render={(row) => (
                  <>
                    <span className="min-w-0 truncate font-semibold text-ink">
                      {row.plan_name}
                    </span>
                    <span className="text-muted">
                      {digits(String(row.sold))}
                    </span>
                    <span className="text-ink">
                      {money(row.revenue, data.currency)}
                    </span>
                  </>
                )}
              />
            </section>
          </div>

          <p className="mt-18 max-w-prose text-11.5 leading-note text-muted">
            الرحلاتُ النقدية وكليك تدخل هذه الأرقام وإن لم يمر مالُها بالمنصة
            (القسم 9): الكشفُ يقيس الدخل لا ما دخل الحساب. أما «متى» فيومُ
            الدولة بمِنطقتها المخزَّنة، لا يومُ الخادم.
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
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-16 border border-line bg-surface p-18">
      <div className="text-12 text-muted">{label}</div>
      <div className="mt-6 text-26 font-bold text-ink">{value}</div>
      <div className="mt-6 text-11 leading-note text-muted">{hint}</div>
    </div>
  );
}

/** أعمدةُ الإيراد — `DESIGN.md` §3.4: بلا شبكةٍ ولا محورٍ ولا مفتاح.
 *
 * الارتفاعُ نسبةٌ من الأقصى، وآخرُ عمودٍ بلون `--tx` وغيرُه `--brd`.
 */
function RevenueBars({ data }: { data: Reports }) {
  const days = data.revenue_by_day;
  if (days.length === 0) {
    return (
      <p className="py-24 text-center text-12.5 text-muted">
        لا رحلاتٍ مكتملة في هذه الفترة.
      </p>
    );
  }

  // الأقصى للنسبة وحدها — قسمةُ عرضٍ لا حسابُ مال، فلا يمر مبلغٌ بها إلى شاشة
  const peak = Math.max(...days.map((row) => Number(row.revenue)), 1);

  // بلا ارتفاعٍ ثابت للحاوية: أطولُ عمودٍ 140px وفوقه قيمةٌ وتحته يوم، فيخرج
  // الارتفاعُ الطبيعي ١٩٠ كما في §3.4 — ورقمٌ ثابتٌ معها يقصّ التسميات
  return (
    <div className="flex items-end gap-7">
      {days.map((row, index) => (
        <div key={row.day} className="flex flex-1 flex-col items-center gap-6">
          {/* **قيمةُ اليوم الصفري لا تُكتب**: نافذةُ الشهر ثلاثون عموداً،
              وكتابةُ «٠.٠٠٠» فوق تسعةٍ وعشرين منها ضجيجٌ يخفي الرقم الوحيد
              الذي يُقرأ. والعمودُ الصفري نفسه يبقى — الفجوةُ معلومة */}
          <span className="text-9 text-muted">
            {Number(row.revenue) > 0 ? digits(row.revenue) : ""}
          </span>
          <span
            className={cn(
              "w-full rounded-t-5",
              index === days.length - 1 ? "bg-ink" : "bg-line",
            )}
            style={{ height: `${(Number(row.revenue) / peak) * 140}px` }}
          />
          <span className="text-9 text-muted">{shortDay(row.day)}</span>
        </div>
      ))}
    </div>
  );
}
