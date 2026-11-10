/** **الاعتمادُ الاستثنائيُّ ومتابعةُ الوثائق** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ١ و٢).
 *
 * * `ExceptionalCard` — في درج الكبتن: الوسمُ «معتمد دون وثائق» ومن اعتمده وسببُه ومهلتُه وما ينقصه، والأفعال:
 *   «اعتماد استثنائي» · «طلب الوثائق» · التذكير · تمديدُ المهلة · «تجميد/إلغاء التجميد». **كلُّها بسببٍ مكتوبٍ يدخل التدقيق.**
 * * `DocumentSettingsCard` — إعداداتُ الدولة: المهلةُ وتكرارُ التذكير وأيامُ التنبيه قبل انتهاء وثيقة.
 * * `RequestAllButton` — «طلب الوثائق» من كلِّ الموسومين في الدولة دفعةً.
 *
 * **والأفعالُ لمن يملك `drivers.exceptional` وحدَه** — حسّاسة: للمالك ومن يمنحه بالاسم؛ وغيرُه يقرأ ولا يرى الأزرار.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveDriverExceptional,
  freezeDriver,
  getDocumentSettings,
  getDriverExceptional,
  listExpiringDocuments,
  requestDriverDocuments,
  saveDocumentSettings,
  setDocumentFollowup,
  unfreezeDriver,
} from "@/api/endpoints";
import type { CountryCode, DocumentSettings, DriverExceptional, ExpiringDocumentRow } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Select, Switch } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useMyPermissions } from "@/lib/permissions";
import { DISPLAY_LOCALE } from "@/lib/utils";

export const EXCEPTIONAL_PERMISSION = "drivers.exceptional";

const MIN_REASON = 4;

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

function day(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(DISPLAY_LOCALE, { year: "numeric", month: "short", day: "numeric" });
}

function daysLeft(iso: string | null): number | null {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

export function useCanExceptional(): boolean {
  const held = useMyPermissions();
  return held?.has(EXCEPTIONAL_PERMISSION) ?? false;
}

/** **الوسمُ في صفِّ القائمة** — للمشرفين وحدَهم، بجانب الحال لا بدلاً منها. */
export function ExceptionalBadge({ exceptional, deadline }: { exceptional: boolean; deadline: string | null }) {
  if (!exceptional) return null;
  const left = daysLeft(deadline);
  return (
    <Badge tone={left !== null && left <= 3 ? "danger" : "warn"}>
      معتمد دون وثائق{left !== null ? ` · ${left > 0 ? `${left} يوماً` : "انتهت المهلة"}` : ""}
    </Badge>
  );
}

export function ExceptionalCard({
  driverId,
  onChanged,
}: {
  driverId: string;
  /** **حالُ الكبتن تغيّرت** — فتُحدَّث القائمةُ خلف الدرج */
  onChanged: (message: string) => void;
}) {
  const canAct = useCanExceptional();
  const [data, setData] = useState<DriverExceptional | null>(null);
  const [reason, setReason] = useState("");
  const [extend, setExtend] = useState("7");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setData(await getDriverExceptional(driverId));
  }, [driverId]);

  useEffect(() => {
    load().catch((caught) => setError(messageOf(caught, "تعذّر قراءة حال الوثائق")));
  }, [load]);

  async function run(action: () => Promise<DriverExceptional | unknown>, message: string, statusChanges: boolean) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const answer = await action();
      if (answer && typeof answer === "object" && "driver_id" in answer) setData(answer as DriverExceptional);
      else await load();
      setReason("");
      setDone(message);
      if (statusChanges) onChanged(message);
    } catch (caught) {
      setError(messageOf(caught, "تعذّر التنفيذ"));
    } finally {
      setBusy(false);
    }
  }

  if (data === null) {
    return error ? <ErrorNote message={error} /> : null;
  }

  const reasonOk = reason.trim().length >= MIN_REASON;
  const left = daysLeft(data.deadline_at);
  return (
    <section className="card mt-12 flex flex-col gap-10 p-16" aria-labelledby="exceptional-title">
      <div className="flex flex-wrap items-center gap-8">
        <h3 id="exceptional-title" className="text-14 font-bold text-ink">
          الاعتماد الاستثنائي ومتابعة الوثائق
        </h3>
        {data.exceptional ? <Badge tone="warn">معتمد دون وثائق</Badge> : null}
        {data.status === "suspended" ? <Badge tone="danger">مجمَّد</Badge> : null}
      </div>

      <p className="text-12.5 leading-relaxed text-muted">
        <b>اعتماد استثنائي</b>: يعتمد السائقَ ولو نقصت وثائقه (الرقمُ المُثبت شرطٌ باقٍ)، بسببٍ مكتوبٍ في سجلّ التدقيق، ويوسم
        الحساب «معتمد دون وثائق» (يراه المشرفون وحدهم). تبدأ مهلةُ الرفع من إعداد الدولة، ويصله تذكيرٌ دوريّ وتذكيرٌ قبل المهلة
        بثلاثة أيامٍ وبيوم، <b>ثم يُجمَّد آلياً</b> إن لم يرفع. رفعُ الوثائق لا يوقف عمله، والاعتمادُ العاديُّ لها يزيل الوسم.
      </p>

      {data.exceptional ? (
        <dl className="grid grid-cols-2 gap-8 text-12.5">
          <dt className="text-muted">اعتمده</dt>
          <dd className="text-ink">{data.approved_by_name ?? "—"} · {day(data.approved_at)}</dd>
          <dt className="text-muted">السبب</dt>
          <dd className="text-ink">{data.reason ?? "—"}</dd>
          <dt className="text-muted">مهلة الرفع</dt>
          <dd className={left !== null && left <= 3 ? "text-danger" : "text-ink"}>
            {day(data.deadline_at)}
            {left !== null ? ` (${left > 0 ? `بعد ${left} يوماً` : "انتهت"})` : ""}
          </dd>
          <dt className="text-muted">آخر تذكير</dt>
          <dd className="text-ink">{day(data.reminded_at)}</dd>
        </dl>
      ) : null}
      <p className="text-12.5 text-ink">
        {data.missing_documents.length > 0
          ? `ينقصه: ${data.missing_documents.join(" · ")}`
          : "لا وثيقةَ مطلوبةً ناقصة."}
      </p>

      {canAct ? (
        <>
          <Field
            label="السبب (إلزاميّ — يدخل سجلّ التدقيق ويصل السائقَ في التجميد)"
            name="exceptional-reason"
            placeholder="مثلاً: سائقٌ معروف، وثائقه قيد الاستخراج"
            value={reason}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="flex flex-wrap gap-8">
            {data.status !== "approved" && data.status !== "suspended" ? (
              <Button
                size="sm"
                disabled={busy || !reasonOk}
                onClick={() =>
                  void run(() => approveDriverExceptional(driverId, reason.trim()), "اعتُمد استثنائياً — بدأت مهلة الوثائق", true)
                }
              >
                اعتماد استثنائي
              </Button>
            ) : null}
            {data.status === "approved" ? (
              <Button
                size="sm"
                variant="danger"
                disabled={busy || !reasonOk}
                onClick={() => void run(() => freezeDriver(driverId, reason.trim()), "جُمِّد الحساب ووصلته رسالةٌ بالسبب", true)}
              >
                تجميد
              </Button>
            ) : null}
            {data.status === "suspended" ? (
              <Button
                size="sm"
                disabled={busy || !reasonOk}
                onClick={() => void run(() => unfreezeDriver(driverId, reason.trim()), "أُلغي التجميد", true)}
              >
                إلغاء التجميد
              </Button>
            ) : null}
            {data.missing_documents.length > 0 ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void run(() => requestDriverDocuments({ driver_ids: [driverId] }), "أُرسل طلبُ الوثائق إلى السائق", false)
                }
              >
                طلب الوثائق
              </Button>
            ) : null}
          </div>

          {data.exceptional ? (
            <div className="flex flex-wrap items-end gap-12">
              <Switch
                label="التذكير الدوريّ لهذا السائق"
                checked={data.reminders_enabled}
                disabled={busy}
                onChange={(next) =>
                  void run(
                    () => setDocumentFollowup(driverId, { reminders: next }),
                    next ? "شُغِّل التذكير" : "أُطفئ التذكير لهذا السائق",
                    false,
                  )
                }
              />
              <Select label="تمديد المهلة" value={extend} onChange={(event) => setExtend(event.target.value)}>
                <option value="3">3 أيام</option>
                <option value="7">7 أيام</option>
                <option value="14">14 يوماً</option>
                <option value="30">30 يوماً</option>
              </Select>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => setDocumentFollowup(driverId, { extend_days: Number(extend) }),
                    `مُدّت المهلة ${extend} يوماً`,
                    true,
                  )
                }
              >
                تمديد
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <p className="text-12 text-muted">الأفعالُ هنا لمن مُنح صلاحية «الاعتماد الاستثنائي» بالاسم.</p>
      )}

      <ErrorNote message={error} />
      <SuccessNote message={done} />
    </section>
  );
}

/** **«طلب الوثائق» من كلِّ «معتمد دون وثائق» في الدولة** — دفعةً واحدة. */
export function RequestAllButton({ country, onDone }: { country: CountryCode | undefined; onDone: (message: string) => void }) {
  const canAct = useCanExceptional();
  const [busy, setBusy] = useState(false);
  if (!canAct) return null;
  return (
    <Button
      size="sm"
      variant="secondary"
      disabled={busy}
      onClick={() => {
        setBusy(true);
        requestDriverDocuments({ all_flagged: true, country_code: country })
          .then((answer) => onDone(`أُرسل طلبُ الوثائق إلى ${answer.sent} سائقاً`))
          .catch((caught) => onDone(messageOf(caught, "تعذّر الإرسال")))
          .finally(() => setBusy(false));
      }}
    >
      طلب الوثائق من الكلّ
    </Button>
  );
}

/** **إعداداتُ متابعة الوثائق للدولة** — كلُّ حقلٍ بشرحه (البند ٢٠). */
export function DocumentSettingsCard({ country }: { country: CountryCode }) {
  const canAct = useCanExceptional();
  const [data, setData] = useState<DocumentSettings | null>(null);
  const [deadline, setDeadline] = useState("14");
  const [reminder, setReminder] = useState("3");
  const [notice, setNotice] = useState("30, 7, 1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const apply = useCallback((answer: DocumentSettings) => {
    setData(answer);
    setDeadline(String(answer.exceptional_deadline_days));
    setReminder(String(answer.exceptional_reminder_days));
    setNotice(answer.expiry_notice_days.join(", "));
  }, []);

  useEffect(() => {
    getDocumentSettings(country)
      .then(apply)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة الإعدادات")));
  }, [country, apply]);

  async function save() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      apply(
        await saveDocumentSettings(country, {
          exceptional_deadline_days: Number(deadline),
          exceptional_reminder_days: Number(reminder),
          expiry_notice_days: notice
            .split(/[,،\s]+/)
            .map((part) => Number(part))
            .filter((value) => Number.isFinite(value) && value > 0),
        }),
      );
      setDone("حُفظت الإعدادات");
    } catch (caught) {
      setError(messageOf(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card mt-12 flex flex-col gap-10 p-16" aria-labelledby="doc-settings-title">
      <h2 id="doc-settings-title" className="text-15 font-bold text-ink">
        متابعة الوثائق — إعدادات الدولة
      </h2>
      <div className="grid gap-12 md:grid-cols-3">
        <div>
          <Field
            label="مهلة رفع الوثائق (أيام)"
            name="doc-deadline"
            inputMode="numeric"
            value={deadline}
            disabled={!canAct}
            onChange={(event) => setDeadline(event.target.value)}
          />
          <p className="mt-4 text-12 text-muted">
            لمن اعتُمد استثنائياً: بعدها يُجمَّد حسابه آلياً حتى يرفع. يصله تذكيرٌ قبلها بثلاثة أيامٍ وبيوم. (1–180)
          </p>
        </div>
        <div>
          <Select
            label="تكرار التذكير"
            value={reminder}
            disabled={!canAct}
            onChange={(event) => setReminder(event.target.value)}
          >
            <option value="1">يومياً</option>
            <option value="3">كلَّ 3 أيام</option>
            <option value="7">أسبوعياً</option>
          </Select>
          <p className="mt-4 text-12 text-muted">
            إشعارٌ «ارفع وثائقك» ما دامت ناقصة. يُطفأ لكلِّ سائقٍ من درجه.
          </p>
        </div>
        <div>
          <Field
            label="التنبيه قبل انتهاء وثيقة (أيام)"
            name="doc-notice"
            value={notice}
            disabled={!canAct}
            onChange={(event) => setNotice(event.target.value)}
          />
          <p className="mt-4 text-12 text-muted">
            لكلِّ السائقين: تنبيهٌ قبل انتهاء الرخصة أو الوثيقة بهذه الأيام (حتى 5 قيم، مثل 30, 7, 1). عند الانتهاء يُعلَّق الحساب
            آلياً حتى تُرفع الجديدة.
          </p>
        </div>
      </div>
      {canAct ? (
        <div>
          <Button size="sm" disabled={busy || data === null} onClick={() => void save()}>
            حفظ
          </Button>
        </div>
      ) : (
        <p className="text-12 text-muted">التعديلُ لمن مُنح صلاحية «الاعتماد الاستثنائي».</p>
      )}
      <ErrorNote message={error} />
      <SuccessNote message={done} />
    </section>
  );
}

/** **«وثائق تنتهي قريباً»** (البند ٢) — المطلوبةُ وحدَها، المنتهيةُ أوّلاً. التنبيهُ والتعليقُ آليّان؛ هذه القائمةُ لمن يتّصل قبلهما. */
export function ExpiringDocumentsCard({ country, onOpen }: { country: CountryCode; onOpen: (driverId: string, name: string) => void }) {
  const [days, setDays] = useState("30");
  const [rows, setRows] = useState<ExpiringDocumentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    listExpiringDocuments(country, Number(days))
      .then(setRows)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة الوثائق")));
  }, [country, days]);

  return (
    <section className="card mt-12 flex flex-col gap-10 p-16" aria-labelledby="expiring-title">
      <div className="flex flex-wrap items-end justify-between gap-12">
        <div>
          <h2 id="expiring-title" className="text-15 font-bold text-ink">
            وثائق تنتهي قريباً
          </h2>
          <p className="text-12 text-muted">
            الوثائقُ المطلوبةُ التي تنتهي خلال المدّة أو انتهت ولم تُستبدل. يصل السائقَ تنبيهٌ آليٌّ بأيام الإعداد أدناه، ويُعلَّق
            حسابُه يومَ الانتهاء حتى يرفع الجديدة.
          </p>
        </div>
        <Select label="خلال" value={days} onChange={(event) => setDays(event.target.value)}>
          <option value="7">7 أيام</option>
          <option value="30">30 يوماً</option>
          <option value="60">60 يوماً</option>
          <option value="120">120 يوماً</option>
        </Select>
      </div>
      <ErrorNote message={error} />
      {rows === null ? <p className="text-12.5 text-muted">…</p> : null}
      {rows !== null && rows.length === 0 ? <p className="text-12.5 text-muted">لا وثيقةَ تنتهي في هذه المدّة.</p> : null}
      <ul className="flex flex-col divide-y divide-line">
        {(rows ?? []).map((row) => (
          <li key={row.document_id} className="flex flex-wrap items-center gap-12 py-8">
            <button type="button" className="min-w-[10rem] text-start text-13 font-semibold text-ink underline" onClick={() => onOpen(row.driver_id, row.driver_name)}>
              {row.driver_name}
            </button>
            <span className="text-12.5 text-ink">{row.doc_label}</span>
            <span className="text-12.5 text-muted">{day(row.expires_on)}</span>
            <Badge tone={row.days_left < 0 ? "danger" : row.days_left <= 7 ? "warn" : "muted"}>
              {row.days_left < 0 ? "انتهت" : row.days_left === 0 ? "اليوم" : `بعد ${row.days_left} يوماً`}
            </Badge>
          </li>
        ))}
      </ul>
    </section>
  );
}
