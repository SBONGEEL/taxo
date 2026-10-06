/** ورقةُ طلب السحب — TAXO 2.0 «C20» (`design/t2-new/captain/C20b-*.dc.html`)، تُفتح من «سحب عبر CliQ» في الأرباح (C09) — SPEC القسم 9.
 *
 * **وهي خطوةُ التأكيد نفسُها**: زرُّ الأرباح يفتحها ولا يرسل، و«إرسال الطلب» هنا وحدَه يرسل — كما كانت حرفاً.
 *
 * **رقمان جاهزان لا ثلاثةٌ مُخترعة**: التصميم القديم يعرض ثلاثة مبالغَ سريعة بقيمٍ ثابتة. وكلُّ قيمةٍ لا تأتي من الخلفية تعني ضربَ مالٍ
 * أو قسمتَه في الواجهة، وهو ممنوع (القسم 14). فالبلاطتان هنا **الحد الأدنى** و**كل المتاح** — كلاهما حقلٌ في `GET /wallet/me/driver`
 * يُنسخ كما هو — وبينهما حقلُ مبلغٍ حرّ.
 *
 * **والقناةُ كليك وحدها**: `WithdrawalMethod` فيه `bank` أيضاً، ولا حقلَ لبيانات حسابٍ بنكي على `drivers` — فطلبٌ بنكيٌّ من التطبيق
 * طلبٌ بلا وجهة. والحوالةُ البنكية تبقى ممكنةً من الإدارة حيث تُعرف الوجهة بغير الجدول.
 *
 * و`alias` كليك شرطُ الخلفية (`withdrawals.create_request`)، فمن لا alias له يضعه من هنا بدل أن يُرسل طلباً يُرفض.
 *
 * **ولغتُها أوراقُ الكبتن** (C07: سطحٌ بحافّةٍ علويةٍ وزاوية ٣٠ ومقبض)، **والبلاطتان بلاطتا «الدفع من» في C10** — بالرموز وحدَها،
 * **فلا تحتاج جسرَ الألوان القائمة** (`.t2-legacy`) الذي كان يلفّها في C09.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { requestWithdrawal, updateDriver } from "@/api/endpoints";
import type { DriverWallet } from "@/api/types";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/fields.css";
import "@/screens/t2/money.css";

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
  // **مقارنةُ عرضٍ لا حسابُ مال** (§14): لا ضربَ ولا قسمة — رقمان من الخلفية
  // يُقارنان ليُقال للكبتن لماذا لا يستطيع، والحكمُ نفسُه يبقى للخلفية
  const blocked =
    Number(wallet.available_for_withdrawal) <
    Number(wallet.min_withdrawal_amount);
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
    <div className="t2 t2-wds" onClick={onClose}>
      <div
        className="t2-wds-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="withdraw-title"
        onClick={(event) => event.stopPropagation()}
      >
        <span className="t2-wds-grab" aria-hidden="true" />
        <h2 id="withdraw-title" className="t2-wds-title">
          طلب سحب
        </h2>
        <p className="t2-wds-lead">
          يصلك عبر كليك بعد موافقة الإدارة، ويُخصم من رصيدك عند الدفع لا عند
          الطلب.
        </p>

        {/* **حين يعلو الحدُّ الأدنى على المتاح**: البلاطتان كلتاهما تؤدّيان إلى ٤٠٩ — «الحد الأدنى» أكبرُ من رصيده، و«كل
            المتاح» أقلُّ من الحدّ. فيضغط ويرتدّ ويعيد، وهو ما تمنعه قاعدةُ «زرٌّ معطَّلٌ يقول لماذا خيرٌ من زرٍّ يعمل ثم يرتدّ».
            وجدته المرحلةُ ١٣ على الجهاز */}
        {blocked ? (
          <p className="t2-wds-blocked">
            <Icon name="info" />
            <span>
              لا يمكن السحب الآن: الحدُّ الأدنى{" "}
              {digits(wallet.min_withdrawal_amount)} {currencyLabel}، والمتاح
              لديك {digits(wallet.available_for_withdrawal)} {currencyLabel}
              {Number(wallet.withdrawal_reserve_amount) > 0
                ? ` — ومنها ${digits(wallet.withdrawal_reserve_amount)} محتجَزةٌ لا تُسحب`
                : ""}
              .
            </span>
          </p>
        ) : null}

        <div className="t2-wds-quick">
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

        <label className="t2-fld-label" htmlFor="withdraw-amount">
          أو اكتب مبلغاً
        </label>
        <input
          id="withdraw-amount"
          className="t2-fld on-card"
          inputMode="decimal"
          dir="ltr"
          placeholder="0.000"
          value={amount}
          onChange={(event) => setAmount(cleanAmount(event.target.value))}
        />

        {hasAlias ? (
          <p className="t2-wds-alias">
            التحويل عبر كليك إلى <b dir="ltr">{cliqAlias}</b>
          </p>
        ) : (
          <div className="t2-wds-aliasfield">
            <label className="t2-fld-label" htmlFor="withdraw-alias">
              alias كليك
            </label>
            <input
              id="withdraw-alias"
              className="t2-fld on-card"
              dir="ltr"
              placeholder="ABUMOHD"
              value={alias}
              onChange={(event) => setAlias(event.target.value)}
            />
            <p className="t2-fld-hint">
              عليه تستلم تحويلات السحب — تأكد من مطابقته لبنكك.
            </p>
          </div>
        )}

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" fill />
            {error}
          </p>
        ) : null}

        <button
          type="button"
          className="t2-wds-send"
          disabled={
            busy ||
            blocked ||
            !amount ||
            (!hasAlias && alias.trim().length === 0)
          }
          onClick={() => void submit()}
        >
          {busy ? "…" : "إرسال الطلب"}
        </button>
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
      aria-pressed={active}
      onClick={() => onPick(value)}
      className="t2-wds-tile"
    >
      <span className="t2-wds-tile-k">{label}</span>
      <span className="t2-wds-tile-v">
        <span className="t2-wds-tile-num" dir="ltr">
          {digits(value)}
        </span>{" "}
        <span className="t2-wds-tile-cur">{currencyLabel}</span>
      </span>
    </button>
  );
}
