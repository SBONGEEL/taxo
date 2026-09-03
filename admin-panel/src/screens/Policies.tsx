/** السياساتُ والشروط — **البند ١٠ (§39٫١٠، §34، §45)**.
 *
 * **والجداولُ نامت منذ `0060` بلا شاشةٍ ولا باب**، وسُدَّ شكلُها في `0068`.
 * وهذه أوّلُ يدٍ تكتب فيها.
 *
 * ## ثلاثةٌ في هذه الشاشة مقصودة
 *
 * **١) لا حقلَ يُحرَّر فوق نفسه** — كلُّ حفظٍ نسخةٌ جديدةٌ برقمٍ أعلى.
 * **والعلّةُ بنصِّ المالك**: «لو بقيت التصحيحاتُ على النسخة نفسِها لصار تصحيحُ
 * فاصلةٍ قادراً على تغيير معنى نصٍّ وافق عليه الناسُ بلا أثر». **فالمحرِّرُ
 * يفتح بنصِّ آخر نسخةٍ ليُكمَل عليه**، ويحفظ نسخةً جديدة.
 *
 * **٢) والنشرُ فعلٌ ثانٍ يستأذن** — يسمّي الوثيقةَ والسوقَ والتطبيق، **ويقول
 * ماذا سيُنزع**. ونشرٌ يقع بضغطةِ حفظٍ يجعل الكاتبَ يخاف القلم.
 *
 * **٣) وزرُّ الحذف يُرسم معطَّلاً بعلّته** لا يُرسم ثمّ يرتدّ: منشورةٌ أو وافق
 * عليها أحد **لا تُحذف** — والخلفيةُ ترفض بالعربية، **والشاشةُ تقول لماذا قبل
 * أن يُضغط**.
 */

import { useCallback, useEffect, useState } from "react";

import {
  createPolicyVersion,
  deletePolicyDraft,
  getOrgProfile,
  listPolicies,
  publishPolicy,
  saveOrgProfile,
  withdrawPolicy,
} from "@/api/endpoints";
import type {
  OrgProfile,
  PolicyApp,
  PolicyDocType,
  PolicyVersion,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDelete } from "@/components/ui/ConfirmDelete";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { moment } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const DOC_LABEL: Record<PolicyDocType, string> = {
  privacy_policy: "سياسة الخصوصية",
  terms_of_use: "شروط الاستخدام",
};

const APP_LABEL: Record<PolicyApp, string> = {
  rider: "تطبيق الراكب",
  driver: "تطبيق الكبتن",
};

const COLUMNS = "0.8fr 0.5fr 0.6fr 0.7fr 0.9fr 0.9fr";

export function PoliciesScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [docType, setDocType] = useState<PolicyDocType>("privacy_policy");
  const [app, setApp] = useState<PolicyApp>("rider");
  const [rows, setRows] = useState<PolicyVersion[] | null>(null);
  const [org, setOrg] = useState<OrgProfile | null>(null);
  const [writing, setWriting] = useState<string | null>(null);
  const [reconsent, setReconsent] = useState(false);
  const [publishing, setPublishing] = useState<PolicyVersion | null>(null);
  const [removing, setRemoving] = useState<PolicyVersion | null>(null);
  const [reading, setReading] = useState<PolicyVersion | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const form = useFormError();

  const load = useCallback(async () => {
    setRows(await listPolicies({ country_code: country, doc_type: docType, app }));
  }, [country, docType, app]);

  useEffect(() => {
    load().catch((caught) => form.capture(caught, "تعذّرت قراءة الوثائق"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    getOrgProfile()
      .then(setOrg)
      .catch((caught) => form.capture(caught, "تعذّر قراءة بيان الجهة"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const live = rows?.find((row) => row.is_published) ?? null;

  /** **يفتح المحرِّرَ بنصِّ آخر نسخة** — فالتصحيحُ إكمالٌ لا كتابةٌ من الصفر. */
  function beginWriting() {
    form.setMessage(null);
    setDone(null);
    setReconsent(false);
    setWriting(rows?.[0]?.body_ar ?? "");
  }

  async function save() {
    if (writing === null) return;
    setBusy(true);
    form.setMessage(null);
    try {
      const created = await createPolicyVersion({
        country_code: country,
        doc_type: docType,
        app,
        body_ar: writing,
        requires_reconsent: reconsent,
      });
      setDone(
        `حُفظت النسخة ${created.version} من ${DOC_LABEL[docType]} لـ${APP_LABEL[app]} — مسوّدةً، ولم تُنشر بعد.`,
      );
      setWriting(null);
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  async function doPublish(row: PolicyVersion) {
    setBusy(true);
    form.setMessage(null);
    try {
      await publishPolicy(row.id);
      setDone(
        live === null
          ? `نُشرت النسخة ${row.version} — وصارت هي الواجبة.`
          : `نُشرت النسخة ${row.version}، وأُطفئت ${live.version}.`,
      );
      setPublishing(null);
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر النشر");
      setPublishing(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
      <Shell
        title="السياسات والشروط"
        subtitle="نصٌّ في القاعدة لا في الحزمة — وكلُّ حفظٍ نسخةٌ جديدة، ولا يُحرَّر ما وافق عليه أحد"
      >
        <ErrorNote message={form.message} />
        <SuccessNote message={done} />

        <div className="mb-14 grid grid-cols-2 gap-12">
          <Select
            label="الوثيقة"
            name="doc_type"
            value={docType}
            onChange={(event) =>
              setDocType(event.target.value as PolicyDocType)
            }
          >
            {(Object.keys(DOC_LABEL) as PolicyDocType[]).map((key) => (
              <option key={key} value={key}>
                {DOC_LABEL[key]}
              </option>
            ))}
          </Select>
          <Select
            label="التطبيق"
            name="policy_app"
            value={app}
            onChange={(event) => setApp(event.target.value as PolicyApp)}
          >
            {(Object.keys(APP_LABEL) as PolicyApp[]).map((key) => (
              <option key={key} value={key}>
                {APP_LABEL[key]}
              </option>
            ))}
          </Select>
        </div>

        <p className="mb-14 rounded-13 border border-line bg-surface-2 px-14 py-11 text-11.5 leading-note text-muted">
          {live
            ? `المنشورةُ الآن: النسخة ${digits(String(live.version))} — ومن وافق على ${digits(String(live.min_accepted_version))} أو ما بعدها فقد وافق على ما يكفي.`
            : "لا نسخةَ منشورةً لهذه الوثيقة في هذا السوق — ولا يُسأل أحدٌ عن قبولها بعد."}
        </p>

        {isAdmin ? (
          <Button className="mb-14" size="md" onClick={beginWriting}>
            اكتب نسخةً جديدة
          </Button>
        ) : null}

        <Table<PolicyVersion>
          columns={COLUMNS}
          headers={["النسخة", "الحال", "تُبرئ من", "وافق عليها", "حُفظت", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا نسخةَ بعد",
            hint: "اكتب الأولى — تولد مسوّدةً، والنشرُ فعلٌ ثانٍ.",
          }}
          render={(row) => (
            <>
              <span className="text-12.5 text-ink" dir="ltr">
                {digits(String(row.version))}
              </span>
              <span>
                {row.is_published ? (
                  <Badge tone="ok">منشورة</Badge>
                ) : (
                  <Badge tone="muted">مسوّدة</Badge>
                )}
              </span>
              <span className="text-12 text-muted" dir="ltr">
                {digits(String(row.min_accepted_version))}
              </span>
              <span className="text-12 text-muted">
                {digits(String(row.consents))}
              </span>
              <span className="text-11.5 text-muted">
                {moment(row.created_at)}
              </span>
              <span className="flex justify-end gap-7">
                <Button size="sm" variant="ghost" onClick={() => setReading(row)}>
                  اقرأ
                </Button>
                {isAdmin && !row.is_published ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setPublishing(row)}
                  >
                    انشُر
                  </Button>
                ) : null}
                {/* **بابُ الرجوع** — ومن نشر في سوقٍ لم يُفتح بعد كان لا يملك
                    إلا أن ينشر فوقه غيرَه */}
                {isAdmin && row.is_published ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      setBusy(true);
                      withdrawPolicy(row.id)
                        .then(() => {
                          setDone(
                            `سُحبت النسخة ${row.version} — ولا وثيقةَ قائمةً الآن، ونصُّها باقٍ.`,
                          );
                          return load();
                        })
                        .catch((caught) => form.capture(caught, "تعذّر السحب"))
                        .finally(() => setBusy(false));
                    }}
                  >
                    اسحب النشر
                  </Button>
                ) : null}
                {isAdmin ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={row.is_published || row.consents > 0}
                    onClick={() => setRemoving(row)}
                  >
                    احذف
                  </Button>
                ) : null}
              </span>
            </>
          )}
        />

        {/* **بيانُ الجهة** — تقرؤه الوثيقةُ نفسُها، **وفراغُه حالٌ صحيحة** */}
        <section className="mt-22 rounded-16 border border-line bg-surface p-18">
          <h2 className="mb-4 text-16 font-bold text-ink">بيان الجهة</h2>
          <p className="mb-14 text-11 leading-note text-muted">
            صفٌّ واحدٌ لا صفٌّ لكلِّ سوق — يُذكر في نصِّ الوثيقتين، ومنه يعرف
            القارئُ بمن يتّصل.
          </p>
          <div className="grid grid-cols-3 gap-12">
            <Field
              label="الاسم القانونيّ"
              name="legal_name"
              value={org?.legal_name ?? ""}
              disabled={!isAdmin}
              onChange={(event) =>
                setOrg({ ...(org ?? emptyOrg()), legal_name: event.target.value })
              }
            />
            <Field
              label="العنوان"
              name="address"
              value={org?.address ?? ""}
              disabled={!isAdmin}
              onChange={(event) =>
                setOrg({ ...(org ?? emptyOrg()), address: event.target.value })
              }
            />
            <Field
              label="بريد الخصوصية"
              name="privacy_email"
              dir="ltr"
              value={org?.privacy_email ?? ""}
              disabled={!isAdmin}
              onChange={(event) =>
                setOrg({
                  ...(org ?? emptyOrg()),
                  privacy_email: event.target.value,
                })
              }
            />
          </div>
          {isAdmin ? (
            <Button
              className="mt-14"
              size="md"
              disabled={busy || org === null}
              onClick={() => {
                if (!org) return;
                setBusy(true);
                saveOrgProfile(org)
                  .then((saved) => {
                    setOrg(saved);
                    setDone("حُفظ بيان الجهة.");
                  })
                  .catch((caught) => form.capture(caught, "تعذّر الحفظ"))
                  .finally(() => setBusy(false));
              }}
            >
              احفظ بيان الجهة
            </Button>
          ) : null}
        </section>

        {writing !== null ? (
          <Modal title="نسخةٌ جديدة" onClose={() => setWriting(null)}>
            <p className="mb-10 text-11.5 leading-note text-muted">
              {DOC_LABEL[docType]} · {APP_LABEL[app]} — تُحفظ **مسوّدة**، ولا
              تُنشر إلا بفعلٍ ثانٍ. والنصُّ مفتوحٌ على آخر نسخةٍ لتُكمل عليها.
            </p>
            <textarea
              name="body_ar"
              rows={16}
              value={writing}
              onChange={(event) => setWriting(event.target.value)}
              className="w-full rounded-13 border border-line bg-surface-2 px-13 py-11 text-12.5 leading-note text-ink"
            />
            <div className="mt-12">
              <Checkbox checked={reconsent} onChange={setReconsent}>
                تغييرٌ جوهريّ — يُسأل من وافق سابقاً من جديد
              </Checkbox>
              <p className="mt-6 text-11 leading-note text-muted">
                تصحيحُ فاصلةٍ لا يُعيد سؤالَ الناس، وتغييرٌ جوهريٌّ بلا إعادةِ
                سؤالٍ يجعل الموافقةَ القديمةَ دعوى.
              </p>
            </div>
            <div className="mt-16 flex gap-10">
              <Button
                size="md"
                disabled={busy || writing.trim().length === 0}
                onClick={() => void save()}
              >
                احفظ مسوّدة
              </Button>
              <Button size="md" variant="ghost" onClick={() => setWriting(null)}>
                إلغاء
              </Button>
            </div>
          </Modal>
        ) : null}

        {reading ? (
          <Modal
            title={`${DOC_LABEL[reading.doc_type]} · النسخة ${digits(String(reading.version))}`}
            onClose={() => setReading(null)}
          >
            <p className="whitespace-pre-line text-12.5 leading-note text-ink">
              {reading.body_ar}
            </p>
          </Modal>
        ) : null}

        {publishing ? (
          <Modal title="تأكيدُ النشر" onClose={() => setPublishing(null)}>
            <p className="text-12.5 leading-note text-ink">
              ستصير النسخة{" "}
              <b dir="ltr">{digits(String(publishing.version))}</b> من{" "}
              <b>{DOC_LABEL[publishing.doc_type]}</b> لـ
              <b>{APP_LABEL[publishing.app]}</b> هي النصَّ القائم.
            </p>
            <p className="mt-8 text-11.5 leading-note text-muted">
              {live
                ? `وتُطفأ النسخة ${digits(String(live.version))} — ويبقى نصُّها شاهداً على من وافق عليه.`
                : "ولا نسخةَ منشورةً قبلها في هذا السوق."}
              {publishing.requires_reconsent
                ? " وهذه النسخةُ تطلب موافقةً جديدةً ممّن وافق سابقاً."
                : " ولا يُسأل من وافق سابقاً من جديد."}
            </p>
            <div className="mt-16 flex gap-10">
              <Button
                size="md"
                disabled={busy}
                onClick={() => void doPublish(publishing)}
              >
                انشُرها
              </Button>
              <Button
                size="md"
                variant="ghost"
                onClick={() => setPublishing(null)}
              >
                تراجُع
              </Button>
            </div>
          </Modal>
        ) : null}

        {removing ? (
          <ConfirmDelete
            what={`النسخة ${removing.version} من ${DOC_LABEL[removing.doc_type]} لـ${APP_LABEL[removing.app]}`}
            note="ولا تُحذف إلا مسوّدةٌ لم يوافق عليها أحد — والخادمُ يرفض غيرَها ويقول السبب."
            onConfirm={async () => {
              await deletePolicyDraft(removing.id);
              setDone(`حُذفت مسوّدةُ النسخة ${removing.version}.`);
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

function emptyOrg(): OrgProfile {
  return { legal_name: null, address: null, privacy_email: null };
}
