/** النسخُ الاحتياطي في اللوحة (`design/BACKUP-AND-RESTORE.md` §٦).
 *
 * **وثلاثةُ أشياءَ تُقال هنا صراحةً لأن الصمتَ عنها هو العطب:**
 *
 * 1. **«لم تُسحب» ليست تفصيلاً**: نسخةٌ على الخادم وحدَه ليست نسخةً احتياطية —
 *    قرصٌ واحدٌ يحمل النظامَ ونسختَه معاً. والوسمُ يأتي من **القرص** يكتبه
 *    سكربتُ السحب، لا من نداءٍ يمرّ بهذا التطبيق.
 * 2. **ولا حذفَ لغير المسحوب** (قرارُ المالك ٢): الجدولُ يقول ذلك كي لا يظنّ
 *    المشرفُ أن «الاحتفاظ ٧» يعني أن الثامنةَ ضاعت.
 * 3. **وتصديرُ التقارير ليس نسخةً احتياطية**: من ظنّ CSV نسخةً يكتشف يومَ
 *    الكارثة أن ما بيده أرقامٌ بلا كلمات مرورٍ ولا مستنداتٍ ولا دفتر.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  backupDownloadToken,
  getBackupState,
  runBackupNow,
  updateBackupSettings,
, backupDownloadUrl } from "@/api/endpoints";
import type { BackupRow, BackupState } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Feedback";
import { moment } from "@/lib/format";
import { digits } from "@/lib/utils";

function size(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${digits((bytes / 1024 ** 3).toFixed(1))} غ.ب`;
  if (bytes >= 1024 ** 2) return `${digits((bytes / 1024 ** 2).toFixed(1))} م.ب`;
  return `${digits(Math.max(1, Math.round(bytes / 1024)).toString())} ك.ب`;
}

/** **ترتيبُ `date.weekday()` في بايثون: الاثنينُ صفر** — لا الأحد. وقائمةٌ
 *  ترتيبُها غيرُ ترتيبِ ما يقرؤه الخادم تأخذ النسخةَ في يومٍ غير المختار. */
const WEEKDAYS = [
  "الاثنين",
  "الثلاثاء",
  "الأربعاء",
  "الخميس",
  "الجمعة",
  "السبت",
  "الأحد",
];

export function Backups({
  onError,
  onDone,
}: {
  onError: (message: string) => void;
  onDone: (message: string) => void;
}) {
  const [state, setState] = useState<BackupState | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => setState(await getBackupState()), []);

  useEffect(() => {
    load().catch((caught) =>
      onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة النسخ"),
    );
  }, [load, onError]);

  if (state === null) return <Spinner />;

  return (
    <div className="space-y-20">
      {/* ------------------------------------------------------ التنبيهات */}
      {state.stale_hours !== null ||
      state.unpulled !== null ||
      state.disk_percent !== null ? (
        <div className="rounded-13 border border-warn-brd bg-warn-soft p-14 text-12.5 text-ink">
          {state.stale_hours !== null ? (
            <p>
              ⚠️ مضى <b>{digits(String(state.stale_hours))} ساعةً</b> بلا نسخةٍ
              ناجحة.
            </p>
          ) : null}
          {state.unpulled !== null ? (
            <p>
              ⚠️ تراكمت <b>{digits(String(state.unpulled))} نسخٍ لم تُسحب</b> إلى
              جهازك — ونسخةٌ على الخادم وحدَه ليست نسخةً احتياطية.
            </p>
          ) : null}
          {state.disk_percent !== null ? (
            <p>
              ⚠️ بلغت مساحةُ النسخ{" "}
              <b>{digits(String(state.disk_percent))}٪</b> من سقفها —{" "}
              <b>ولا يُحذف شيءٌ بموجبها</b>.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* ---------------------------------------------------------- الأخذ */}
      <section>
        <div className="mb-10 flex flex-wrap items-center justify-between gap-10">
          <div>
            <h2 className="text-15 font-bold text-ink">النسخ الاحتياطي</h2>
            <p className="mt-2 text-11.5 text-muted">
              آخرُ نسخةٍ ناجحة:{" "}
              {state.last_success_at ? moment(state.last_success_at) : "لا توجد"} ·
              الإجمالي {size(state.total_bytes)}
            </p>
          </div>
          <Button
            size="sm"
            loading={busy}
            onClick={() => {
              setBusy(true);
              runBackupNow()
                .then((row) => {
                  onDone(`أُخذت النسخة ${row.name}`);
                  return load();
                })
                .catch((caught) =>
                  onError(
                    caught instanceof ApiError ? caught.message : "تعذّر أخذ النسخة",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            نسخة احتياطية الآن
          </Button>
        </div>

        <p className="mb-10 rounded-13 border border-line p-12 text-11.5 leading-relaxed text-muted">
          <b className="text-ink">مفتاحُ التشفير ليس في الأرشيف</b> — بقصد. فاستعادةٌ
          بلا مفتاح Fernet تُنتج نظاماً يعمل <b className="text-ink">بعقودِ مزوّدين لا
          تُقرأ</b>، يُدخلها المشرفُ من جديد ولا يفقد غيرَها. وعبارةُ فكِّ تشفير
          الأرشيف تسكن حيث يسكن ذلك المفتاح.{" "}
          <b className="text-ink">وتصديرُ التقارير ليس نسخةً احتياطية</b>: الاستعادةُ
          منه مستحيلة.
        </p>

        {state.backups.length === 0 ? (
          <p className="rounded-13 border border-line p-14 text-12.5 text-muted">
            لا نسخَ على الخادم بعد.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-13 border border-line">
            <table className="w-full min-w-[720px] text-12.5">
              <thead>
                <tr className="border-b border-line bg-surface-2 text-muted">
                  <th className="p-8 text-start font-semibold">النسخة</th>
                  <th className="p-8 text-start font-semibold">التاريخ</th>
                  <th className="p-8 text-start font-semibold">الحجم</th>
                  <th className="p-8 text-start font-semibold">الترحيلة</th>
                  <th className="p-8 text-start font-semibold">سُحبت؟</th>
                  <th className="p-8 text-start font-semibold">تنزيل</th>
                </tr>
              </thead>
              <tbody>
                {state.backups.map((row) => (
                  <Row key={row.name} row={row} onError={onError} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ------------------------------------------------------- الجدولة */}
      <SettingsForm
        state={state}
        onSaved={(message) => {
          onDone(message);
          void load();
        }}
        onError={onError}
      />
    </div>
  );
}

function Row({
  row,
  onError,
}: {
  row: BackupRow;
  onError: (message: string) => void;
}) {
  const [asking, setAsking] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const file = row.encrypted ? "db.dump.gpg" : "db.dump";

  return (
    <tr className="border-b border-line last:border-0">
      <td className="p-8 font-medium text-ink" dir="ltr">
        {row.name}
        {row.encrypted ? (
          <span className="ms-6 text-11 text-ok">مشفَّرة</span>
        ) : (
          <span className="ms-6 text-11 text-warn">غير مشفَّرة</span>
        )}
      </td>
      <td className="p-8 text-muted">
        {row.taken_at ? moment(row.taken_at) : "—"}
      </td>
      <td className="p-8 text-ink">{size(row.size_bytes)}</td>
      <td className="p-8 text-muted" dir="ltr">
        {row.alembic_revision ?? "—"}
      </td>
      <td className="p-8">
        {/* **«لم تُسحب» تحذيرٌ لا حياد**: قرصٌ واحدٌ يحمل النظامَ ونسختَه معاً */}
        <Badge tone={row.pulled ? "ok" : "warn"}>
          {row.pulled ? "سُحبت" : "لم تُسحب"}
        </Badge>
      </td>
      <td className="p-8">
        {asking ? (
          <div className="flex items-center gap-6">
            <Field
              label=""
              type="password"
              placeholder="كلمة مرورك"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <Button
              size="sm"
              loading={busy}
              disabled={password === ""}
              onClick={() => {
                setBusy(true);
                backupDownloadToken(row.name, password, file)
                  .then(({ token }) => {
                    // **رابطٌ لمرةٍ واحدةٍ ينتهي بعد خمس دقائق** — يُفتح فوراً
                    window.location.href = backupDownloadUrl(token);
                    setAsking(false);
                    setPassword("");
                  })
                  .catch((caught) =>
                    onError(
                      caught instanceof ApiError ? caught.message : "تعذّر التنزيل",
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              تأكيد
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setAsking(true)}>
            نزّل القاعدة
          </Button>
        )}
      </td>
    </tr>
  );
}

function SettingsForm({
  state,
  onSaved,
  onError,
}: {
  state: BackupState;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
}) {
  const s = state.settings;
  const [enabled, setEnabled] = useState(s.enabled);
  const [frequency, setFrequency] = useState(s.frequency);
  // **يومُ الأسبوع**: كان بلا خانةٍ منذ بُني، و«أسبوعياً» يُختار بلا يوم —
  // فيُقرأ `weekday is None` في `backups.due` **فلا تُؤخذ نسخةٌ أبداً**. جدولةٌ
  // تبدو مضبوطةً في الشاشة ولا تعمل، ولا شيءَ يفشل حتى يوم الاستعادة.
  //
  // والافتراضُ **السبت** لا صفرٌ صامت: من بدّل إلى «أسبوعياً» يجب أن يرى يوماً
  // مختاراً يصحّحه، لا خانةً فارغةً يمرّ عليها
  const [weekday, setWeekday] = useState(String(s.weekday ?? 6));
  const [hour, setHour] = useState(String(s.hour_local));
  const [keep, setKeep] = useState(String(s.keep_count));
  const [staleHours, setStaleHours] = useState(String(s.alert_after_hours));
  const [unpulled, setUnpulled] = useState(String(s.alert_unpulled_count));
  // **فارغٌ يعني «لا سقف»** — كسائر السقوف في هذا المشروع، ويُكتب صراحةً
  const [maxBytes, setMaxBytes] = useState(
    s.max_bytes === null ? "" : String(s.max_bytes),
  );
  const [busy, setBusy] = useState(false);

  return (
    <section>
      <h2 className="mb-4 text-15 font-bold text-ink">الجدولة والاحتفاظ</h2>
      <p className="mb-10 text-11.5 leading-relaxed text-muted">
        الساعةُ <b className="text-ink">بتوقيت الأردن</b> لا بتوقيت الخادم.
        و<b className="text-ink">عددُ المحفوظات يقع على المسحوبة وحدَها</b>: ما لم
        تسحبه لا يُحذف مهما بلغ عددُه — يُنبَّه عنه فقط. فالخطأ غيرُ متماثل: قرصٌ
        يمتلئ يُصلَح بأمر، ونسخةٌ حُذفت ولم يملكها أحدٌ لا تعود.
      </p>

      <div className="grid gap-10 md:grid-cols-3">
        <Checkbox checked={enabled} onChange={setEnabled}>
          الجدولة مفعّلة
        </Checkbox>
        <Select
          label="التكرار"
          value={frequency}
          onChange={(event) => setFrequency(event.target.value)}
        >
          <option value="daily">يومياً</option>
          <option value="weekly">أسبوعياً</option>
        </Select>
        {frequency === "weekly" ? (
          <Select
            label="يومُ الأسبوع"
            value={weekday}
            onChange={(event) => setWeekday(event.target.value)}
          >
            {WEEKDAYS.map((label, index) => (
              <option key={label} value={String(index)}>
                {label}
              </option>
            ))}
          </Select>
        ) : null}
        <Field
          label="الساعة (بتوقيت الأردن)"
          dir="ltr"
          inputMode="numeric"
          value={hour}
          onChange={(event) => setHour(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <Field
          label="عدد المحفوظات (المسحوبة)"
          dir="ltr"
          inputMode="numeric"
          value={keep}
          onChange={(event) => setKeep(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <Field
          label="تنبيه بعد كم ساعة بلا نسخة"
          dir="ltr"
          inputMode="numeric"
          value={staleHours}
          onChange={(event) =>
            setStaleHours(event.target.value.replace(/[^0-9]/g, ""))
          }
        />
        <Field
          label="تنبيه إن تجاوز حجمُ النسخة (بايت — فارغ = لا سقف)"
          dir="ltr"
          inputMode="numeric"
          value={maxBytes}
          onChange={(event) =>
            setMaxBytes(event.target.value.replace(/[^0-9]/g, ""))
          }
        />
        <Field
          label="تنبيه عند كم نسخةٍ لم تُسحب"
          dir="ltr"
          inputMode="numeric"
          value={unpulled}
          onChange={(event) =>
            setUnpulled(event.target.value.replace(/[^0-9]/g, ""))
          }
        />
      </div>

      <Button
        className="mt-14"
        size="sm"
        loading={busy}
        disabled={hour === "" || keep === ""}
        onClick={() => {
          setBusy(true);
          updateBackupSettings({
            enabled,
            frequency,
            // **ويُرسل مع «أسبوعياً» وحدَها**: يومٌ على جدولةٍ يومية قيمةٌ لا
            // تُقرأ، وحفظُها يجعل تبديلاً لاحقاً يرث اختياراً لم يره أحد
            ...(frequency === "weekly" ? { weekday: Number(weekday) } : {}),
            hour_local: Number(hour),
            keep_count: Number(keep),
            alert_after_hours: Number(staleHours),
            alert_unpulled_count: Number(unpulled),
            max_bytes: maxBytes === "" ? null : Number(maxBytes),
          })
            .then(() => onSaved("حُفظت جدولةُ النسخ"))
            .catch((caught) =>
              onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </section>
  );
}
