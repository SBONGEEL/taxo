/** **«الملخّصات المالية»** — A37–A39 (`design/TAXO2-DESIGN-REQUESTS.md` §٧، SPEC §٦٥-د) — **صفحةُ قراءةٍ وحدَها**.
 *
 * **لوحاتُ A37–A39 لم تُرسم بعد**، فتُبنى من عُدّة اللوحة القائمة (بطاقاتُ «التقارير»، وجدولُها، وحبّاتُها، وسطورُ الحال)
 * **وتُطابَق اللوحاتِ حين تصل**. **وما فيها كلُّه من الطلب نفسِه**: شريطُ المرشِّحات، وشريطُ المطابقة بحاليه، ومجموعاتُ البطاقات
 * بأرقامها وأعدادها، وما وراء كلِّ بطاقةٍ بتبويبيه، وصفحةُ المنع، وسطرُ التدقيق.
 *
 * **ولا زرَّ هنا يحرّك مالاً** (القاعدةُ ١): الأزرارُ فتحٌ وتصديرٌ وتنقّل. **ولا حسابَ مالٍ في الشاشة** (§14 و`check:money-math`):
 * كلُّ مبلغٍ وعددٍ ونسبةٍ نزل محسوباً — **حتى مجموعُ البطاقة ومن وراءها من استعلامٍ واحدٍ في الخلفية** فلا يفترقان.
 *
 * **والمنعُ من الخادم لا من الدور**: ٤٠٣ ⇒ صفحةُ «تحتاج الصلاحية». **والمرشِّحُ الذي لا ينطبق على بطاقةٍ يُقال**: «لا ينطبق» بعلّته
 * كما أرسلتها الخلفية — **لا صفرٌ يُقرأ «لا عمولةَ على الكاش»**.
 */

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { exportFinance, getFinanceSummary, getFinanceTransactions, getFinanceUsers } from "@/api/endpoints";
import type {
  CountryCode,
  Currency,
  FinanceGroup,
  FinanceMethod,
  FinanceMetric,
  FinancePeriod,
  FinanceQuery,
  FinanceReconciliation,
  FinanceStatus,
  FinanceSummary,
  FinanceTransactionsPage,
  FinanceUserType,
  FinanceUsersPage,
  FinanceView,
} from "@/api/types";
import { OpenProfile } from "@/components/profile/OpenProfile";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { useCountry } from "@/lib/country";
import { moment, money } from "@/lib/format";
import { cn, digits } from "@/lib/utils";
import { DateField, Icon } from "@/taxo2";

const PERIOD_LABEL: Record<FinancePeriod, string> = {
  today: "اليوم",
  week: "الأسبوع",
  month: "الشهر",
  custom: "مخصَّصة",
};

const USER_TYPE_LABEL: Record<FinanceUserType, string> = {
  rider: "راكب",
  driver: "كبتن",
};

const METHOD_LABEL: Record<FinanceMethod, string> = {
  cash: "كاش",
  cliq: "كليك",
  card: "بطاقة",
  wallet: "محفظة",
};

const STATUS_LABEL: Record<FinanceStatus, string> = {
  confirmed: "مؤكَّد",
  unconfirmed: "غيرُ مؤكَّد",
  disputed: "متنازَعٌ عليه",
};

/** **سطرُ التدقيق بنصِّ A39** — ثابتٌ في أسفل الصفحة وما وراء البطاقة: من يقرأ يعرف أن قراءتَه تُكتب. */
const AUDIT_LINE = "فتحُك هذه الصفحة وكلُّ تصديرٍ يُسجَّلان باسمك";

/** صفحةُ ما وراء البطاقة — خمسون صفّاً، **والعددُ الكاملُ من الخلفية** (`total`) فلا يُخمَّن آخرُ صفحة. */
const PAGE = 50;

type Tab = Exclude<FinanceView, "summary">;

interface Filters {
  period: FinancePeriod;
  from: string;
  to: string;
  userType: FinanceUserType | "all";
  method: FinanceMethod | "all";
  status: FinanceStatus | "all";
}

const INITIAL: Filters = { period: "month", from: "", to: "", userType: "all", method: "all", status: "all" };

/** **ما يُرسل** — والفترةُ المخصَّصةُ بلا تاريخيها لا تُرسل أصلاً (`null`): الخادمُ يردّها ٤٢٢، والشاشةُ تطلب التاريخين أوّلاً. */
function queryOf(country: CountryCode, filters: Filters): FinanceQuery | null {
  if (filters.period === "custom" && (!filters.from || !filters.to)) return null;
  return {
    country_code: country,
    period: filters.period,
    from_date: filters.period === "custom" ? filters.from : undefined,
    to_date: filters.period === "custom" ? filters.to : undefined,
    user_type: filters.userType === "all" ? undefined : filters.userType,
    method: filters.method === "all" ? undefined : filters.method,
    status: filters.status === "all" ? undefined : filters.status,
  };
}

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

export function FinanceSummaryScreen() {
  // **السوقُ من مبدّل الرأس** — واحدٌ في كلِّ مرّة، والعملةُ تتبعه من الخلفية
  const { country } = useCountry();
  const [filters, setFilters] = useState<Filters>(INITIAL);
  const [data, setData] = useState<FinanceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  const [open, setOpen] = useState<FinanceMetric | null>(null);
  const [exporting, setExporting] = useState(false);
  const query = useMemo(() => queryOf(country, filters), [country, filters]);

  useEffect(() => {
    setData(null);
    setError(null);
    if (!query) return;
    let alive = true;
    getFinanceSummary(query)
      .then((body) => {
        if (alive) setData(body);
      })
      .catch((caught) => {
        if (!alive) return;
        if (caught instanceof ApiError && caught.status === 403) setDenied(true);
        else setError(messageOf(caught, "تعذّر قراءة الملخّصات"));
      });
    return () => {
      alive = false;
    };
  }, [query]);

  async function download(view: FinanceView, metric?: string) {
    if (!query) return;
    setExporting(true);
    setError(null);
    try {
      await exportFinance(query, view, metric);
    } catch (caught) {
      setError(messageOf(caught, "تعذّر تصديرُ الملفّ"));
    } finally {
      setExporting(false);
    }
  }

  if (denied) {
    return (
      <Shell title="الملخّصات المالية">
        <Denied />
      </Shell>
    );
  }

  const currency = data?.window.currency;

  return (
    <Shell
      title="الملخّصات المالية"
      subtitle="من الدفتر وجداول المال مباشرةً — قراءةٌ وحدَها"
      actions={
        open ? null : (
          <Button size="sm" variant="secondary" loading={exporting} disabled={!data} onClick={() => void download("summary")}>
            تصدير Excel
          </Button>
        )
      }
    >
      <FilterBar filters={filters} onChange={setFilters} />
      <ErrorNote message={error} />

      {query === null ? (
        <p className="mt-18 text-12.5 text-muted">اختر تاريخَي البداية والنهاية — بيوم السوق.</p>
      ) : data === null ? (
        error ? null : <Spinner className="mx-auto my-38" />
      ) : (
        <>
          <ReconciliationStrip
            value={data.reconciliation}
            currency={data.window.currency}
            timeZone={data.window.timezone}
          />
          <WindowLine data={data} />
          {open ? (
            <DrillDown
              metric={open}
              query={query}
              currency={data.window.currency}
              timeZone={data.window.timezone}
              filters={filters}
              onFilters={setFilters}
              onBack={() => setOpen(null)}
              onExport={(view) => void download(view, open.key)}
              exporting={exporting}
            />
          ) : (
            data.groups.map((group) =>
              group.layout === "table" ? (
                <LedgerTable key={group.key} group={group} currency={data.window.currency} onOpen={setOpen} />
              ) : (
                <GroupCards key={group.key} group={group} currency={data.window.currency} onOpen={setOpen} />
              ),
            )
          )}
        </>
      )}

      <p className="mt-22 text-11.5 text-muted">
        <Icon name="history" /> {AUDIT_LINE}
        {currency ? ` · كلُّ رقمٍ بعملة السوق (${currency}) — لا يُجمع سوقان` : ""}
      </p>
    </Shell>
  );
}

/** **A39 — صفحةُ المنع**: بنصِّ الطلب، **ومعها من يمنح** فلا يبقى المشرفُ أمام بابٍ لا يعرف مفتاحَه. */
function Denied() {
  return (
    <div className="ad-banner" role="alert">
      <Icon name="lock" fill />
      <div>
        <p className="ad-banner-title">هذه الصفحة تحتاج صلاحية الملخّصات المالية — يمنحها مشرفُ الصلاحيات</p>
        <p className="ad-banner-body">
          لا تُعطى لأحدٍ افتراضاً ولا للمشرف الكامل، وتُمنح بالاسم من «المستخدمون والصلاحيات». {AUDIT_LINE}.
        </p>
      </div>
    </div>
  );
}

/** **شريطُ المرشِّحات ثابتٌ أعلى المحتوى** (A37): الفترةُ مبدّلٌ واحد، **والمخصَّصةُ بتاريخين**، ثمّ نوعُ المستخدم والطريقةُ والحال
 *  حبّاتٍ «الكلّ» أوّلُها. **والسوقُ ليس هنا**: مبدّلُ الرأس يحكمه لكلِّ شاشة. */
function FilterBar({ filters, onChange }: { filters: Filters; onChange: (next: Filters) => void }) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <div className="sticky top-header z-10 mb-14 flex flex-col gap-10 bg-bg py-10">
      <div className="flex flex-wrap items-center gap-12">
        <Segmented
          label="الفترة"
          value={filters.period}
          options={(Object.keys(PERIOD_LABEL) as FinancePeriod[]).map((key) => ({ key, label: PERIOD_LABEL[key] }))}
          onPick={(period) => set({ period })}
        />
        {filters.period === "custom" ? (
          <span className="flex flex-wrap items-center gap-8">
            <DateField label="من" value={filters.from} max={filters.to || undefined} onChange={(from) => set({ from })} hint="من تاريخ" />
            <DateField label="إلى" value={filters.to} min={filters.from || undefined} onChange={(to) => set({ to })} hint="إلى تاريخ" />
          </span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-12">
        <FilterGroup label="المستخدم">
          <Pills
            value={filters.userType}
            options={[
              { key: "all", label: "الكلّ" },
              ...(Object.keys(USER_TYPE_LABEL) as FinanceUserType[]).map((key) => ({ key, label: USER_TYPE_LABEL[key] })),
            ]}
            onPick={(userType) => set({ userType })}
          />
        </FilterGroup>
        <FilterGroup label="الطريقة">
          <Pills
            value={filters.method}
            options={[
              { key: "all", label: "الكلّ" },
              ...(Object.keys(METHOD_LABEL) as FinanceMethod[]).map((key) => ({ key, label: METHOD_LABEL[key] })),
            ]}
            onPick={(method) => set({ method })}
          />
        </FilterGroup>
        <FilterGroup label="الحال">
          <Pills
            value={filters.status}
            options={[
              { key: "all", label: "الكلّ" },
              ...(Object.keys(STATUS_LABEL) as FinanceStatus[]).map((key) => ({ key, label: STATUS_LABEL[key] })),
            ]}
            onPick={(status) => set({ status })}
          />
        </FilterGroup>
      </div>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-8">
      <span className="text-11.5 text-muted">{label}</span>
      {children}
    </span>
  );
}

/** **شريطُ المطابقة — حالان** (A37): سطرٌ أخضرُ هادئ، **أو شريطٌ أحمرُ واضحٌ بالفرق الأوّل وزرّ «التفاصيل»** — والفروقُ كلُّها من
 *  الخلفية (`differences`)، **فلا يُطرح رقمٌ من رقمٍ هنا**. **ووقتُ الفحص بمِنطقة السوق** كحدود الفترة تحته. */
function ReconciliationStrip({
  value,
  currency,
  timeZone,
}: {
  value: FinanceReconciliation;
  currency: Currency;
  timeZone: string;
}) {
  const [details, setDetails] = useState(false);
  if (value.reconciled) {
    return (
      <div className="ad-note ok" role="status">
        <Icon name="check_circle" fill />
        <span>
          المجاميعُ تطابق الدفتر — آخرُ فحص {digits(moment(value.checked_at, timeZone))} · {digits(String(value.checks))} فحصاً
        </span>
      </div>
    );
  }
  const first = value.differences[0];
  return (
    <div className="ad-note danger" role="alert">
      <Icon name="error" fill />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-8">
          <b>
            المجاميعُ لا تطابق الدفتر — الفرق {first ? money(first.difference_amount, currency) : ""} في {first?.label}
          </b>
          <Button size="sm" variant="secondary" onClick={() => setDetails((now) => !now)}>
            {details ? "إخفاء" : "التفاصيل"}
          </Button>
        </div>
        {details ? (
          <ul className="ad-mini mt-8">
            {value.differences.map((item) => (
              <li key={item.key}>
                <span className="ad-mini-row">
                  <span className="ad-mini-main">
                    <span className="ad-mini-title">{item.label}</span>
                    <span className="ad-mini-at">
                      الصفحة {money(item.page_amount, currency)} · الدفتر {money(item.ledger_amount, currency)}
                    </span>
                  </span>
                  <span className="ad-mini-value">{money(item.difference_amount, currency)}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

/** **حدّا الفترة بيوم السوق** كما حسبهما الخادم — **ويُكتبان بمِنطقته** (`window.timezone`) لا بمِنطقة المتصفّح: ليبيا من
 *  متصفّحٍ في عمّان كانت تبدأ «اليوم» الساعةَ 01:00 تحت عنوان `Africa/Tripoli`. */
function WindowLine({ data }: { data: FinanceSummary }) {
  const zone = data.window.timezone;
  return (
    <p className="mt-10 text-11.5 text-muted">
      {PERIOD_LABEL[data.window.period]}: من {digits(moment(data.window.from_at, zone))} إلى{" "}
      {digits(moment(data.window.to_at, zone))} ·{" "}
      {data.window.timezone} — والأرصدةُ «الآن» لا تتبع الفترة
    </p>
  );
}

/** **التعريفُ كما نشرته الخلفية** — وما بين علامتَي `…` اسمُ جدولٍ أو عمودٍ يُرسم خطَّ شيفرة. */
function Definition({ text }: { text: string }) {
  return (
    <>
      {text.split("`").map((part, index) =>
        index % 2 === 1 ? (
          <code key={index} dir="ltr" className="font-mono text-10.5 text-ink">
            {part}
          </code>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

function GroupCards({
  group,
  currency,
  onOpen,
}: {
  group: FinanceGroup;
  currency: Currency;
  onOpen: (metric: FinanceMetric) => void;
}) {
  return (
    <section className="mt-18">
      <h2 className="mb-12 text-14 font-bold text-ink">{group.title}</h2>
      <div className="grid gap-14 md:grid-cols-2 xl:grid-cols-4">
        {group.metrics.map((metric) => (
          <MetricCard key={metric.key} metric={metric} currency={currency} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}

/** **بطاقةُ مجموع** (A37): الرقمُ الكبيرُ بعملته · عددٌ صغيرٌ تحته · «افتح». **والمخزونُ يقول إنه رصيدٌ الآن**، **و«فوق السقف»
 *  بشارة تحذير** متى كان فيه أحد. **والتعريفُ تحتها** لمن سأل «من أين هذا الرقم؟». */
function MetricCard({
  metric,
  currency,
  onOpen,
}: {
  metric: FinanceMetric;
  currency: Currency;
  onOpen: (metric: FinanceMetric) => void;
}) {
  const alarming = metric.warn && metric.applicable && metric.users > 0;
  return (
    <div className="flex flex-col rounded-16 border border-line bg-surface p-18">
      <div className="flex items-center justify-between gap-8">
        <span className="text-12 text-muted">{metric.label}</span>
        <span className="flex flex-wrap gap-6">
          {alarming ? <Badge tone="danger">تحذير</Badge> : null}
          {metric.stock ? <Badge tone="muted">رصيدٌ الآن</Badge> : null}
        </span>
      </div>
      {metric.applicable ? (
        <>
          <div className={cn("mt-6 text-26 font-bold", alarming ? "text-danger" : "text-ink")}>
            {money(metric.amount, currency)}
          </div>
          <div className="mt-4 text-11.5 text-muted">
            {digits(String(metric.stock ? metric.users : metric.count))} {metric.unit}
          </div>
          {metric.breakdown.length > 0 ? (
            <ul className="ad-mini mt-8">
              {metric.breakdown.map((line) => (
                <li key={line.key}>
                  <span className="ad-mini-row">
                    <span className="ad-mini-main">
                      <span className="ad-mini-title">{line.label}</span>
                      <span className="ad-mini-at">{digits(String(line.count))}</span>
                    </span>
                    <span className="ad-mini-value">{money(line.amount, currency)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <>
          <div className="mt-6 text-26 font-bold text-muted">—</div>
          <div className="mt-4 text-11.5 text-muted">لا ينطبق: {metric.reason}</div>
        </>
      )}
      <details className="mt-10 text-11 leading-note text-muted">
        <summary className="cursor-pointer">من أين هذا الرقم؟</summary>
        <p className="mt-6">
          <Definition text={metric.definition} />
        </p>
      </details>
      <div className="mt-auto pt-12">
        <Button size="sm" variant="secondary" disabled={!metric.applicable} onClick={() => onOpen(metric)}>
          افتح
          <Icon name="chevron_left" />
        </Button>
      </div>
    </div>
  );
}

/** **حركةُ الدفتر بالنوع** — ثلاثون نوعاً لا تُقرأ بطاقات، فجدولٌ مضغوط. **وكلُّ سطرٍ تقابله المطابقةُ بالدفتر الخام.** */
function LedgerTable({
  group,
  currency,
  onOpen,
}: {
  group: FinanceGroup;
  currency: Currency;
  onOpen: (metric: FinanceMetric) => void;
}) {
  return (
    <section className="mt-22">
      <h2 className="mb-4 text-14 font-bold text-ink">{group.title}</h2>
      <p className="mb-12 text-11.5 text-muted">كلُّ نوعِ قيدٍ في الفترة بإشارته — الموجبُ دخل محفظةً، والسالبُ خرج منها.</p>
      <Table
        height="auto"
        columns="1.6fr 1fr .6fr auto"
        headers={["النوع", "المبلغ", "القيود", ""]}
        rows={group.metrics}
        keyOf={(metric) => metric.key}
        empty={{ title: "لا قيود", hint: "لا قيدَ في الدفتر لهذا السوق في الفترة." }}
        render={(metric) => (
          <>
            <span className="min-w-0 truncate text-ink">{metric.label}</span>
            <span className="text-ink">{metric.applicable ? money(metric.amount, currency) : "—"}</span>
            <span className="text-muted">{metric.applicable ? digits(String(metric.count)) : "—"}</span>
            <span className="ad-row-end">
              <Button size="sm" variant="ghost" disabled={!metric.applicable || metric.count === 0} onClick={() => onOpen(metric)}>
                افتح
              </Button>
            </span>
          </>
        )}
      />
    </section>
  );
}

/** **A38 — ما وراء البطاقة**: اسمُ المجموع ورقمُه، **والمرشِّحاتُ شاراتٌ تُزال**، وتبويبان («المستخدمون» · «المعاملات»)، وترقيمٌ،
 *  وتصديرُ التبويب القائم. **والصفُّ يفتح صاحبَه في صفحته القائمة** (`OpenProfile`). */
function DrillDown({
  metric,
  query,
  currency,
  timeZone,
  filters,
  onFilters,
  onBack,
  onExport,
  exporting,
}: {
  metric: FinanceMetric;
  query: FinanceQuery;
  currency: Currency;
  /** **مِنطقةُ السوق** — وقتُ كلِّ معاملةٍ بها، كما يكتبه الملفُّ المصدَّر */
  timeZone: string;
  filters: Filters;
  onFilters: (next: Filters) => void;
  onBack: () => void;
  onExport: (view: Tab) => void;
  exporting: boolean;
}) {
  const [tab, setTab] = useState<Tab>("users");
  const [page, setPage] = useState(0);
  const [users, setUsers] = useState<FinanceUsersPage | null>(null);
  const [lines, setLines] = useState<FinanceTransactionsPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(0);
  }, [tab, query, metric.key]);

  useEffect(() => {
    let alive = true;
    setError(null);
    setUsers(null);
    setLines(null);
    const reader =
      tab === "users"
        ? getFinanceUsers(metric.key, query, PAGE, page * PAGE).then((body) => alive && setUsers(body))
        : getFinanceTransactions(metric.key, query, PAGE, page * PAGE).then((body) => alive && setLines(body));
    reader.catch((caught) => {
      if (alive) setError(messageOf(caught, "تعذّر قراءة ما وراء المجموع"));
    });
    return () => {
      alive = false;
    };
  }, [tab, page, query, metric.key]);

  const current = tab === "users" ? users : lines;
  const shown = current?.metric ?? metric;
  const total = current?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  // **المرشِّحاتُ القائمةُ شاراتٍ تُزال** — والفترةُ لا تُزال: لكلِّ رقمٍ فترة
  const chips: { key: string; label: string; clear?: () => void }[] = [
    { key: "period", label: PERIOD_LABEL[filters.period] },
  ];
  if (filters.userType !== "all") {
    chips.push({ key: "user", label: USER_TYPE_LABEL[filters.userType], clear: () => onFilters({ ...filters, userType: "all" }) });
  }
  if (filters.method !== "all") {
    chips.push({ key: "method", label: METHOD_LABEL[filters.method], clear: () => onFilters({ ...filters, method: "all" }) });
  }
  if (filters.status !== "all") {
    chips.push({ key: "status", label: STATUS_LABEL[filters.status], clear: () => onFilters({ ...filters, status: "all" }) });
  }

  return (
    <section className="mt-18">
      <div className="flex flex-wrap items-start justify-between gap-12">
        <div className="min-w-0">
          <Button size="sm" variant="ghost" onClick={onBack}>
            <Icon name="arrow_forward" />
            كلُّ المجاميع
          </Button>
          <h2 className="mt-8 text-16 font-bold text-ink">{shown.label}</h2>
          <div className="mt-4 text-26 font-bold text-ink">
            {shown.applicable ? money(shown.amount, currency) : "—"}
          </div>
          <div className="ad-chips mt-8">
            {chips.map((chip) => (
              <Badge key={chip.key} tone="muted">
                {chip.label}
                {chip.clear ? (
                  <button type="button" className="ms-4" aria-label={`أزل مرشِّح ${chip.label}`} onClick={chip.clear}>
                    <Icon name="close" />
                  </button>
                ) : null}
              </Badge>
            ))}
          </div>
        </div>
        <Button size="sm" variant="secondary" loading={exporting} onClick={() => onExport(tab)}>
          تصدير Excel
        </Button>
      </div>

      <div className="mt-14">
        <Segmented
          label="ما وراء المجموع"
          value={tab}
          options={[
            { key: "users", label: "المستخدمون" },
            { key: "transactions", label: "المعاملات" },
          ]}
          onPick={setTab}
        />
      </div>
      <ErrorNote message={error} />
      {!shown.applicable ? <p className="mt-12 text-12.5 text-muted">لا ينطبق: {shown.reason}</p> : null}

      <div className="mt-12">
        {tab === "users" ? (
          <Table
            height="auto"
            columns="1.6fr .8fr .8fr 1fr auto"
            headers={["الاسم", "الدور", "المعاملات", "المجموع", ""]}
            rows={users ? users.rows : null}
            // **الحسابُ بدوره** — حاملُ الدورين سطران (راكبٌ وكبتن) بمعرّفٍ واحد، فالمفتاحُ يحمل الدورَ أيضاً
            keyOf={(row) => `${row.role}-${row.user_id ?? row.name ?? "—"}`}
            empty={{ title: "لا معاملات في هذه الفترة", hint: "بدّل الفترة أو المرشِّحات من الشريط أعلاه." }}
            render={(row) => (
              <>
                <span className="ad-reason">
                  <span className="ad-reason-main">{row.name ?? "—"}</span>
                  {row.phone_masked ? (
                    <span className="ad-reason-sub" dir="ltr">
                      {row.phone_masked}
                    </span>
                  ) : null}
                </span>
                <span className="text-muted">{row.role_label}</span>
                <span className="text-muted">{digits(String(row.count))}</span>
                <span className="text-ink">{money(row.amount, currency)}</span>
                <span className="ad-row-end">
                  <Profile role={row.role} userId={row.user_id} driverId={row.driver_id} name={row.name} />
                </span>
              </>
            )}
          />
        ) : (
          <Table
            height="auto"
            columns=".9fr 1.3fr 1.1fr .7fr .9fr .9fr auto"
            headers={["التاريخ", "المستخدم", "النوع", "الطريقة", "المبلغ", "الحال", ""]}
            rows={lines ? lines.rows : null}
            keyOf={(row) => `${row.source}-${row.ref_id}`}
            empty={{ title: "لا معاملات في هذه الفترة", hint: "بدّل الفترة أو المرشِّحات من الشريط أعلاه." }}
            render={(row) => (
              <>
                <span className="text-muted">{digits(moment(row.occurred_at, timeZone))}</span>
                <span className="ad-reason">
                  <span className="ad-reason-main">{row.name ?? "—"}</span>
                  <span className="ad-reason-sub">{row.role_label}</span>
                </span>
                <span className="ad-reason">
                  <span className="ad-reason-main">{row.kind_label}</span>
                  {row.ride_id ? (
                    <span className="ad-reason-sub" dir="ltr" title={row.ride_id}>
                      رحلة {row.ride_id.slice(0, 8)}
                    </span>
                  ) : null}
                </span>
                <span className="text-muted">{row.method_label ?? "—"}</span>
                <span className="text-ink">{money(row.amount, currency)}</span>
                <span className="text-muted">{row.status_label ?? "—"}</span>
                <span className="ad-row-end">
                  <Profile role={row.role} userId={row.user_id} driverId={row.driver_id} name={row.name} />
                </span>
              </>
            )}
          />
        )}
      </div>

      {current && total > PAGE ? (
        <div className="mt-12 flex flex-wrap items-center justify-between gap-8 text-11.5 text-muted">
          <span>
            صفحة {digits(String(page + 1))} من {digits(String(pages))} · {digits(String(total))} صفّاً
          </span>
          <span className="flex gap-8">
            <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((now) => now - 1)}>
              السابقة
            </Button>
            <Button size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => setPage((now) => now + 1)}>
              التالية
            </Button>
          </span>
        </div>
      ) : null}
    </section>
  );
}

/** **صاحبُ الصفّ في صفحته القائمة** — الكبتنُ بـ`drivers.id` والراكبُ بـ`users.id`، ولا يُخلطان (`OpenProfile`). */
function Profile({
  role,
  userId,
  driverId,
  name,
}: {
  role: FinanceUserType;
  userId: string | null;
  driverId: string | null;
  name: string | null;
}) {
  if (role === "driver" && driverId) return <OpenProfile kind="driver" id={driverId} search={name} />;
  if (userId) return <OpenProfile kind="rider" id={userId} />;
  return null;
}
