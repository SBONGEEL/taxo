/** بطاقة تأكيد حوالة كليك — SPEC القسم 6.2/5، و`DESIGN-DECISIONS.md` بند 32.
 *
 * لا وجود لها في التصميم، فرُسمت بنمط بطاقة الطلب الواردة: ورقةٌ سفليةٌ فوق
 * تعتيم، بمبلغٍ كبيرٍ ومرجعٍ وزرَّين.
 *
 * **وحلقةُ العدّاد تُرسم لأن خلفها مهلةً تقع فعلاً** (البند 32): موعدُ
 * الانقضاء مجمَّدٌ على الصف، ومهمةُ `app/tasks/payments.py` تحوّل الدفعة إلى
 * نزاعٍ عنده وتُخطر الطرفين. ولو لم تكن المهلة مبنيةً لما رُسمت الحلقة —
 * عدّادٌ يبلغ الصفر ولا يقع شيء يَعِد الكبتن بحسمٍ آليٍّ فينام عنه.
 *
 * والوحدةُ ساعاتٌ لا ثوانٍ، فالحلقةُ تُحدَّث كل دقيقة: عدّادُ ثوانٍ على مهلةٍ
 * من أربعٍ وعشرين ساعة يستهلك البطارية ولا يقول شيئاً جديداً.
 *
 * **والمرجعُ يُعرض كما أدخله الراكب**، لا تُبدَّل خاناته: به يبحث الكبتن في
 * كشف حسابه، ورقمٌ بشكلٍ آخر رقمٌ لا يجده.
 *
 * وزرُّ «لم تصلني» لا يفتح نزاعاً بنفسه: يُحوّل إلى `screens/Dispute.tsx`
 * حيث السببُ نصٌّ يقرؤه إنسان — والخلفية تطلب سبباً (`reason` 3–255)، فبطاقةٌ
 * ترسل نزاعاً بلا سببٍ تُرسل إلى الإدارة صفّاً لا تعرف ماذا تفعل به.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { confirmPayment } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { arabicDigits, cn } from "@/lib/utils";

export interface CliqTransfer {
  rideId: string;
  paymentId: string;
  amount: string;
  currency: string;
  transferReference: string;
  /** موعدُ الانقضاء كما جمّدته الخلفية — `null` لدفعةٍ سبقت المهلة. */
  expiresAt: string | null;
}

interface Props {
  transfer: CliqTransfer;
  currencyLabel: string;
  onConfirmed: () => void;
  onDispute: () => void;
  onDismiss: () => void;
}

/** ما بقي من المهلة نصّاً — «٦ ساعات» أو «٤٠ دقيقة»، ولا ثوانيَ في الأخير. */
function remainingLabel(minutes: number): string {
  if (minutes <= 0) return "انقضت المهلة";
  if (minutes < 60) return `${arabicDigits(String(minutes))} دقيقة`;
  return `${arabicDigits(String(Math.floor(minutes / 60)))} ساعة`;
}

export function CliqTransferSheet({
  transfer,
  currencyLabel,
  onConfirmed,
  onDispute,
  onDismiss,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!transfer.expiresAt) return;
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, [transfer.expiresAt]);

  const deadline = transfer.expiresAt
    ? new Date(transfer.expiresAt).getTime()
    : null;
  const minutesLeft =
    deadline === null
      ? null
      : Math.max(0, Math.floor((deadline - now) / 60_000));

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await confirmPayment(transfer.paymentId);
      onConfirmed();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تأكيد الدفعة",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="absolute inset-0 z-50 animate-fadein bg-dim">
      <div className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-22 pt-18">
        <div className="mb-6 text-13 text-muted">حوالة كليك بانتظار تأكيدك</div>
        <div className="mb-15 flex items-baseline justify-between">
          <div className="text-30 font-bold leading-hero text-ink">
            {arabicDigits(transfer.amount)}{" "}
            <span className="text-13 font-medium text-muted">
              {currencyLabel}
            </span>
          </div>
          {minutesLeft !== null ? (
            <div className="text-end">
              <div
                className={cn(
                  "text-13 font-bold",
                  minutesLeft <= 60 ? "text-danger" : "text-warn",
                )}
              >
                {remainingLabel(minutesLeft)}
              </div>
              <div className="text-10.5 text-muted">قبل أن تصير نزاعاً</div>
            </div>
          ) : null}
        </div>

        <div className="mb-15 rounded-14 border border-line bg-surface-2 px-14 py-12">
          <div className="flex items-baseline justify-between">
            <span className="text-11.5 text-muted">
              مرجع الحوالة كما أدخله الراكب
            </span>
            <span dir="ltr" className="text-13 font-bold text-ink">
              {transfer.transferReference || "—"}
            </span>
          </div>
          <p className="mt-8 text-11 leading-note text-muted">
            تأكّد من وصولها إلى حسابك قبل أن تؤكد — تأكيدُك هو ما يُثبّت الدفعة،
            والمال يبقى معك ولا يمر بمحفظتك.
          </p>
        </div>

        <ErrorNote message={error} />

        <div className="mt-12 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy}
            onClick={() => void confirm()}
          >
            وصلتني
          </Button>
          {/* بحدٍّ ولونِ `--dng` كما في البند 32 — الرفضُ فعلٌ ثقيل */}
          <Button
            className="flex-1 border-danger text-danger"
            size="md"
            variant="secondary"
            disabled={busy}
            onClick={onDispute}
          >
            لم تصلني
          </Button>
        </div>

        <button
          type="button"
          onClick={onDismiss}
          className="mt-12 w-full text-center text-11.5 font-semibold text-muted"
        >
          لاحقاً — تبقى في تفاصيل الرحلة
        </button>
      </div>
    </div>
  );
}
