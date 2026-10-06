/** بطاقة تأكيد حوالة كليك — SPEC القسم 6.2/5، و`DESIGN-DECISIONS.md` بند 32 — TAXO 2.0 «C21d»
 * (`design/t2-new/captain/C21d-cliq-transfer-sheet.dc.html`)، تصل من المقبس فوق الرئيسية.
 *
 * لا وجود لها في اللوحة الحيّة، **فرُسمت بلغة بطاقة الطلب الواردة C05**: بطاقةٌ عائمةٌ فوق ظلّ الهوية، بمبلغٍ كبيرٍ ومرجعٍ وزرَّين —
 * «لم تصلني» بحدِّ الخطر في موضع «رفض»، و«وصلتني» بالجمر في موضع «قبول».
 *
 * **والمهلةُ تُرسم لأن خلفها انقضاءً يقع فعلاً** (البند 32): موعدُ الانقضاء مجمَّدٌ على الصف، ومهمةُ `app/tasks/payments.py` تحوّل
 * الدفعة إلى نزاعٍ عنده وتُخطر الطرفين. ولو لم تكن المهلة مبنيةً لما رُسمت — عدّادٌ يبلغ الصفر ولا يقع شيء يَعِد الكبتن بحسمٍ آليٍّ فينام عنه.
 *
 * والوحدةُ ساعاتٌ لا ثوانٍ، فالمهلةُ تُحدَّث كل دقيقة: عدّادُ ثوانٍ على مهلةٍ من أربعٍ وعشرين ساعة يستهلك البطارية ولا يقول شيئاً جديداً.
 *
 * **والمرجعُ يُعرض كما أدخله الراكب**، لا تُبدَّل خاناته: به يبحث الكبتن في كشف حسابه، ورقمٌ بشكلٍ آخر رقمٌ لا يجده.
 *
 * وزرُّ «لم تصلني» لا يفتح نزاعاً بنفسه: يُحوّل إلى `screens/Dispute.tsx` حيث السببُ نصٌّ يقرؤه إنسان — والخلفية تطلب سبباً
 * (`reason` 3–255)، فبطاقةٌ ترسل نزاعاً بلا سببٍ تُرسل إلى الإدارة صفّاً لا تعرف ماذا تفعل به.
 *
 * **والمنطقُ هو هو حرفاً** (التأكيدُ وأفعالُ الأزرار الثلاثة)، **ولا يُغلقها لمسُ الظلّ** كما كانت — القرارُ أو «لاحقاً».
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { confirmPayment } from "@/api/endpoints";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/money.css";

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
  if (minutes < 60) return `${digits(String(minutes))} دقيقة`;
  return `${digits(String(Math.floor(minutes / 60)))} ساعة`;
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
    <div className="t2 t2-cts">
      <div
        className="t2-cts-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cts-title"
      >
        <div className="t2-cts-top">
          <div className="t2-cts-main">
            <p id="cts-title" className="t2-cts-caption">
              حوالة كليك بانتظار تأكيدك
            </p>
            <p className="t2-cts-amount">
              <span className="t2-cts-num" dir="ltr">
                {digits(transfer.amount)}
              </span>
              <span className="t2-cts-cur">{currencyLabel}</span>
            </p>
          </div>
          {minutesLeft !== null ? (
            <div className={minutesLeft <= 60 ? "t2-cts-left urgent" : "t2-cts-left"}>
              <span className="t2-cts-left-v">
                <Icon name="hourglass_top" />
                {remainingLabel(minutesLeft)}
              </span>
              <span className="t2-cts-left-k">قبل أن تصير نزاعاً</span>
            </div>
          ) : null}
        </div>

        <div className="t2-cts-ref">
          <p className="t2-cts-ref-row">
            <span>مرجع الحوالة كما أدخله الراكب</span>
            <span dir="ltr" className="t2-cts-ref-code">
              {transfer.transferReference || "—"}
            </span>
          </p>
          <p className="t2-cts-ref-note">
            تأكّد من وصولها إلى حسابك قبل أن تؤكد — تأكيدُك هو ما يُثبّت الدفعة،
            والمال يبقى معك ولا يمر بمحفظتك.
          </p>
        </div>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" fill />
            {error}
          </p>
        ) : null}

        <div className="t2-cts-acts">
          {/* بحدٍّ ولونِ الخطر كما في البند 32 — الرفضُ فعلٌ ثقيل */}
          <button
            type="button"
            className="t2-cts-no"
            disabled={busy}
            onClick={onDispute}
          >
            لم تصلني
          </button>
          <button
            type="button"
            className="t2-cts-yes"
            disabled={busy}
            onClick={() => void confirm()}
          >
            {busy ? (
              "…"
            ) : (
              <>
                <Icon name="check" />
                وصلتني
              </>
            )}
          </button>
        </div>

        <button type="button" className="t2-cts-later" onClick={onDismiss}>
          لاحقاً — تبقى في تفاصيل الرحلة
        </button>
      </div>
    </div>
  );
}
