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
 * **والمُعرِّفُ الوحيدُ `device_hash`**: مُعمّىً مرّتين ولا يُوصَل بصاحبه —
 * وهو موجودٌ ليُقال «جهازان أم أربعمئة»، لا ليُعرف أيُّ جهاز.
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
      setSelected(await getErrorGroup(id));
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
            <span className="text-muted">{row.event_count}</span>
            <span className="font-semibold text-ink">{row.user_count}</span>
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
                {APP_LABEL[selected.app]} · أول ظهور {moment(selected.first_seen_at)}{" "}
                ({selected.first_seen_release ?? "—"}) · آخر ظهور{" "}
                {moment(selected.last_seen_at)} ({selected.last_seen_release ?? "—"})
              </p>
              <p className="mt-4 text-12 text-muted">
                {selected.event_count} مرّة · {selected.user_count} جهازاً متأثراً
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
                onClick={() => {
                  setSelected(null);
                  setNotes([]);
                }}
                className="rounded-12 border border-line px-14 py-9 text-12.5 font-semibold text-muted"
              >
                إغلاق
              </button>
            </div>
          </div>

          {selected.latest ? (
            <div className="mt-14 space-y-10">
              <Detail label="المسار">{selected.latest.route ?? "—"}</Detail>
              <Detail label="الجهاز">
                {selected.latest.platform} · {selected.latest.os_version ?? "—"} ·{" "}
                {selected.latest.online ? "متصل" : "غير متصل"}
              </Detail>
              {/* **الخيطُ إلى الخلفية** — يُبحث به في سجلّ الخادم مباشرةً */}
              {selected.latest.request_id ? (
                <Detail label="الرقم المرجعي">
                  {selected.latest.request_id}
                </Detail>
              ) : null}
              {selected.latest.stack ? (
                <Block label="أثر المكدَّس">{selected.latest.stack}</Block>
              ) : null}
              {selected.latest.component_stack ? (
                <Block label="شجرة المكوّنات">
                  {selected.latest.component_stack}
                </Block>
              ) : null}
              {selected.latest.breadcrumbs?.length ? (
                <Block label="الفُتات">
                  {JSON.stringify(selected.latest.breadcrumbs, null, 2)}
                </Block>
              ) : null}
            </div>
          ) : (
            <p className="mt-12 text-12.5 text-muted">لا حدثَ محفوظٌ لهذه المجموعة.</p>
          )}

          {notes.length ? (
            <div className="mt-14">
              <h3 className="mb-6 text-13 font-bold text-ink">
                ما كتبه الناس ({notes.length})
              </h3>
              <ul className="space-y-8">
                {notes
                  .filter((item) => item.note)
                  .map((item) => (
                    <li
                      key={item.id}
                      className="rounded-12 border border-line bg-surface-2 p-12"
                    >
                      <p className="text-12.5 leading-note text-ink">{item.note}</p>
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

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p className="text-12.5 text-muted">
      <span className="font-semibold text-ink">{label}: </span>
      <span dir="ltr">{children}</span>
    </p>
  );
}

function Block({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <p className="mb-4 text-12 font-semibold text-ink">{label}</p>
      <pre
        dir="ltr"
        className="scr max-h-list overflow-auto rounded-12 border border-line bg-surface-2 p-12 text-11 leading-relaxed text-muted"
      >
        {children}
      </pre>
    </div>
  );
}
