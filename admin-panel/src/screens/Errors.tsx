/** شاشةُ الأعطال — **تُرتَّب بالمتأثّرين لا بالمرّات** (2026-09-20).
 *
 * **وهذا الافتراضُ هو الشاشةُ كلُّها**: حلقةُ رسمٍ في هاتفٍ واحدٍ تُنتج آلافَ
 * الأحداث، **فالترتيبُ بالمرّات يضعها فوق عطبٍ يمسّ نصفَ الأسطول**. والسؤالُ
 * الذي يُبنى عليه قرارٌ هو «كم إنساناً»، لا «كم مرّة».
 *
 * **وصفٌّ واحدٌ لكلِّ عطبٍ لا صفٌّ لكلِّ وقوع**: التجميعُ يقع في الخلفية
 * (`services/error_reports.fingerprint_of`)، وهذه تعرض ما جمّعته. **ولو عرضت
 * الأحداثَ خاماً** لقرأ المشرفُ أربعين صفّاً متطابقاً ولم يعرف أواحدٌ أصابه
 * أربعون مرّةً أم أربعون إنساناً مرّةً.
 *
 * ## وما ليس في هذه الشاشة — بقصد
 *
 * **لا رقمَ هاتفٍ ولا حسابَ ولا موقع.** ما يصل الجدولَ مرّ بـ`core/scrub.py`،
 * **فالشاشةُ لا تملك ما تُخفيه** — وهذا أقوى من إخفاءٍ في الواجهة، لأن ما
 * يُخفيه المتصفّحُ يبقى في الردّ لمن يقرأ الـAPI.
 *
 * > **⚠ واستثناءٌ مكتوبٌ لا مسكوتٌ عنه** (قِيس ٢٠٢٦-٠٩-٢١): **الإحداثيّةُ في
 * > نصٍّ حرٍّ لا تُحجب** — `lat=31.9539 lng=35.9106` استقرّ في الجدول عارياً،
 * > **وقرارُ المالك إبقاؤه**. فالسطرُ أعلاه يصف الهاتفَ والبريدَ والمبلغَ
 * > والمُعرِّف، **ولا يُقاس عليه الموقع**.
 *
 * **والمُعرِّفُ الوحيدُ `device_hash`**: مُعمّىً مرّتين ولا يُوصَل بصاحبه —
 * وهو موجودٌ ليُقال «جهازان أم أربعمئة»، لا ليُعرف أيُّ جهاز.
 *
 * ## والتفصيلُ يعرض كلَّ ما خُزِّن لا مُقتطَفاً منه (٢٠٢٦-٠٩-٢١)
 *
 * **كان يعرض آخرَ حدثٍ وحدَه**، وأثرَ المكدَّس في صندوقٍ يُقصّ بارتفاعٍ ثابت،
 * والفُتاتَ `JSON` خاماً. **ومُقتطَفٌ يُقرأ كاملاً هو الشكلُ الثاني عشر**:
 * بديلٌ يعمل فيستر ما بُني له. فصار يعرض:
 *
 * - **أثرَ المكدَّس كاملاً**، و**إطاراتُ المكتبات تُميَّز عن إطاراتنا** —
 *   لأن العينَ تقفز إلى الثانية، وأولُ سطرٍ في الأثر غالباً ليس موضعَ العطب.
 * - **كلَّ المرّات لا آخرَها**: «وقعت على ثلاثة أجهزةٍ في ثلاثة مساراتٍ» خبرٌ
 *   لا يقوله آخرُ حدثٍ مهما فُصِّل، **وكلُّ مرّةٍ تُفتح وحدَها**.
 * - **والفُتاتَ سطراً سطراً بأوقاته** — وهو ما يقول *ماذا كان يفعل قبل أن يقع*.
 *
 * > **⚠ والفُتاتُ فارغٌ اليومَ بحقّ**: الخلفيةُ تقبله (`scrub_breadcrumbs`)
 * > والشاشةُ ترسمه، **ولا تطبيقَ يرسله بعد** — فالقسمُ يقول ذلك بنصّه ولا
 * > يُقرأ سكوتُه «لم يقع شيءٌ قبل العطب».
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  getErrorGroup,
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
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
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
  error: "استثناء",
  rejection: "وعدٌ مرفوض",
  boundary: "حدُّ الشاشة",
  user_report: "بلاغُ مستخدم",
};

/** **إطارُ مكتبةٍ لا إطارُنا** — والتمييزُ بصريٌّ لا حذف.
 *
 * **ولا يُحذف الإطارُ الأجنبيُّ بحال**: العطبُ يقع أحياناً *داخل* المكتبة
 * بوسيطٍ أرسلناه نحن، **فحذفُه يقطع الخيط**. يُخفَّت لونُه فحسب، فتقفز العينُ
 * إلى ما نملك إصلاحَه **دون أن يضيع ما لا نملكه**.
 */
const VENDOR_FRAME = /node_modules|\/vendor|vendor-|chunk-|react-dom|\.vite\//i;

/** كم إطاراً يُعرض قبل الطيّ — **والبقيّةُ تُفتح ولا تُقصّ**. */
const FRAME_PREVIEW = 12;

/** ترتيبُ مفاتيح الفُتات كما يبنيها `core/scrub.py::_CRUMB_KEYS`. */
const CRUMB_KEYS = ["kind", "level", "method", "status", "route", "path", "text"];

const COLUMNS = "1fr 2.2fr 0.7fr 0.8fr 0.6fr 0.7fr 0.8fr";

export function ErrorsScreen() {
  const [status, setStatus] = useState<ErrorStatus | "all">("open");
  const [app, setApp] = useState<ClientApp | "all">("all");
  const [sort, setSort] = useState<ErrorSort>("users");
  const [release, setRelease] = useState("");
  const [appliedRelease, setAppliedRelease] = useState("");
  const [rows, setRows] = useState<ErrorGroupRow[] | null>(null);
  const [selected, setSelected] = useState<ErrorGroupDetail | null>(null);
  const [notes, setNotes] = useState<ErrorEventRow[]>([]);
  /** **كلُّ مرّات هذا العطب** — لا آخرُها وحدَها. */
  const [events, setEvents] = useState<ErrorEventRow[]>([]);
  /** **المرّةُ المعروضةُ الآن** — الأحدثُ افتراضاً، وتُبدَّل بالنقر. */
  const [picked, setPicked] = useState<ErrorEventRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const search = useSearch();

  const load = useCallback(async () => {
    setRows(null);
    setRows(
      await listErrorGroups({
        app: app === "all" ? undefined : app,
        status: status === "all" ? undefined : status,
        release: appliedRelease || undefined,
        q: search.term,
        sort,
        limit: 200,
      }),
    );
  }, [app, status, appliedRelease, search.term, sort]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الأعطال",
      ),
    );
  }, [load]);

  const open = async (id: string) => {
    setError(null);
    try {
      const detail = await getErrorGroup(id);
      setSelected(detail);
      // **كلُّ المرّات** — «ثلاثةُ أجهزةٍ في ثلاثة مسارات» لا يقوله آخرُ حدث
      const all = await listErrorEvents(id, false);
      setEvents(all);
      setPicked(detail.latest ?? all[0] ?? null);
      // **بلاغاتُ الناس أولاً**: جملةُ إنسانٍ تقول ما كان يحاول أن يفعل
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
      await open(id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  };

  const close = () => {
    setSelected(null);
    setNotes([]);
    setEvents([]);
    setPicked(null);
  };

  return (
    <Shell
      title="الأعطال"
      subtitle="عطبٌ واحدٌ في صفٍّ واحدٍ مهما تكرّر — والترتيبُ بمن أصابهم لا بعدد المرّات"
    >
      <Pills
        value={status}
        onPick={(key) => setStatus(key)}
        options={[
          { key: "open", label: "مفتوحة" },
          { key: "resolved", label: "محسومة" },
          { key: "ignored", label: "مكتومة" },
          { key: "all", label: "الكل" },
        ]}
      />

      <div className="mt-8">
        <Pills
          value={app}
          onPick={(key) => setApp(key)}
          options={[
            { key: "all", label: "كل التطبيقات" },
            { key: "rider", label: "الراكب" },
            { key: "driver", label: "الكبتن" },
            { key: "panel", label: "اللوحة" },
          ]}
        />
      </div>

      <div className="mt-8">
        <Pills
          value={sort}
          onPick={(key) => setSort(key === "all" ? "users" : key)}
          options={[
            { key: "users", label: "الأكثر تأثيراً" },
            { key: "last_seen", label: "الأحدث" },
            { key: "events", label: "الأكثر تكراراً" },
          ]}
        />
      </div>

      <form
        className="mb-14 mt-12 flex max-w-modal items-end gap-9"
        onSubmit={(event) => {
          event.preventDefault();
          setAppliedRelease(release.trim());
        }}
      >
        <div className="flex-1">
          <Field
            label="الإصدار (آخرُ ظهور)"
            placeholder="1.4.0+42"
            dir="ltr"
            value={release}
            onChange={(event) => setRelease(event.target.value)}
          />
        </div>
        <button
          type="submit"
          className="rounded-13 border border-line px-16 py-13 text-13 font-semibold text-ink"
        >
          فلترة
        </button>
      </form>

      <ErrorNote message={error} />

      <Table
        toolbar={
          <TableSearch
            value={search.text}
            onChange={search.setText}
            placeholder="صنفُ الاستثناء أو نصُّ الرسالة…"
          />
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns={COLUMNS}
        headers={[
          "آخر ظهور",
          "العطب",
          "التطبيق",
          "الإصدار",
          "المرات",
          "المتأثرون",
          "الحالة",
        ]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا أعطال في هذه الفلترة",
          hint: "بدّل الحالة أو امسح الإصدار — وغيابُ الأعطال ليس دليلَ سلامة.",
        }}
        render={(row) => (
          <>
            <span className="text-muted">{moment(row.last_seen_at)}</span>

            <button
              type="button"
              onClick={() => void open(row.id)}
              className="min-w-0 text-start"
            >
              <span className="block truncate font-semibold text-ink">
                {row.name}
              </span>
              <span className="block truncate text-12 text-muted">
                {KIND_LABEL[row.kind] ?? row.kind} · {row.title}
              </span>
            </button>

            <span className="text-ink">{APP_LABEL[row.app] ?? row.app}</span>
            <span className="text-muted" dir="ltr">
              {row.last_seen_release ?? "—"}
            </span>
            <span className="text-muted">{digits(row.event_count)}</span>
            <span className="font-semibold text-ink">
              {digits(row.user_count)}
            </span>
            <span>
              <Badge tone={STATUS_TONE[row.status]}>
                {STATUS_LABEL[row.status]}
              </Badge>
            </span>
          </>
        )}
      />

      {selected ? (
        <section className="mt-16 rounded-16 border border-line bg-surface p-16">
          <div className="flex flex-wrap items-start justify-between gap-12">
            <div className="min-w-0">
              <h2 className="text-15 font-bold text-ink">{selected.name}</h2>
              <p className="mt-4 text-12.5 leading-note text-muted">
                {selected.title}
              </p>
              <p className="mt-6 text-12 text-muted">
                {APP_LABEL[selected.app]} · أول ظهور{" "}
                {moment(selected.first_seen_at)} (
                {selected.first_seen_release ?? "—"}) · آخر ظهور{" "}
                {moment(selected.last_seen_at)} (
                {selected.last_seen_release ?? "—"})
              </p>
              <p className="mt-4 text-12 text-muted">
                {digits(selected.event_count)} مرّة ·{" "}
                {digits(selected.user_count)} جهازاً متأثراً
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

          {picked ? (
            <div className="mt-14 space-y-10">
              <EventBody event={picked} newest={picked.id === events[0]?.id} />
            </div>
          ) : (
            <p className="mt-12 text-12.5 text-muted">
              لا حدثَ محفوظٌ لهذه المجموعة.
            </p>
          )}

          <Occurrences
            events={events}
            pickedId={picked?.id ?? null}
            onPick={(event) => setPicked(event)}
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
          وقع {moment(event.occurred_at)} · وصل {moment(event.received_at)}
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

      {/* **الجهازُ والبيئة** — «أفي النسخة الجديدة وحدَها؟» أولُ سؤالٍ يُسأل */}
      <div className="flex flex-wrap gap-12">
        <Detail label="المنصّة">{event.platform}</Detail>
        <Detail label="الإصدار">{event.release ?? "—"}</Detail>
        <Detail label="القناة">{event.channel ?? "—"}</Detail>
        <Detail label="الشبكة">{event.online ? "متصل" : "غير متصل"}</Detail>
        <Detail label="التكرار في الجلسة">{digits(event.repeat)}</Detail>
      </div>
      <Detail label="نظام التشغيل">{event.os_version ?? "—"}</Detail>
      {/* **مُعمّىً مرّتين** — يقول «كم جهازاً»، ولا يقول أيُّ جهاز */}
      <Detail label="بصمة الجهاز">{event.device_hash}</Detail>

      {/* **الخيطُ إلى الخلفية** — يُنسخ ويُبحث به في سجلّ الخادم مباشرةً */}
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
              <span className="text-12 text-muted">
                {moment(item.received_at)}
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
          الخلفيةُ تقبله والشاشةُ ترسمه، ولا تطبيقَ يرسله بعد.
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

/** أثرٌ **يُفتح كاملاً**، وإطاراتُ المكتبات مُخفَّتةٌ لا محذوفة. */
function StackBlock({ label, stack }: { label: string; stack: string }) {
  const [all, setAll] = useState(false);
  const lines = stack.split("\n");
  const shown = all ? lines : lines.slice(0, FRAME_PREVIEW);
  const hidden = lines.length - shown.length;

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
        {shown.map((line, index) => (
          <span
            key={index}
            className={
              VENDOR_FRAME.test(line) ? "block text-muted" : "block text-ink"
            }
          >
            {line}
          </span>
        ))}
      </pre>
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
