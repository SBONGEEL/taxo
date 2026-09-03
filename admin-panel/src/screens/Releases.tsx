/** لوحةُ الإصدارات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.
 *
 * **أخطرُ شاشةٍ في هذه اللوحة، وليست عن مال**: خطأُ مالٍ يمسّ حساباً، **وخطأُ
 * حدٍّ هنا يوقف كلَّ من حمّل التطبيق دفعةً واحدة**. ولذلك ثلاثةُ أشياءَ فيها
 * مقصودة:
 *
 * ١. **الرقمُ هو `versionCode` لا اسمُ نسخة** — وهو ما تقارن به أندرويد،
 *    و`versionName` ثابتٌ في هذه الشجرة (قِيست حزمتان بـ`1.0` و`1.1`
 *    ورقمُهما `392`). **والشاشةُ تقوله للمشرف بنصِّها** كي لا يكتب `1.2.0`.
 *
 * ٢. **ورفعُ الحدِّ يستأذن مرّتين** — ورقةٌ تسمّي **من سيُقفل**، ثمّ **رقمٌ
 *    يُعاد كتابتُه**. **والثانيةُ مفروضةٌ في الخلفية** لا هنا: العقدُ يرفض بلا
 *    `confirm_min_supported_build`، **فورقةٌ في الشاشة وحدَها راحةٌ لا حماية**.
 *
 * ٣. **والرابطُ يُطرق قبل الحفظ** — في الخلفية كذلك. فما يظهر هنا عند الرفض
 *    **نصُّ الخادم** لا رسالةٌ من عندنا.
 *
 * **ولا حقلَ لرقم الإصدار في التعديل**: الرقمُ هويةُ حزمةٍ موقَّعةٍ في يد
 * الناس، **وتغييرُه يجعل السجلَّ يصف حزمةً غيرَ التي وُصفت** — وهو تزويرُ
 * سجلٍّ لا تصحيحُ حقل. والخطأُ فيه يُصحَّح بحذف الصفِّ وكتابة غيره.
 */

import { useCallback, useEffect, useState } from "react";

import {
  createRelease,
  deleteRelease,
  listReleases,
  updateRelease,
} from "@/api/endpoints";
import type { AppRelease, ClientApp } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDelete } from "@/components/ui/ConfirmDelete";
import { Field, Select } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { moment } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const APP_LABEL: Record<ClientApp, string> = {
  rider: "تطبيق الراكب",
  driver: "تطبيق الكبتن",
  panel: "غلاف المشرف",
};

const COLUMNS = "0.9fr 0.6fr 0.7fr 0.6fr 1.4fr 0.7fr";

interface Draft {
  app: ClientApp;
  build: string;
  min: string;
  url: string;
  notes: string;
  hours: string;
}

const EMPTY: Draft = {
  app: "rider",
  build: "",
  min: "",
  url: "",
  notes: "",
  hours: "24",
};

export function ReleasesScreen() {
  const { isAdmin } = useSession();
  const [rows, setRows] = useState<AppRelease[] | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [editing, setEditing] = useState<AppRelease | null>(null);
  const [removing, setRemoving] = useState<AppRelease | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const form = useFormError();

  const load = useCallback(async () => {
    setRows(await listReleases());
  }, []);

  useEffect(() => {
    load().catch((caught) => form.capture(caught, "تعذّرت قراءة الإصدارات"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  /** **الحدُّ القائم للتطبيق المختار** — منه تُعرف الورقةُ الأولى: هل يرتفع؟ */
  const standing =
    rows?.find((row) => row.app === draft.app && row.is_current)
      ?.min_supported_build ?? 0;
  const rises = Number(draft.min) > standing;
  const ready =
    draft.build.length > 0 &&
    draft.min.length > 0 &&
    draft.url.length > 0 &&
    draft.notes.trim().length > 0;

  function begin() {
    form.setMessage(null);
    setDone(null);
    setTyped("");
    if (rises) {
      setConfirming(true);
      return;
    }
    void save();
  }

  async function save(confirmation?: number) {
    setBusy(true);
    form.setMessage(null);
    const body = {
      app: draft.app,
      build: Number(draft.build),
      min_supported_build: Number(draft.min),
      download_url: draft.url.trim(),
      release_notes: draft.notes.trim(),
      reminder_hours: Number(draft.hours || "24"),
      ...(confirmation === undefined
        ? {}
        : { confirm_min_supported_build: confirmation }),
    };
    try {
      if (editing) {
        await updateRelease(editing.id, body);
        setDone(
          `حُدِّث سجلُّ ${APP_LABEL[draft.app]} — الحدُّ الأدنى الآن ${draft.min}.`,
        );
      } else {
        await createRelease(body);
        setDone(
          `سُجِّل الإصدار ${draft.build} لـ${APP_LABEL[draft.app]}، والحدُّ الأدنى ${draft.min}.`,
        );
      }
      setDraft(EMPTY);
      setEditing(null);
      setConfirming(false);
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
      <Shell
        title="إصدارات التطبيقات"
        subtitle="رقمُ الحزمة، وأدنى ما يُقبل، ورابطُ التحميل — ورفعُ الحدِّ يوقف كلَّ من هو دونه"
      >
        <ErrorNote message={form.message} />
        <SuccessNote message={done} />

        {isAdmin ? (
          <section className="mb-18 rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-16 font-bold text-ink">
              {editing ? "تعديلُ سجلِّ إصدار" : "إصدارٌ جديد"}
            </h2>
            {/* **الرقمُ يُقال للمشرف بنصِّه**: من كتب `1.2.0` كتب رقماً لا
                يعرفه أندرويد، والحزمةُ تُقارَن بـ`versionCode` وحدَه */}
            <p className="mb-14 text-11 leading-note text-muted">
              الرقمُ هو <b className="font-bold">versionCode</b> الحزمة — عددٌ
              صحيحٌ يزيد مع كلِّ بناء، لا «1.2.0». وتقرؤه من بيان الحزم
              (<span dir="ltr">landing/downloads/manifest.json</span>) أو من
              شاشة «حول التطبيق».
            </p>

            <div className="grid grid-cols-2 gap-12">
              <Select
                label="التطبيق"
                name="app"
                value={draft.app}
                disabled={editing !== null}
                onChange={(event) =>
                  setDraft({ ...draft, app: event.target.value as ClientApp })
                }
              >
                {(Object.keys(APP_LABEL) as ClientApp[]).map((key) => (
                  <option key={key} value={key}>
                    {APP_LABEL[key]}
                  </option>
                ))}
              </Select>
              <Field
                label="رقم الإصدار (versionCode)"
                name="build"
                dir="ltr"
                inputMode="numeric"
                value={draft.build}
                disabled={editing !== null}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    build: event.target.value.replace(/\D/g, ""),
                  })
                }
              />
              <Field
                label="أدنى إصدارٍ مقبول"
                name="min_supported_build"
                dir="ltr"
                inputMode="numeric"
                value={draft.min}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    min: event.target.value.replace(/\D/g, ""),
                  })
                }
              />
              <Field
                label="كتمُ التنبيه الاختياريّ (ساعة)"
                name="reminder_hours"
                dir="ltr"
                inputMode="numeric"
                value={draft.hours}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    hours: event.target.value.replace(/\D/g, ""),
                  })
                }
              />
              <div className="col-span-2">
                <Field
                  label="رابط التحميل"
                  name="download_url"
                  dir="ltr"
                  value={draft.url}
                  onChange={(event) =>
                    setDraft({ ...draft, url: event.target.value })
                  }
                />
              </div>
              <div className="col-span-2">
                <label className="mb-6 block text-11.5 text-muted">
                  ما الجديد — يقرؤه صاحبُ الهاتف
                </label>
                <textarea
                  name="release_notes"
                  rows={3}
                  value={draft.notes}
                  onChange={(event) =>
                    setDraft({ ...draft, notes: event.target.value })
                  }
                  className="w-full rounded-13 border border-line bg-surface-2 px-13 py-11 text-12.5 leading-note text-ink"
                />
              </div>
            </div>

            {rises && draft.min ? (
              <p className="mt-12 rounded-13 border border-warn px-13 py-10 text-11.5 leading-note text-warn">
                هذا الحدُّ يوقف كلَّ من حزمتُه أقلُّ من{" "}
                <b dir="ltr">{draft.min}</b> — لا يفتح التطبيقَ حتى يحمّل
                الجديد. وسيُطلب منك تأكيدُ الرقم.
              </p>
            ) : null}

            <div className="mt-16 flex gap-10">
              <Button size="md" disabled={!ready || busy} onClick={begin}>
                {editing ? "حفظ التعديل" : "تسجيل الإصدار"}
              </Button>
              {editing ? (
                <Button
                  size="md"
                  variant="ghost"
                  onClick={() => {
                    setEditing(null);
                    setDraft(EMPTY);
                  }}
                >
                  إلغاء
                </Button>
              ) : null}
            </div>
          </section>
        ) : null}

        <Table<AppRelease>
          columns={COLUMNS}
          headers={[
            "التطبيق",
            "الإصدار",
            "أدنى مقبول",
            "الكتم",
            "ما الجديد",
            "",
          ]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا إصدارَ مسجَّل",
            hint: "ولا شاشةَ تحديثٍ تظهر لأحد — غيابُ السجلِّ يعطّل الحجب لا التطبيق.",
          }}
          render={(row) => (
            <>
              <span className="flex items-center gap-7 text-12.5 text-ink">
                {APP_LABEL[row.app]}
                {row.is_current ? <Badge tone="ok">الحاكم</Badge> : null}
              </span>
              <span className="text-12.5 text-ink" dir="ltr">
                {digits(String(row.build))}
              </span>
              <span className="text-12.5 text-ink" dir="ltr">
                {digits(String(row.min_supported_build))}
              </span>
              <span className="text-11.5 text-muted">
                {digits(String(row.reminder_hours))} ساعة
              </span>
              <span className="truncate text-11.5 text-muted">
                {row.release_notes}
              </span>
              <span className="flex justify-end gap-7">
                {isAdmin ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setEditing(row);
                        setDraft({
                          app: row.app,
                          build: String(row.build),
                          min: String(row.min_supported_build),
                          url: row.download_url,
                          notes: row.release_notes,
                          hours: String(row.reminder_hours),
                        });
                      }}
                    >
                      تعديل
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setRemoving(row)}
                    >
                      حذف
                    </Button>
                  </>
                ) : null}
              </span>
            </>
          )}
        />

        <p className="mt-12 text-11 leading-note text-muted">
          آخرُ تحديثٍ للسجلّ:{" "}
          {rows && rows.length > 0 ? moment(rows[0].updated_at) : "—"}
        </p>

        {/* **الإذنُ الثاني**: رقمٌ يُعاد كتابتُه — والخلفيةُ ترفض بدونه، فهذه
            ورقةٌ تُظهر الشرطَ لا تُنشئه */}
        {confirming ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-dim p-24"
            onClick={() => setConfirming(false)}
          >
            <div
              className="w-full max-w-modal rounded-22 border border-line bg-surface p-22"
              onClick={(event) => event.stopPropagation()}
            >
              <h2 className="text-16 font-bold text-ink">
                تأكيدُ حدٍّ يوقف المستخدمين
              </h2>
              <p className="mt-9 text-12.5 leading-note text-ink">
                كلُّ من حزمتُه أقلُّ من <b dir="ltr">{draft.min}</b> في{" "}
                <b>{APP_LABEL[draft.app]}</b> لن يفتح التطبيقَ حتى يحمّل النسخة
                الجديدة من الرابط أعلاه.
              </p>
              <p className="mt-8 text-11.5 leading-note text-muted">
                أعِد كتابة الرقم لتأكيده — ورقمٌ خاطئٌ هنا يوقف الجميع دفعةً
                واحدة.
              </p>
              <div className="mt-12">
                <Field
                  label="أعِد كتابة الحدّ"
                  name="confirm_min_supported_build"
                  dir="ltr"
                  inputMode="numeric"
                  value={typed}
                  onChange={(event) =>
                    setTyped(event.target.value.replace(/\D/g, ""))
                  }
                />
              </div>
              <div className="mt-16 flex gap-10">
                <Button
                  size="md"
                  disabled={busy || typed !== draft.min}
                  onClick={() => void save(Number(typed))}
                >
                  أوقفهم وأكمل
                </Button>
                <Button
                  size="md"
                  variant="ghost"
                  onClick={() => setConfirming(false)}
                >
                  تراجُع
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {removing ? (
          <ConfirmDelete
            what={`إصدار ${removing.build} من ${APP_LABEL[removing.app]}`}
            note="سجلُّ إصدارٍ إعدادُ تشغيلٍ لا شاهدَ نزاع — ويبقى أثرُه في سجل التدقيق بقيمته قبل الحذف."
            onConfirm={async () => {
              await deleteRelease(removing.id);
              setDone(`حُذف سجلُّ الإصدار ${removing.build}.`);
              setRemoving(null);
              await load();
            }}
            onClose={() => setRemoving(null)}
          />
        ) : null}
      </Shell>
    </FormErrors>
  );
}