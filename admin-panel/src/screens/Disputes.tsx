/** النزاعات والدعم — SPEC القسم 13/4 و6.2، و`DESIGN.md` §3.3.
 *
 * **نزاعُ كليك وحده يصل هنا**: الكاش يقع يداً بيد فلا فراغَ فيه، والمحفظةُ
 * يشهد عليها الدفتر — والتحويلُ وحده يقع خارج التطبيق بلا API يشهد عليه، فبين
 * قول الراكب «حوّلتُ» وقول الكبتن «لم يصلني» فراغٌ يملؤه إنسان. وهذه الشاشة
 * هي ذلك الإنسان.
 *
 * **ومصدران للنزاع لا واحد**: كبتنٌ ضغط «لم تصلني»، أو **مهلةٌ انقضت** فحوّلته
 * المهمةُ الدورية آلياً (القسم 6.2/6). والثاني يحمل سبباً ثابتاً تعرفه الشاشة،
 * فتقول للمشرف إن أحداً لم يتّهم أحداً — الكبتن لم يفتح تطبيقه فحسب. والفرقُ
 * يغيّر السؤال الذي يبدأ به المشرف.
 *
 * **والحكمُ يصف الواقعة لا الحالة الناتجة**: `paid` = «وصل المال» فتصير
 * الدفعة `confirmed` ويُقيَّد ما يقيَّد، و`unpaid` = «لم يصل» فتصير `failed`.
 * والاشتقاقُ في الخلفية في مكانٍ واحد.
 *
 * **والفصلُ متاحٌ لـ`support`** خلافاً لبقية اللوحة: القسم 13/8 يعطيه «قراءة
 * ومعالجة نزاعات» — وهو الدور الذي وُجد لهذا.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listPayments, resolveDispute } from "@/api/endpoints";
import type { DisputeResolution, Payment } from "@/api/types";
import { Shell } from "@/components/Shell";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { arabicDigits } from "@/lib/utils";

/** نصُّ السبب الذي تكتبه المهمة الدورية — مطابقٌ لـ`AUTO_DISPUTE_REASON`. */
const AUTO_REASON = "انقضت مهلة تأكيد الحوالة دون ردّ الكبتن";

function when(iso: string | null): string {
  if (!iso) return "—";
  const at = new Date(iso);
  return `${at.toLocaleDateString("ar-EG", { day: "numeric", month: "long" })} ${at.toLocaleTimeString("ar-EG", { hour: "numeric", minute: "2-digit" })}`;
}

export function DisputesScreen() {
  // مبدّلُ الدولة في الرأس وعدٌ لكل شاشة — وشاشةٌ تتجاهله تعرض على مشرف
  // السوق الليبي نزاعاتٍ أردنية
  const { country } = useCountry();
  const [rows, setRows] = useState<Payment[] | null>(null);
  const [open, setOpen] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(await listPayments("disputed", country));
  }, [country]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة النزاعات",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="النزاعات والدعم"
      subtitle="حوالاتُ كليك التي لم تُؤكَّد — بقول الكبتن أو بانقضاء المهلة"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className="mt-12">
        <Table
          columns="1fr 1.6fr 1.2fr 1fr 1fr"
          headers={["المبلغ", "السبب", "مرجع الحوالة", "فُتح", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا نزاعات مفتوحة",
            hint: "يظهر هنا كل نزاعٍ ينتظر قراراً — من كبتن أو من انقضاء مهلة.",
          }}
          render={(row) => (
            <>
              <span className="font-semibold text-ink">
                {arabicDigits(row.amount)}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-ink">
                  {row.dispute_reason ?? "—"}
                </span>
                {row.dispute_reason === AUTO_REASON ? (
                  <span className="block text-10.5 text-muted">
                    آليّ — لم يتّهم أحدٌ أحداً، الكبتن لم يردّ حتى انقضت المهلة
                  </span>
                ) : (
                  <span className="block text-10.5 text-muted">من الكبتن</span>
                )}
              </span>
              <span dir="ltr" className="text-start text-muted">
                {row.cliq_transfer_reference ?? "—"}
              </span>
              <span className="text-muted">{when(row.disputed_at)}</span>
              <span className="flex justify-end">
                <button
                  type="button"
                  onClick={() => setOpen(row)}
                  className="text-11.5 font-semibold text-ink underline"
                >
                  الفصل
                </button>
              </span>
            </>
          )}
        />
      </div>

      {open ? (
        <ResolveModal
          payment={open}
          onClose={() => setOpen(null)}
          onResolved={(message) => {
            setOpen(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}

function ResolveModal({
  payment,
  onClose,
  onResolved,
}: {
  payment: Payment;
  onClose: () => void;
  onResolved: (message: string) => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<DisputeResolution | null>(null);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;

  function decide(resolution: DisputeResolution) {
    setBusy(resolution);
    setError(null);
    resolveDispute(payment.id, resolution, note.trim() || undefined)
      .then(() =>
        onResolved(
          resolution === "paid"
            ? "فُصل لصالح الكبتن — الدفعة مؤكدة"
            : "فُصل بأن المال لم يصل — الدفعة فاشلة",
        ),
      )
      .catch((caught) => form.capture(caught, "تعذّر الفصل"))
      .finally(() => setBusy(null));
  }

  return (
    <FormErrors value={form.field}>
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">فصل النزاع</h2>
        <p className="mb-16 text-12 leading-note text-muted">
          الحكمُ يصف الواقعة لا الحالة: «وصل المال» تجعل الدفعة مؤكدةً ويُقيَّد
          ما يقيَّد، و«لم يصل» تجعلها فاشلة. وكلاهما نهائي ويدخل سجل التدقيق.
        </p>

        <dl className="mb-16 rounded-14 border border-line bg-surface-2 px-14 py-12 text-12.5">
          <Row label="المبلغ" value={arabicDigits(payment.amount)} />
          <Row label="alias الكبتن" value={payment.cliq_alias ?? "—"} ltr />
          <Row label="مرجع TAXO" value={payment.cliq_reference ?? "—"} ltr />
          <Row
            label="المرجع الذي أدخله الراكب"
            value={payment.cliq_transfer_reference ?? "—"}
            ltr
            last
          />
        </dl>

        <p className="mb-14 text-11.5 leading-note text-muted">
          {payment.dispute_reason === AUTO_REASON
            ? "فُتح آلياً بانقضاء المهلة: لم ينفِ الكبتن وصول المال، بل لم يردّ. اسأله قبل أن تحكم."
            : `سببُ الكبتن: ${payment.dispute_reason ?? "—"}`}
        </p>

        <Field
          label="ملاحظة الفصل"
          name="note"
          placeholder="تُحفظ مع القرار في السجل"
          value={note}
          maxLength={255}
          onChange={(event) => setNote(event.target.value)}
        />

        <ErrorNote message={error} />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy === "paid"}
            disabled={busy !== null}
            onClick={() => decide("paid")}
          >
            وصل المال — لصالح الكبتن
          </Button>
          <Button
            className="flex-1 border-danger text-danger"
            size="md"
            variant="secondary"
            loading={busy === "unpaid"}
            disabled={busy !== null}
            onClick={() => decide("unpaid")}
          >
            لم يصل — لصالح الراكب
          </Button>
        </div>
      </div>
    </div>
    </FormErrors>
  );
}

function Row({
  label,
  value,
  ltr = false,
  last = false,
}: {
  label: string;
  value: string;
  ltr?: boolean;
  last?: boolean;
}) {
  return (
    <div className={`flex justify-between ${last ? "" : "mb-8"}`}>
      <dt className="text-muted">{label}</dt>
      <dd dir={ltr ? "ltr" : undefined} className="font-semibold text-ink">
        {value}
      </dd>
    </div>
  );
}
