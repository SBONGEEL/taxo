/** قسمُ «الإحصاءات» — زياراتُ الموقع وتحميلاتُه وأرقامُ Google Play (أمرُ المالك ٢٠٢٦-١١-٠٤، `design/SITE-STATS.md`)، بصلاحيّة `stats.view`.
 *
 * **الأرقامُ كلُّها من الخلفيّة مجمَّعةً** (قاعدةُ «التجميعُ في الخلفيّة»): الشاشةُ تعرض ولا تجمع. **ولا رقمَ قبل يوم البناء** — «منذ» تحت كلِّ
 * لوحٍ يقول متى بدأ العدّ، فلا يُقرأ صفرُ أمسِ غيابَ زوّار. **ولا IP ولا كوكي** في المصدر أصلاً، فلا شيءَ هنا يُعرّف أحداً.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { importPlayStats, siteStatsReport } from "@/api/endpoints";
import type { SiteStatsReport, StatsApp, StatsWindow } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { useFormError } from "@/lib/form-errors";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";

const APPS: { key: StatsApp; label: string }[] = [
  { key: "rider", label: "تطبيق الراكب" },
  { key: "driver", label: "تطبيق الكبتن" },
];

const WINDOWS: { key: StatsWindow; label: string }[] = [
  { key: "today", label: "اليوم" },
  { key: "week", label: "الأسبوع" },
  { key: "month", label: "الشهر" },
  { key: "all", label: "الكلّ" },
];

const SOURCES: Record<string, string> = { facebook: "فيسبوك", google: "Google", direct: "مباشر", other: "أخرى" };

/** أسماءُ البلدان بالعربيّة لما يغلب على الزوّار — وغيرُها برمزه كما هو. */
const COUNTRIES: Record<string, string> = {
  JO: "الأردن", DZ: "الجزائر", LY: "ليبيا", SA: "السعودية", AE: "الإمارات", EG: "مصر", MA: "المغرب", TN: "تونس", FR: "فرنسا", US: "أمريكا", "??": "غير معروف",
};

type Range = 30 | 90;

function count(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : digits(value.toLocaleString(DISPLAY_LOCALE));
}

function day(iso: string | null): string {
  if (!iso) return "—";
  return digits(new Date(`${iso}T12:00:00Z`).toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "short", year: "numeric" }));
}

function Since({ iso }: { iso: string | null }) {
  return <p className="st-since">{iso ? `العدُّ منذ ${day(iso)}` : "لم يُعدَّ شيءٌ بعد"}</p>;
}

/** أعمدةٌ يوميّةٌ بسيطة — الارتفاعُ نسبةٌ من أكبر يوم، والرقمُ في التلميح. */
function Bars({ rows }: { rows: { day: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) return <p className="st-empty">لا أيّامَ بعد.</p>;
  return (
    <div className="st-bars" role="img" aria-label="رسمٌ يوميّ">
      {rows.map((r) => (
        <span key={r.day} className="st-bar" title={`${day(r.day)}: ${digits(String(r.value))}`}>
          <i style={{ height: `${Math.max(2, (r.value / max) * 100)}%` }} />
        </span>
      ))}
    </div>
  );
}

function Ranked({ title, rows, name }: { title: string; rows: { key: string; count: number }[]; name?: (key: string) => string }) {
  return (
    <div className="st-ranked">
      <strong>{title}</strong>
      {rows.length === 0 && <p className="st-empty">لا شيءَ بعد.</p>}
      {rows.map((r) => (
        <div key={r.key} className="st-row">
          <span dir="auto">{name ? name(r.key) : r.key}</span>
          <span>{count(r.count)}</span>
        </div>
      ))}
    </div>
  );
}

export function SiteStatsScreen() {
  const [range, setRange] = useState<Range>(30);
  const [data, setData] = useState<SiteStatsReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const form = useFormError();

  const load = useCallback(async () => {
    form.clear();
    try {
      setData(await siteStatsReport(range));
    } catch (caught) {
      form.capture(caught, "تعذّرت قراءة الإحصاءات");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range]);

  useEffect(() => {
    void load();
  }, [load]);

  async function importNow() {
    setBusy(true);
    setDone(null);
    form.clear();
    try {
      const result = await importPlayStats();
      setDone(digits(`استُورد تقريرُ Play — ${result.rows} صفّاً`));
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر استيرادُ تقرير Play");
    } finally {
      setBusy(false);
    }
  }

  const downloads = useMemo(() => {
    const byApp: Record<StatsApp, { day: string; value: number }[]> = { rider: [], driver: [] };
    const clicks: Record<StatsApp, number> = { rider: 0, driver: 0 };
    for (const row of data?.downloads_daily ?? []) {
      byApp[row.app].push({ day: row.day, value: row.downloads });
      clicks[row.app] += row.clicks;
    }
    return { byApp, clicks };
  }, [data]);

  const play = useMemo(() => {
    const byApp: Record<StatsApp, { day: string; value: number }[]> = { rider: [], driver: [] };
    const totals: Record<StatsApp, { installs: number; uninstalls: number; active: number }> = {
      rider: { installs: 0, uninstalls: 0, active: 0 },
      driver: { installs: 0, uninstalls: 0, active: 0 },
    };
    for (const row of data?.play_daily ?? []) {
      byApp[row.app].push({ day: row.day, value: row.installs });
      totals[row.app].installs += row.installs;
      totals[row.app].uninstalls += row.uninstalls;
      // الأجهزةُ النشطةُ لقطةُ يومٍ لا مجموع — آخرُ يومٍ مقروء
      totals[row.app].active = row.active_devices;
    }
    return { byApp, totals };
  }, [data]);

  const country = (key: string) => COUNTRIES[key] ?? key;
  const lastImport = data?.play_last_import ?? null;

  return (
    <Shell
      title="الإحصاءات"
      subtitle="زياراتُ الموقع وتحميلاتُه وأرقامُ Google Play — أعدادٌ مجمَّعةٌ بلا IP ولا كوكي"
      actions={<Button size="sm" variant="secondary" loading={busy} onClick={importNow}>استيراد Play الآن</Button>}
    >
      <style>{CSS}</style>
      <Segmented
        label="المدّة"
        value={String(range)}
        onPick={(value) => setRange(Number(value) as Range)}
        options={[
          { key: "30", label: digits("آخر 30 يوماً") },
          { key: "90", label: digits("آخر 90 يوماً") },
        ]}
      />
      {done && <SuccessNote message={done} />}
      {form.message && <ErrorNote message={form.message} />}
      {!data && !form.message && <p>…</p>}
      {data && (
        <div className="st-wrap">
          <section className="ad-card st-panel">
            <strong>التحميلات — الموقع + Google Play</strong>
            <div className="st-table" role="table">
              <div className="st-tr st-th" role="row">
                <span role="columnheader" />
                {WINDOWS.map((w) => (
                  <span key={w.key} role="columnheader">{w.label}</span>
                ))}
              </div>
              {APPS.map((app) => (
                <div key={app.key} className="st-tr" role="row">
                  <span role="rowheader">{app.label}</span>
                  {WINDOWS.map((w) => {
                    const cell = data.summary[app.key]?.[w.key];
                    return (
                      <span key={w.key} role="cell" title={cell ? digits(`الموقع ${cell.site} · Play ${cell.play}`) : undefined}>
                        <b>{count(cell?.total)}</b>
                        {cell && <small>{digits(`موقع ${cell.site} · Play ${cell.play}`)}</small>}
                      </span>
                    );
                  })}
                </div>
              ))}
            </div>
          </section>

          <section className="ad-card st-panel">
            <strong>الموقع</strong>
            <div className="st-tiles">
              {WINDOWS.map((w) => (
                <div key={w.key} className="st-tile">
                  <span>{w.label}</span>
                  <b>{count(data.visits[w.key]?.views)}</b>
                  <small>{w.key === "all" ? "زيارة" : `زيارة · ${count(data.visits[w.key]?.uniques)} زائراً`}</small>
                </div>
              ))}
            </div>
            <Bars rows={data.site_daily.map((r) => ({ day: r.day, value: r.views }))} />
            <div className="st-cols">
              <Ranked title="أعلى الصفحات" rows={data.top_pages} />
              <Ranked title="المصادر" rows={data.top_sources} name={(k) => SOURCES[k] ?? k} />
              <Ranked title="البلدان" rows={data.site_countries} name={country} />
            </div>
            <Since iso={data.since.site} />
          </section>

          <section className="ad-card st-panel">
            <strong>تحميلاتُ الموقع</strong>
            <div className="st-cols">
              {APPS.map((app) => (
                <div key={app.key} className="st-ranked">
                  <strong>{app.label}</strong>
                  <Bars rows={downloads.byApp[app.key]} />
                  <p className="st-since">{digits(`ضغطاتُ الزرّ في المدّة: ${downloads.clicks[app.key]}`)} — والتحميلُ يُعدّ حين تُطلب الحزمةُ كاملة</p>
                </div>
              ))}
              <Ranked title="البلدان" rows={data.download_countries} name={country} />
            </div>
            <Since iso={data.since.downloads} />
          </section>

          <section className="ad-card st-panel">
            <strong>Google Play</strong>
            <p className="st-since">
              {lastImport
                ? digits(
                    `آخرُ استيراد: ${new Date(lastImport.ran_at).toLocaleString(DISPLAY_LOCALE)} — ${
                      lastImport.status === "ok" ? `${lastImport.rows} صفّاً` : "فشل"
                    }`,
                  )
                : "لم يُستورد تقريرٌ بعد"}
              {data.play_last_day ? ` · آخرُ يومٍ في التقرير ${day(data.play_last_day)}` : ""}
            </p>
            {lastImport?.error && <ErrorNote message={lastImport.error} />}
            <div className="st-cols">
              {APPS.map((app) => (
                <div key={app.key} className="st-ranked">
                  <strong>{app.label}</strong>
                  <Bars rows={play.byApp[app.key]} />
                  <div className="st-row"><span>تثبيت</span><span>{count(play.totals[app.key].installs)}</span></div>
                  <div className="st-row"><span>إلغاءُ تثبيت</span><span>{count(play.totals[app.key].uninstalls)}</span></div>
                  <div className="st-row"><span>أجهزةٌ نشطة (آخر يوم)</span><span>{count(play.totals[app.key].active)}</span></div>
                </div>
              ))}
              <Ranked title="البلدان" rows={data.play_countries} name={country} />
            </div>
            <p className="st-since">Play ينشر تقاريرَه متأخّرةً يوماً أو يومين — فاليومُ والأمسُ قد يبقيان صفراً حتى الاستيراد التالي.</p>
          </section>
          <section className="ad-card st-panel">
            <strong>محاولاتُ التسجيل في دولٍ غيرِ نشطة</strong>
            <p className="st-since">من ضغط «متابعة» في دولةٍ «قريباً» أو «متوقفة» في مُنتقي الهاتف — عددٌ لكلِّ دولةٍ في المدّة المختارة، بلا أيِّ رقم هاتف. حالُ كلِّ دولةٍ من «الدول والحدود».</p>
            <Ranked title="الدول" rows={data.signup_attempts} name={country} />
          </section>
        </div>
      )}
    </Shell>
  );
}

const CSS = `
.st-wrap{display:grid;gap:12px;margin-top:12px}
.st-panel{display:flex;flex-direction:column;gap:10px;padding:14px}
.st-table{display:grid;gap:6px;overflow-x:auto}
.st-tr{display:grid;grid-template-columns:minmax(110px,1.2fr) repeat(4,minmax(78px,1fr));gap:8px;align-items:start}
.st-th span{font-size:12px;opacity:.7}
.st-tr span{display:flex;flex-direction:column;gap:2px}
.st-tr b{font-size:20px}
.st-tr small,.st-tile small{font-size:11.5px;opacity:.7}
.st-tiles{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(130px,1fr))}
.st-tile{display:flex;flex-direction:column;gap:2px;padding:10px;border-radius:12px;background:var(--t2-bg,rgba(127,127,127,.08))}
.st-tile b{font-size:22px}
.st-bars{display:flex;align-items:flex-end;gap:2px;height:72px;direction:ltr}
.st-bar{flex:1;height:100%;display:flex;align-items:flex-end}
.st-bar i{display:block;width:100%;border-radius:3px 3px 0 0;background:var(--t2-brand,#f26b1d)}
.st-cols{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.st-ranked{display:flex;flex-direction:column;gap:6px}
.st-row{display:flex;justify-content:space-between;gap:8px;font-size:14px}
.st-since,.st-empty{font-size:12.5px;opacity:.7;margin:0}
`;
