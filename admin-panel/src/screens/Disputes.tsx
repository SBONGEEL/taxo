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
 *
 * **وبلغة TAXO 2.0** (A07 · A07b): الجدولُ من العُدّة، والفصلُ حوارُها (`Modal`) — **والزرّان كما كانا**: حكمان نهائيّان
 * بعرضين متساويين، «لم يصل» بلون الخطر. **ولا تأكيدَ يُضاف ولا يُنزع**: الحوارُ نفسُه هو التأكيد.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listPayments, resolveDispute } from "@/api/endpoints";
import type { DisputeResolution, Payment } from "@/api/types";
import { PaymentParties } from "@/components/profile/PaymentParties";
import { Shell } from "@/components/Shell";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { Table, TableSearch } from "@/components/Table";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { cn, digits,
  DISPLAY_LOCALE,
} from "@/lib/utils";

/** نصُّ السبب الذي تكتبه المهمة الدورية — مطابقٌ لـ`AUTO_DISPUTE_REASON`. */
const AUTO_REASON = "انقضت مهلة تأكيد الحوالة دون ردّ الكبتن";

function when(iso: string | null): string {
  if (!iso) return "—";
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }))}`;
}

export function DisputesScreen() {
  // مبدّلُ الدولة في الرأس وعدٌ لكل شاشة — وشاشةٌ تتجاهله تعرض على مشرف
  // السوق الليبي نزاعاتٍ أردنية
  const { country } = useCountry();
  const [rows, setRows] = useState<Payment[] | null>(null);
  const [open, setOpen] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const search = useSearch();

  const load = useCallback(async () => {
    setRows(null);
    setRows(await listPayments("disputed", country, search.term));
  }, [country, search.term]);

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

      <div className={cn("ad-disputes-table", (error || done) && "mt-12")}>
        <Table
          toolbar={
            <TableSearch
              value={search.text}
              onChange={search.setText}
              placeholder="اسمُ الراكب أو الكبتن، أو رقمُ أحدهما…"
            />
          }
          searching={search.searching}
          noResults={NO_RESULTS}
          columns="1fr 1.2fr 1.6fr 1.2fr 1fr 1fr"
          headers={["المبلغ", "الطرفان", "السبب", "مرجع الحوالة", "فُتح", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا نزاعات مفتوحة",
            hint: "يظهر هنا كل نزاعٍ ينتظر قراراً — من كبتن أو من انقضاء مهلة.",
          }}
          render={(row) => (
            <>
              <span className="ad-fare">{digits(row.amount)}</span>
              {/* **ومن يفصل نزاعاً يحتاج الطرفين لا أحدَهما** — §39٫١٢٫٤،
                  والبيتُ واحدٌ مع شاشة المدفوعات لأن البابَ واحد */}
              <PaymentParties payment={row} />
              <span className="ad-reason">
                <span className="ad-reason-main">{row.dispute_reason ?? "—"}</span>
                {row.dispute_reason === AUTO_REASON ? (
                  <span className="ad-reason-sub">
                    آليّ — لم يتّهم أحدٌ أحداً، الكبتن لم يردّ حتى انقضت المهلة
                  </span>
                ) : (
                  <span className="ad-reason-sub">من الكبتن</span>
                )}
              </span>
              <span dir="ltr" className="ad-ltr ad-tone-muted">
                {row.cliq_transfer_reference ?? "—"}
              </span>
              <span className="ad-tone-muted">{when(row.disputed_at)}</span>
              <span className="ad-row-end">
                <Button size="sm" variant="secondary" onClick={() => setOpen(row)}>
                  الفصل
                </Button>
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
      <Modal title="فصل النزاع" onClose={onClose}>
        <p className="ad-modal-lede">
          الحكمُ يصف الواقعة لا الحالة: «وصل المال» تجعل الدفعة مؤكدةً ويُقيَّد
          ما يقيَّد، و«لم يصل» تجعلها فاشلة. وكلاهما نهائي ويدخل سجل التدقيق.
        </p>

        <dl className="ad-resolve-dl">
          <Row label="المبلغ" value={digits(payment.amount)} />
          <Row label="alias الكبتن" value={payment.cliq_alias ?? "—"} ltr />
          <Row label="مرجع TAXO" value={payment.cliq_reference ?? "—"} ltr />
          <Row
            label="المرجع الذي أدخله الراكب"
            value={payment.cliq_transfer_reference ?? "—"}
            ltr
          />
        </dl>

        <p className="ad-resolve-reason">
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

        <div className="ad-modal-actions ad-modal-split">
          <Button
            size="md"
            loading={busy === "paid"}
            disabled={busy !== null}
            onClick={() => decide("paid")}
          >
            وصل المال — لصالح الكبتن
          </Button>
          <Button
            size="md"
            variant="danger"
            loading={busy === "unpaid"}
            disabled={busy !== null}
            onClick={() => decide("unpaid")}
          >
            لم يصل — لصالح الراكب
          </Button>
        </div>
      </Modal>
    </FormErrors>
  );
}

function Row({
  label,
  value,
  ltr = false,
}: {
  label: string;
  value: string;
  ltr?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd dir={ltr ? "ltr" : undefined}>{value}</dd>
    </div>
  );
}
