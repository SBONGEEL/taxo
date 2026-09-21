/** شاشةُ الأعطال — **تُرتَّب بالمتأثّرين لا بالمرّات** (2026-09-20).
 *
 * **وهذا الافتراضُ هو الشاشةُ كلُّها**: حلقةُ رسمٍ في هاتفٍ واحدٍ تُنتج آلافَ
 * الأحداث، **فالترتيبُ بالمرّات يضعها فوق عطبٍ يمسّ نصفَ الأسطول**. والسؤالُ
 * الذي يُبنى عليه قرارٌ هو «كم إنساناً»، لا «كم مرّة».
 *
 * **وصفٌّ واحدٌ لكلِّ عطبٍ لا صفٌّ لكلِّ وقوع**: التجميعُ يقع في الخلفية
 * (`services/error_reports.fingerprint_of`)، وهذه تعرض ما جمّعته.
 *
 * ## ولمحةٌ فوق الجدول — **ثلاثةُ أسئلةٍ تُجاب بنظرة** (٢٠٢٦-٠٩-٢١)
 *
 * «ما الجديد» · «ما الذي يكبر» · «من أُصيب». **وجدولٌ وحدَه لا يجيبها**: يقول
 * ما وقع ولا يقول **أيتسارع أم يخبو**، ومن يفتح لوحةً كلَّ صباحٍ يحتاج الفرقَ
 * لا المجموع.
 *
 * **والأرقامُ كلُّها من الخلفية** (`services/error_stats.py`) — وهي قاعدةُ
 * `services/stats.py` نفسُها: **لوحةٌ تجمع صفوفَها بنفسها تكذب أوّلَ ما تُقصَّ
 * صفحة**، فتقول «٥٠ جهازاً» وهي تعني الخمسين المعروضين.
 *
 * ## والرسمُ الصغيرُ يقول الاتجاه، ولا يُقرأ عدداً
 *
 * **أعمدةٌ نسبيّةٌ إلى أعلى ساعةٍ في الصفِّ نفسِه** لا إلى الجدول كلِّه: كلُّ
 * صفٍّ يُقرأ بذاته — «أيتسارع هذا؟» لا «أهو أكبرُ من ذاك؟»، والثاني تجيبه
 * الأعمدةُ الرقميّة. **وساعةٌ صامتةٌ صفرٌ لا فجوة** (تُبنى في الخلفية).
 *
 * ## وما ليس في هذه الشاشة — بقصد
 *
 * **لا رقمَ هاتفٍ ولا حسابَ.** ما يصل الجدولَ مرّ بـ`core/scrub.py`، **فالشاشةُ
 * لا تملك ما تُخفيه** — وهذا أقوى من إخفاءٍ في الواجهة.
 *
 * > **⚠ واستثناءٌ مكتوبٌ لا مسكوتٌ عنه** (قِيس ٢٠٢٦-٠٩-٢١): **الإحداثيّةُ في
 * > نصٍّ حرٍّ لا تُحجب** — استقرّت في الجدول عاريةً، **وقرارُ المالك إبقاؤها**.
 * > فما فوق يصف الهاتفَ والبريدَ والمبلغَ والمُعرِّف، **ولا يُقاس عليه الموقع**.
 *
 * **والمُعرِّفُ الوحيدُ `device_hash`**: مُعمّىً مرّتين ولا يُوصَل بصاحبه.
 *
 * ## وتمييزُ إطارات المكتبات نُزع بعد أن قِيس (قرارُ المالك ٢٠٢٦-٠٩-٢١)
 *
 * **كان تلوينٌ يُخفِّت «إطارَ المكتبة»، فقِيست حزمةُ الإنتاج فلم يطابق شيئاً**:
 * الحزمُ `index-*` و`mapbox-*` و`web-*`، **ولا حزمةَ `vendor-*` وReact داخلَ
 * `index-*`**. **فكان يلوّن إطارَ mapbox على أنه إطارُنا** — وتمييزٌ يخطئ أسوأُ
 * من لا تمييز. **ولا سبيلَ صحيحاً بلا خرائطِ مصدر**، فنُزع وكُتب الحدُّ في
 * الشاشة.
 *
 * > **⚠ والفُتاتُ يُجمع منذ ٢٠٢٦-٠٩-٢١** (`lib/breadcrumbs.ts`) — وما سبقه من
 * > أحداثٍ لا فُتاتَ فيه بحقّ، ولا يُقرأ فراغُه «لم يقع شيءٌ قبل العطب».
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  bulkIgnoreErrors,
  bulkResolveErrors,
  getErrorGroup,
  getErrorSummary,
  getErrorTrend,
  ignoreErrorGroup,
  listErrorEvents,
  listErrorGroups,
  reopenErrorGroup,
  resolveErrorGroup,
} from "@/api/endpoints";
import type {
  ClientApp,
  ErrorEventRow,
  ErrorGroupDetail,
  ErrorGroupRow,
  ErrorSort,
  ErrorStatus,
  ErrorSummary,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Badge, type Tone } from "@/components/ui/Badge";
import { ErrorNote } from "@/components/ui/Feedback";
import { exactMoment, moment, sinceNow } from "@/lib/format";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { digits } from "@/lib/utils";

const APP_LABEL: Record<ClientApp, string> = {
  rider: "الراكب",
  driver: "الكبتن",
  panel: "اللوحة",
};

const STATUS_LABEL: Record<ErrorStatus, string> = {
  open: "مفتوح",
  resolved: "محسوم",
  ignored: "مكتوم",
};

const STATUS_TONE: Record<ErrorStatus, Tone> = {
  open: "danger",
  resolved: "ok",
  ignored: "muted",
};

/** **البابُ الذي دخل منه** — وأربعتُها تفشل أربعَ فشلاتٍ مختلفة. */
const KIND_LABEL: Record<string, string> = {
  error: "خطأ",
  rejection: "وعدٌ مرفوض",
  boundary: "حدُّ الشاشة",
  user_report: "بلاغُ مستخدم",
};

const KIND_TONE: Record<string, Tone> = {
  error: "danger",
  rejection: "muted",
  boundary: "danger",
  user_report: "warn",
};

/** **«جديد» حتى أربعٍ وعشرين ساعة** — بقدر نافذة اللمحة، فلا رقمان لمعنًى. */
const NEW_WINDOW_MS = 24 * 60 * 60 * 1000;

const PAGE = 50;
const TREND_HOURS = 24;

const COLUMNS = "34px 2.1fr 76px 96px 72px 76px 132px";

export function ErrorsScreen() {
  const [status, setStatus] = useState<ErrorStatus | "all">("open");
  const [app, setApp] = useState<ClientApp | "all">("all");
  const [sort, setSort] = useState<ErrorSort>("users");
  const [hours, setHours] = useState<number | "all">(24);
  const [page, setPage] = useState(0);

  const [rows, setRows] = useState<ErrorGroupRow[] | null>(null);
  const [summary, setSummary] = useState<ErrorSummary | null>(null);
  const [trend, setTrend] = useState<Record<string, number[]>>({});
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const [selected, setSelected] = useState<ErrorGroupDetail | null>(null);
  const [notes, setNotes] = useState<ErrorEventRow[]>([]);
  const [events, setEvents] = useState<ErrorEventRow[]>([]);
  const [shown, setShown] = useState<ErrorEventRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const search = useSearch();

  const load = useCallback(async () => {
    setRows(null);
    const found = await listErrorGroups({
      app: app === "all" ? undefined : app,
      status: status === "all" ? undefined : status,
      q: search.term,
      sort,
      hours: hours === "all" ? undefined : hours,
      limit: PAGE,
      offset: page * PAGE,
    });
    setRows(found);
    setPicked(new Set());
    // **المنحنى لما يُعرض وحدَه** — لا لكلِّ ما في القاعدة
    setTrend(
      Object.fromEntries(
        (await getErrorTrend(found.map((row) => row.id), TREND_HOURS)).map(
          (item) => [item.group_id, item.buckets],
        ),
      ),
    );
  }, [app, status, search.term, sort, hours, page]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الأعطال",
      ),
    );
  }, [load]);

  const loadSummary = useCallback(async () => {
    setSummary(await getErrorSummary());
  }, []);

  useEffect(() => {
    loadSummary().catch(() => setSummary(null));
  }, [loadSummary]);

  const open = async (id: string) => {
    setError(null);
    try {
      const detail = await getErrorGroup(id);
      setSelected(detail);
      const all = await listErrorEvents(id, false);
      setEvents(all);
      setShown(detail.latest ?? all[0] ?? null);
      setNotes(await listErrorEvents(id, true));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر فتح العطب");
    }
  };

  const act = async (
    action: (id: string) => Promise<ErrorGroupRow>,
    id: string,
  ) => {
    setError(null);
    try {
      await action(id);
      await load();
      await loadSummary();
      await open(id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  };

  const bulk = async (action: (ids: string[]) => Promise<ErrorGroupRow[]>) => {
    setError(null);
    try {
      await action([...picked]);
      await load();
      await loadSummary();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  };

  const toggle = (id: string) =>
    setPicked((was) => {
      const next = new Set(was);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const close = () => {
    setSelected(null);
    setNotes([]);
    setEvents([]);
    setShown(null);
  };

  const allPicked = !!rows?.length && picked.size === rows.length;

  return (
    <Shell
      title="الأعطال"
      subtitle="عطبٌ واحدٌ في صفٍّ واحدٍ مهما تكرّر — والترتيبُ بمن أصابهم لا بعدد المرّات"
    >
      <Summary data={summary} />

      <div className="mt-14">
        <Pills
          value={status}
          onPick={(key) => {
            setStatus(key);
            setPage(0);
          }}
          options={[
            { key: "open", label: "مفتوحة" },
            { key: "resolved", label: "محسومة" },
            { key: "ignored", label: "مكتومة" },
            { key: "all", label: "الكل" },
          ]}
        />
      </div>

      <div className="mt-8">
        <Pills
          value={app}
          onPick={(key) => {
            setApp(key);
            setPage(0);
          }}
          options={[
            { key: "all", label: "كل التطبيقات" },
            { key: "rider", label: "الراكب" },
            { key: "driver", label: "الكبتن" },
            { key: "panel", label: "اللوحة" },
          ]}
        />
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-12">
        <Pills
          value={String(hours)}
          onPick={(key) => {
            setHours(key === "all" ? "all" : Number(key));
            setPage(0);
          }}
          options={[
            { key: "1", label: "ساعة" },
            { key: "24", label: "24 ساعة" },
            { key: "168", label: "7 أيام" },
            { key: "720", label: "30 يوماً" },
            { key: "all", label: "الكل" },
          ]}
        />
        <label className="flex items-center gap-8 text-11.5 text-muted">
          الترتيب
          <select
            value={sort}
            onChange={(event) => {
              setSort(event.target.value as ErrorSort);
              setPage(0);
            }}
            className="rounded-12 border border-line bg-surface px-12 py-9 text-12 font-semibold text-ink"
          >
            <option value="users">الأكثر تأثيراً (المتأثرون)</option>
            <option value="events">الأكثر تكراراً</option>
            <option value="last_seen">آخر ظهور</option>
            <option value="first_seen">أول ظهور</option>
          </select>
        </label>
      </div>

      <div className="mt-12">
        <ErrorNote message={error} />
      </div>

      {picked.size ? (
        <div className="mb-10 flex flex-wrap items-center gap-10 rounded-13 border border-line bg-surface-2 p-12">
          <span className="text-12.5 font-semibold text-ink">
            حُدِّد {digits(picked.size)} من {digits(rows?.length ?? 0)}
          </span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => void bulk(bulkResolveErrors)}
            className="rounded-12 border border-line px-14 py-9 text-12 font-semibold text-ink"
          >
            حسمُ المحدَّد
          </button>
          <button
            type="button"
            onClick={() => void bulk(bulkIgnoreErrors)}
            className="rounded-12 border border-line px-14 py-9 text-12 font-semibold text-muted"
          >
            كتمُ المحدَّد
          </button>
          <button
            type="button"
            onClick={() => setPicked(new Set())}
            className="rounded-12 border border-line px-14 py-9 text-12 font-semibold text-muted"
          >
            إلغاءُ التحديد
          </button>
        </div>
      ) : null}

      <Table
        toolbar={
          <div className="flex flex-wrap items-center gap-10">
            <label className="flex items-center gap-8 text-11.5 text-muted">
              <input
                type="checkbox"
                checked={allPicked}
                onChange={() =>
                  setPicked(
                    allPicked
                      ? new Set()
                      : new Set((rows ?? []).map((row) => row.id)),
                  )
                }
              />
              تحديدُ الكلّ
            </label>
            <div className="min-w-half flex-1">
              <TableSearch
                value={search.text}
                onChange={search.setText}
                placeholder="صنفُ الاستثناء أو نصُّ الرسالة أو الملفّ…"
              />
            </div>
          </div>
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns={COLUMNS}
        headers={["", "العطب", "التطبيق", "آخر 24 ساعة", "المرات", "المتأثرون", "الظهور"]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: emptyTitle(status, app, hours),
          hint: "بدّل الحالةَ أو وسّع المدّة أو امسح البحث — وغيابُ الأعطال ليس دليلَ سلامة.",
        }}
        render={(row) => (
          <>
            <span onClick={(event) => event.stopPropagation()}>
              <input
                type="checkbox"
                checked={picked.has(row.id)}
                onChange={() => toggle(row.id)}
              />
            </span>

            <button
              type="button"
              onClick={() => void open(row.id)}
              className="min-w-0 text-start"
            >
              <span className="flex items-center gap-6">
                <Badge tone={KIND_TONE[row.kind] ?? "muted"}>
                  {KIND_LABEL[row.kind] ?? row.kind}
                </Badge>
                {row.regressed_at ? <Badge tone="warn">ارتداد</Badge> : null}
                {isNew(row) ? <Badge tone="ok">جديد</Badge> : null}
                <span className="truncate font-semibold text-ink">
                  {row.name}
                </span>
              </span>
              <span className="mt-4 block truncate text-11.5 text-muted" dir="ltr">
                {row.culprit ?? row.title}
              </span>
            </button>

            <span>
              <Badge tone="muted">{APP_LABEL[row.app] ?? row.app}</Badge>
            </span>

            <span>
              <Spark values={trend[row.id]} />
            </span>

            <span className="text-13 font-semibold text-ink">
              {digits(row.event_count)}
            </span>
            <span className="text-13 font-semibold text-ink">
              {digits(row.user_count)}
              <span className="block text-10.5 font-normal text-muted">
                جهازاً
              </span>
            </span>

            <span className="text-11.5 text-muted">
              <span className="block text-12 font-semibold text-ink" title={exactMoment(row.last_seen_at)}>
                {sinceNow(row.last_seen_at)}
              </span>
              <span title={exactMoment(row.first_seen_at)}>
                أول ظهور {sinceNow(row.first_seen_at)}
              </span>
            </span>
          </>
        )}
      />

      <div className="mt-12 flex items-center justify-between text-11.5 text-muted">
        <span>
          {rows?.length
            ? `يُعرض ${digits(page * PAGE + 1)}–${digits(page * PAGE + rows.length)} — والعدُّ من الخلفية لا من الصفحة`
            : ""}
        </span>
        <span className="flex gap-8">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((n) => Math.max(0, n - 1))}
            className="rounded-12 border border-line px-14 py-9 text-11.5 font-semibold text-ink disabled:opacity-50"
          >
            السابق
          </button>
          <button
            type="button"
            disabled={(rows?.length ?? 0) < PAGE}
            onClick={() => setPage((n) => n + 1)}
            className="rounded-12 border border-line px-14 py-9 text-11.5 font-semibold text-ink disabled:opacity-50"
          >
            التالي
          </button>
        </span>
      </div>

      {selected ? (
        <section className="mt-16 rounded-16 border border-line bg-surface p-16">
          <div className="flex flex-wrap items-start justify-between gap-12">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-8">
                <h2 className="text-15 font-bold text-ink">{selected.name}</h2>
                <Badge tone={STATUS_TONE[selected.status]}>
                  {STATUS_LABEL[selected.status]}
                </Badge>
                {selected.regressed_at ? <Badge tone="warn">ارتداد</Badge> : null}
              </div>
              <p className="mt-4 text-12.5 leading-note text-muted">
                {selected.title}
              </p>
              {selected.culprit ? (
                <p className="mt-4 text-11.5 text-muted" dir="ltr">
                  {selected.culprit}
                </p>
              ) : null}
              <p className="mt-6 text-12 text-muted">
                {APP_LABEL[selected.app]} · أول ظهور{" "}
                <span title={exactMoment(selected.first_seen_at)}>
                  {moment(selected.first_seen_at)}
                </span>{" "}
                ({selected.first_seen_release ?? "—"}) · آخر ظهور{" "}
                <span title={exactMoment(selected.last_seen_at)}>
                  {moment(selected.last_seen_at)}
                </span>{" "}
                ({selected.last_seen_release ?? "—"})
              </p>
              <p className="mt-4 text-12 text-muted">
                {digits(selected.event_count)} مرّة ·{" "}
                {digits(selected.user_count)} جهازاً متأثراً
                {selected.regressed_at ? " · عادت بعد حسمها" : ""}
              </p>
            </div>

            <div className="flex flex-wrap gap-8">
              {selected.status !== "resolved" ? (
                <button
                  type="button"
                  onClick={() => void act(resolveErrorGroup, selected.id)}
                  className="rounded-12 border border-line px-14 py-9 text-12.5 font-semibold text-ink"
                >
                  حُسم
                </button>
              ) : null}
              {selected.status !== "ignored" ? (
                <button
                  type="button"
                  onClick={() => void act(ignoreErrorGroup, selected.id)}
                  className="rounded-12 border border-line px-14 py-9 text-12.5 font-semibold text-muted"
                >
                  كتم
                </button>
              ) : null}
              {selected.status !== "open" ? (
                <button
                  type="button"
                  onClick={() => void act(reopenErrorGroup, selected.id)}
                  className="rounded-12 border border-line px-14 py-9 text-12.5 font-semibold text-muted"
                >
                  أعد فتحه
                </button>
              ) : null}
              <button
                type="button"
                onClick={close}
                className="rounded-12 border border-line px-14 py-9 text-12.5 font-semibold text-muted"
              >
                إغلاق
              </button>
            </div>
          </div>

          {shown ? (
            <div className="mt-14 space-y-10">
              <EventBody event={shown} newest={shown.id === events[0]?.id} />
            </div>
          ) : (
            <p className="mt-12 text-12.5 text-muted">
              لا حدثَ محفوظٌ لهذه المجموعة.
            </p>
          )}

          <Occurrences
            events={events}
            pickedId={shown?.id ?? null}
            onPick={(event) => setShown(event)}
          />

          {notes.length ? (
            <div className="mt-14">
              <h3 className="mb-6 text-13 font-bold text-ink">
                ما كتبه الناس ({digits(notes.length)})
              </h3>
              <ul className="space-y-8">
                {notes
                  .filter((item) => item.note)
                  .map((item) => (
                    <li
                      key={item.id}
                      className="rounded-12 border border-line bg-surface-2 p-12"
                    >
                      <p className="text-12.5 leading-note text-ink">
                        {item.note}
                      </p>
                      <p className="mt-4 text-11 text-muted">
                        {moment(item.received_at)}
                      </p>
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}
    </Shell>
  );
}

/** **جديدٌ** — أوّلُ ظهورٍ داخلَ نافذة اللمحة. */
function isNew(row: ErrorGroupRow): boolean {
  return Date.now() - new Date(row.first_seen_at).getTime() < NEW_WINDOW_MS;
}

/** عنوانُ الفراغ **بحسب المرشِّح** — لا نصٌّ واحدٌ لكلِّ حال. */
function emptyTitle(
  status: ErrorStatus | "all",
  app: ClientApp | "all",
  hours: number | "all",
): string {
  const state =
    status === "all" ? "أعطالَ" : `أعطالَ ${STATUS_LABEL[status]}ة`;
  const where = app === "all" ? "" : ` في ${APP_LABEL[app]}`;
  const when =
    hours === "all"
      ? ""
      : hours === 1
        ? " خلال ساعة"
        : ` خلال ${digits(hours)} ساعة`;
  return `لا ${state}${where}${when}`;
}

/** بطاقاتُ اللمحة — **وكلُّ رقمٍ منها من القاعدة**. */
function Summary({ data }: { data: ErrorSummary | null }) {
  if (!data) return null;
  const delta =
    data.devices_prev_24h > 0
      ? Math.round(
          ((data.devices_24h - data.devices_prev_24h) / data.devices_prev_24h) *
            100,
        )
      : null;

  return (
    <div className="mt-14 grid gap-12 md:grid-cols-4">
      <Card
        label="أعطالٌ مفتوحة"
        value={data.open}
        note={`منها ${digits(data.new_24h)} جديدة خلال 24 ساعة`}
      />
      <Card
        label="جديدةٌ خلال 24 ساعة"
        value={data.new_24h}
        note={
          data.regressed_24h
            ? `ومعها ${digits(data.regressed_24h)} ارتداد`
            : "ولا ارتدادَ فيها"
        }
      />
      <Card
        label="أجهزةٌ متأثرةٌ خلال 24 ساعة"
        value={data.devices_24h}
        note={
          delta === null
            ? "ولا يومَ سابقٌ يُقاس عليه"
            : `${delta >= 0 ? "+" : "−"}${digits(Math.abs(delta))}% عن الأمس`
        }
      />
      <Card
        label="بلاغاتُ مستخدمين تنتظر"
        value={data.reported_open}
        note={
          data.oldest_reported_at
            ? `أقدمُها ${sinceNow(data.oldest_reported_at)}`
            : "ولا بلاغَ ينتظر"
        }
        attention={data.reported_open > 0}
      />
    </div>
  );
}

function Card({
  label,
  value,
  note,
  attention,
}: {
  label: string;
  value: number;
  note: string;
  attention?: boolean;
}) {
  return (
    <div className="rounded-14 border border-line bg-surface p-14">
      <p className="text-11.5 text-muted">{label}</p>
      <p
        className={
          attention
            ? "mt-6 text-26 font-bold text-warn"
            : "mt-6 text-26 font-bold text-ink"
        }
      >
        {digits(value)}
      </p>
      <p className="mt-4 text-11 text-muted">{note}</p>
    </div>
  );
}

/** أعمدةُ الساعات — **نسبيّةٌ إلى أعلى ساعةٍ في هذا الصفّ وحدَه**. */
function Spark({ values }: { values?: number[] }) {
  if (!values?.length) {
    return <span className="text-11 text-muted">—</span>;
  }
  const peak = Math.max(...values, 1);
  const total = values.reduce((sum, item) => sum + item, 0);
  return (
    <span
      className="flex h-20 items-end gap-2"
      title={`${digits(total)} خلال ${digits(values.length)} ساعة`}
    >
      {values.map((item, index) => (
        <span
          key={index}
          className={
            index === values.length - 1
              ? "w-3 rounded-2 bg-ink"
              : "w-3 rounded-2 bg-line"
          }
          style={{ height: `${Math.max(2, Math.round((item / peak) * 20))}px` }}
        />
      ))}
    </span>
  );
}

/** كلُّ ما خُزِّن عن **مرّةٍ واحدةٍ بعينها**. */
function EventBody({
  event,
  newest,
}: {
  event: ErrorEventRow;
  newest: boolean;
}) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-8">
        <Badge tone={newest ? "ok" : "muted"}>
          {newest ? "الأحدث" : "مرّةٌ سابقة"}
        </Badge>
        {event.user_reported ? <Badge tone="warn">بلاغُ مستخدم</Badge> : null}
        <span className="text-11 text-muted">
          وقع{" "}
          <span title={exactMoment(event.occurred_at)}>
            {moment(event.occurred_at)}
          </span>{" "}
          · وصل{" "}
          <span title={exactMoment(event.received_at)}>
            {moment(event.received_at)}
          </span>
        </span>
      </div>

      {event.user_reported && event.note ? (
        <div className="rounded-12 border border-line bg-surface-2 p-12">
          <p className="mb-4 text-12 font-semibold text-ink">
            ما كتبه صاحبُ الجهاز
          </p>
          <p className="text-12.5 leading-note text-ink">{event.note}</p>
        </div>
      ) : null}

      <Detail label="الرسالة">{event.message}</Detail>
      <Detail label="المسار">{event.route ?? "—"}</Detail>

      <div className="flex flex-wrap gap-12">
        <Detail label="المنصّة">{event.platform}</Detail>
        <Detail label="الإصدار">{event.release ?? "—"}</Detail>
        <Detail label="القناة">{event.channel ?? "—"}</Detail>
        <Detail label="الشبكة">{event.online ? "متصل" : "غير متصل"}</Detail>
        <Detail label="التكرار في الجلسة">{digits(event.repeat)}</Detail>
      </div>
      <Detail label="نظام التشغيل">{event.os_version ?? "—"}</Detail>
      <Detail label="بصمة الجهاز">{event.device_hash}</Detail>

      {event.request_id ? (
        <CopyLine label="الرقم المرجعي" value={event.request_id} />
      ) : null}

      {event.stack ? (
        <StackBlock label="أثر المكدَّس" stack={event.stack} />
      ) : null}
      {event.component_stack ? (
        <StackBlock label="شجرة المكوّنات" stack={event.component_stack} />
      ) : null}

      <Crumbs items={event.breadcrumbs} />
    </>
  );
}

/** **كلُّ المرّات** — وكلُّ واحدةٍ تُفتح وحدَها. */
function Occurrences({
  events,
  pickedId,
  onPick,
}: {
  events: ErrorEventRow[];
  pickedId: string | null;
  onPick: (event: ErrorEventRow) => void;
}) {
  if (events.length <= 1) return null;
  return (
    <div className="mt-14">
      <h3 className="mb-6 text-13 font-bold text-ink">
        كل المرّات ({digits(events.length)})
      </h3>
      <ul className="space-y-8">
        {events.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onPick(item)}
              className={
                item.id === pickedId
                  ? "flex w-full flex-wrap items-center gap-8 rounded-12 border border-brand bg-surface-2 p-12 text-start"
                  : "flex w-full flex-wrap items-center gap-8 rounded-12 border border-line p-12 text-start"
              }
            >
              <span
                className="text-12 text-muted"
                title={exactMoment(item.received_at)}
              >
                {sinceNow(item.received_at)}
              </span>
              <span className="text-12 text-ink" dir="ltr">
                {item.route ?? "—"}
              </span>
              <span className="text-11 text-muted" dir="ltr">
                {item.device_hash}
              </span>
              {item.user_reported ? <Badge tone="warn">بلاغ</Badge> : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** الفُتاتُ بترتيبه وأوقاته — **سطراً سطراً لا `JSON` خاماً**. */
function Crumbs({ items }: { items: Record<string, unknown>[] | null }) {
  if (!items?.length) {
    return (
      <div>
        <p className="mb-4 text-12 font-semibold text-ink">الفُتات</p>
        <p className="text-12 leading-note text-muted">
          لا فُتاتَ في هذه المرّة — ولا يُقرأ ذلك «لم يقع شيءٌ قبل العطب»:
          جمعُ الفُتات حديثٌ، وما وقع قبله لا فُتاتَ فيه بحقّ.
        </p>
      </div>
    );
  }
  return (
    <div>
      <p className="mb-4 text-12 font-semibold text-ink">
        الفُتات ({digits(items.length)})
      </p>
      <ol className="space-y-6">
        {items.map((crumb, index) => {
          const at = crumb.at;
          return (
            <li
              key={index}
              className="flex flex-wrap items-center gap-8 rounded-12 border border-line p-12"
            >
              <span className="text-11 text-muted" dir="ltr">
                {typeof at === "string" ? moment(at) : "—"}
              </span>
              {CRUMB_KEYS.filter((key) => crumb[key] !== undefined).map(
                (key) => (
                  <span key={key} className="text-11.5 text-ink" dir="ltr">
                    {key}={String(crumb[key])}
                  </span>
                ),
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** ترتيبُ مفاتيح الفُتات كما يبنيها `core/scrub.py::_CRUMB_KEYS`. */
const CRUMB_KEYS = ["kind", "level", "method", "status", "route", "path", "text"];

/** كم إطاراً يُعرض قبل الطيّ — **والبقيّةُ تُفتح ولا تُقصّ**. */
const FRAME_PREVIEW = 12;

function Detail({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <p className="text-12.5 text-muted">
      <span className="font-semibold text-ink">{label}: </span>
      <span dir="ltr">{children}</span>
    </p>
  );
}

/** سطرٌ يُنسخ — **الرقمُ المرجعيُّ يُلصَق في بحث السجلّ، فلا يُكتب بيد**. */
function CopyLine({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <p className="flex flex-wrap items-center gap-8 text-12.5 text-muted">
      <span className="font-semibold text-ink">{label}: </span>
      <span dir="ltr">{value}</span>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard
            .writeText(value)
            .then(() => setCopied(true))
            .catch(() => setCopied(false));
        }}
        className="rounded-12 border border-line px-14 py-9 text-11 font-semibold text-muted"
      >
        {copied ? "نُسخ" : "انسخ"}
      </button>
    </p>
  );
}

/** أثرٌ **يُفتح كاملاً** — ولا يُميَّز إطارُ المكتبة، انظر رأسَ الملفّ. */
function StackBlock({ label, stack }: { label: string; stack: string }) {
  const [all, setAll] = useState(false);
  const lines = stack.split("\n");
  const list = all ? lines : lines.slice(0, FRAME_PREVIEW);
  const hidden = lines.length - list.length;

  return (
    <div>
      <p className="mb-4 text-12 font-semibold text-ink">{label}</p>
      <pre
        dir="ltr"
        className={
          all
            ? "scr overflow-auto rounded-12 border border-line bg-surface-2 p-12 text-11 leading-relaxed text-muted"
            : "scr max-h-list overflow-auto rounded-12 border border-line bg-surface-2 p-12 text-11 leading-relaxed text-muted"
        }
      >
        {list.map((line, index) => (
          <span key={index} className="block text-ink">
            {line}
          </span>
        ))}
      </pre>
      <p className="mt-4 text-11 leading-note text-muted">
        إطارُ المكتبة لا يُميَّز من إطارِنا — الحزمةُ مُصغَّرةٌ بلا خرائطِ
        مصدر، ولا اسمَ في الأثر يفرّقهما.
      </p>
      {hidden > 0 || all ? (
        <button
          type="button"
          onClick={() => setAll((was) => !was)}
          className="mt-6 rounded-12 border border-line px-14 py-9 text-11 font-semibold text-muted"
        >
          {all ? "اطوِ الأثر" : `أظهر ${digits(hidden)} إطاراً إضافياً`}
        </button>
      ) : null}
    </div>
  );
}
