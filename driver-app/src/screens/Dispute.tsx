/** فتح نزاع — SPEC القسم 6.2، وشكلُه من `DESIGN.md` §5.3.
 *
 * **على كليك وحدها**، وأسبابُه أسبابُ كليك لا أسبابُ الكاش: الراكب هنا
 * *يقول* إنه حوّل، والحوالةُ إما لم تصل، أو وصلت ناقصةً، أو وصلت باسمٍ لا
 * يطابق ما اتُّفق عليه. أسبابُ التصميم الثلاثة («لم يدفع إطلاقاً»، «نزل
 * وغادر دون دفع») مكتوبةٌ لرحلة كاش لا نزاعَ فيها أصلاً — انحرافٌ مسجّلٌ في
 * `DESIGN-DECISIONS.md`.
 *
 * والسببُ نصٌّ حرّ في الخلفية (`reason: str`, 3–255): فالخياراتُ الثلاثة
 * تُملي النص وحقلُ الملاحظة يُلحق به، ولا يذهب إلى الإدارة رمزٌ بلا كلام.
 *
 * ومرجعُ الحوالة — ما ولّده TAXO وما أدخله الراكب — يُعرض هنا لا زينةً: به
 * يبحث الكبتن في كشف حسابه قبل أن يفتح نزاعاً لم يقع.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { disputePayment, getRide, getRidePayments } from "@/api/endpoints";
import type { Payment, Ride } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import { arabicDigits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

const REASONS = [
  "لم تصلني الحوالة إطلاقاً",
  "وصلتني حوالة أقل من الأجرة",
  "المرجع الذي أدخله الراكب لا يطابق أي حوالة وصلتني",
];

export function DisputeScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const goBack = useGoBack();

  const [ride, setRide] = useState<Ride | null>(null);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [one, paid] = await Promise.all([
      getRide(rideId),
      getRidePayments(rideId),
    ]);
    setRide(one);
    setPayment(
      paid.payments.find(
        (row) => row.method === "cliq" && row.status === "pending",
      ) ?? null,
    );
  }, [rideId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الدفعة",
      ),
    );
  }, [load]);

  async function submit() {
    if (!payment || !reason) return;
    setBusy(true);
    setError(null);
    try {
      // نصٌّ واحد يقرؤه إنسان: السبب المختار ثم ملاحظةُ الكبتن إن كتبها
      const text = note.trim() ? `${reason} — ${note.trim()}` : reason;
      await disputePayment(payment.id, text.slice(0, 255));
      navigate(`/rides/${rideId}`, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر فتح النزاع",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!ride) {
    return (
      <div className="flex h-full items-center justify-center bg-bg px-16">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const currency = CURRENCY_LABEL[ride.currency];

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-14 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">فتح نزاع</h1>
      </div>

      <p className="mb-16 text-12.5 leading-note text-muted">
        افتح نزاعاً إن لم تصلك حوالة الرحلة. تفصله الإدارة: مدفوعة أو غير
        مدفوعة.
      </p>

      <div className="mb-12 card p-14">
        <div className="flex justify-between text-12.5">
          <span className="text-muted">{formatWhen(ride.created_at)}</span>
          <span className="font-bold text-ink">
            {arabicDigits(
              payment?.amount ?? ride.final_fare ?? ride.estimated_fare,
            )}{" "}
            {currency}
          </span>
        </div>
        {payment?.cliq_reference ? (
          <div className="mt-8 flex justify-between text-11.5">
            <span className="text-muted">مرجع TAXO</span>
            <span className="font-medium text-ink">
              {payment.cliq_reference}
            </span>
          </div>
        ) : null}
        {payment?.cliq_transfer_reference ? (
          <div className="mt-6 flex justify-between text-11.5">
            <span className="text-muted">المرجع الذي أدخله الراكب</span>
            <span className="font-medium text-ink">
              {payment.cliq_transfer_reference}
            </span>
          </div>
        ) : null}
      </div>

      {payment === null ? (
        <ErrorNote message="لا دفعة كليك بانتظار تأكيدك على هذه الرحلة. النزاع متاح على دفعات كليك وحدها." />
      ) : (
        <>
          <div className="mb-14 flex flex-col gap-9">
            {REASONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setReason(option)}
                className={cn(
                  "pressable flex items-center gap-11 rounded-14 border bg-surface px-14 py-13 text-start",
                  reason === option ? "border-ink" : "border-line",
                )}
              >
                <span
                  className={cn(
                    "block size-16 flex-none rounded-full border",
                    reason === option
                      ? "border-ink bg-ink"
                      : "border-line bg-transparent",
                  )}
                />
                <span className="text-13 text-ink">{option}</span>
              </button>
            ))}
          </div>

          <Field
            label="ملاحظة"
            placeholder="أضف تفصيلاً يساعد الإدارة…"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
          />

          <ErrorNote message={error} />

          <Button
            variant="danger"
            className="mt-18"
            loading={busy}
            disabled={reason === null}
            onClick={() => void submit()}
          >
            إرسال النزاع
          </Button>

          <p className="mt-12 text-11.5 leading-note text-muted">
            المسار الفعلي مسجَّلٌ مع الرحلة، وتراه الإدارة حين تفصل في النزاع.
          </p>
        </>
      )}
    </div>
  );
}
