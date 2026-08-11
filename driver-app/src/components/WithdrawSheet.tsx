/** ورقةُ طلب السحب — `DESIGN.md` §5.3، وSPEC القسم 9.
 *
 * **رقمان جاهزان لا ثلاثةٌ مُخترعة**: التصميم يعرض ثلاثة مبالغَ سريعة بقيمٍ
 * ثابتة. وكلُّ قيمةٍ لا تأتي من الخلفية تعني ضربَ مالٍ أو قسمتَه في الواجهة،
 * وهو ممنوع (القسم 14). فالزرّان هنا **الحد الأدنى** و**كل المتاح** — كلاهما
 * حقلٌ في `GET /wallet/me/driver` يُنسخ كما هو — وبينهما حقلُ مبلغٍ حرّ.
 *
 * **والقناةُ كليك وحدها**: `WithdrawalMethod` فيه `bank` أيضاً، ولا حقلَ
 * لبيانات حسابٍ بنكي على `drivers` — فطلبٌ بنكيٌّ من التطبيق طلبٌ بلا وجهة.
 * والحوالةُ البنكية تبقى ممكنةً من الإدارة حيث تُعرف الوجهة بغير الجدول.
 *
 * و`alias` كليك شرطُ الخلفية (`withdrawals.create_request`)، فمن لا alias له
 * يضعه من هنا بدل أن يُرسل طلباً يُرفض: الرفضُ صحيحٌ ونصُّه واضح، لكنه طريقٌ
 * مسدود إن كانت الشاشةُ التي تُصلحه لم تُبنَ بعد.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { requestWithdrawal, updateDriver } from "@/api/endpoints";
import type { DriverWallet } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { arabicDigits, cn } from "@/lib/utils";

interface Props {
  wallet: DriverWallet;
  currencyLabel: string;
  cliqAlias: string | null;
  onAliasSaved: (alias: string) => void;
  onDone: () => void;
  onClose: () => void;
}

/** المبلغ كما يكتبه الكبتن: خاناتٌ ونقطةٌ واحدة، بلا `Number` ولا تقريب. */
function cleanAmount(raw: string): string {
  const digits = raw.replace(/[^0-9.]/g, "");
  const [whole, ...rest] = digits.split(".");
  return rest.length > 0 ? `${whole}.${rest.join("").slice(0, 3)}` : whole;
}

export function WithdrawSheet({
  wallet,
  currencyLabel,
  cliqAlias,
  onAliasSaved,
  onDone,
  onClose,
}: Props) {
  const [amount, setAmount] = useState("");
  const [alias, setAlias] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const hasAlias = (cliqAlias ?? "").trim().length > 0;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (!hasAlias) {
        const driver = await updateDriver({ cliq_alias: alias.trim() });
        onAliasSaved(driver.cliq_alias ?? alias.trim());
      }
      await requestWithdrawal(amount, "cliq");
      onDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="absolute inset-0 z-50 animate-fadein-fast bg-dim"
      onClick={onClose}
    >
      <div
        className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-24 pt-20"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">طلب سحب</h2>
        <p className="mb-16 text-12 text-muted">
          يصلك عبر كليك بعد موافقة الإدارة، ويُخصم من رصيدك عند الدفع لا عند
          الطلب.
        </p>

        <div className="mb-14 flex gap-8">
          <Quick
            label="الحد الأدنى"
            value={wallet.min_withdrawal_amount}
            currencyLabel={currencyLabel}
            active={amount === wallet.min_withdrawal_amount}
            onPick={setAmount}
          />
          <Quick
            label="كل المتاح"
            value={wallet.available_for_withdrawal}
            currencyLabel={currencyLabel}
            active={amount === wallet.available_for_withdrawal}
            onPick={setAmount}
          />
        </div>

        <Field
          label="أو اكتب مبلغاً"
          inputMode="decimal"
          dir="ltr"
          placeholder="0.000"
          value={amount}
          onChange={(event) => setAmount(cleanAmount(event.target.value))}
        />

        {hasAlias ? (
          <p className="mt-14 rounded-12 border border-line bg-surface-2 px-14 py-11 text-12 text-muted">
            التحويل عبر كليك إلى{" "}
            <b dir="ltr" className="font-bold text-ink">
              {cliqAlias}
            </b>
          </p>
        ) : (
          <div className="mt-14">
            <Field
              label="alias كليك"
              dir="ltr"
              placeholder="ABUMOHD"
              value={alias}
              onChange={(event) => setAlias(event.target.value)}
            />
            <p className="mt-6 text-11.5 leading-note text-muted">
              عليه تستلم تحويلات السحب — تأكد من مطابقته لبنكك.
            </p>
          </div>
        )}

        <ErrorNote message={error} />

        <Button
          className="mt-16"
          size="md"
          loading={busy}
          disabled={!amount || (!hasAlias && alias.trim().length === 0)}
          onClick={() => void submit()}
        >
          إرسال الطلب
        </Button>
      </div>
    </div>
  );
}

function Quick({
  label,
  value,
  currencyLabel,
  active,
  onPick,
}: {
  label: string;
  value: string;
  currencyLabel: string;
  active: boolean;
  onPick: (value: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPick(value)}
      className={cn(
        "flex-1 rounded-12 border p-12 text-center text-ink",
        active ? "border-ink bg-surface-2" : "border-line",
      )}
    >
      <span className="block text-11 text-muted">{label}</span>
      <span className="block text-14 font-bold">
        {arabicDigits(value)} {currencyLabel}
      </span>
    </button>
  );
}
