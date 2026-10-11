/** ورقةُ طلب السحب — TAXO 2.0 «C20» (`design/t2-new/captain/C20b-*.dc.html`)، تُفتح من «سحب عبر CliQ» في الأرباح (C09) — SPEC القسم 9.
 *
 * **وهي خطوةُ التأكيد نفسُها**: زرُّ الأرباح يفتحها ولا يرسل، و«إرسال الطلب» هنا وحدَه يرسل — كما كانت حرفاً.
 *
 * **رقمان جاهزان لا ثلاثةٌ مُخترعة**: التصميم القديم يعرض ثلاثة مبالغَ سريعة بقيمٍ ثابتة. وكلُّ قيمةٍ لا تأتي من الخلفية تعني ضربَ مالٍ
 * أو قسمتَه في الواجهة، وهو ممنوع (القسم 14). فالبلاطتان هنا **الحد الأدنى** و**كل المتاح** — كلاهما حقلٌ في `GET /wallet/me/driver`
 * يُنسخ كما هو — وبينهما حقلُ مبلغٍ حرّ.
 *
 * **وحين يُشعَل التقريبُ في سوقه** (SPEC §٧٠-ج/٦، المثال ج): «كلُّ المتاح» يصل **أكبرَ مضاعفٍ لوحدة السوق** محسوباً في الخلفية
 * (`37.842 ⇐ 37.500`، والكسرُ يبقى له)، **والحقلُ الحرُّ يقول خطواتِ الوحدة** ويُفحص قبل الإرسال (`lib/rounding.ts`).
 *
 * **والقناةُ كليك وحدها**: `WithdrawalMethod` فيه `bank` أيضاً، ولا حقلَ لبيانات حسابٍ بنكي على `drivers` — فطلبٌ بنكيٌّ من التطبيق
 * طلبٌ بلا وجهة. والحوالةُ البنكية تبقى ممكنةً من الإدارة حيث تُعرف الوجهة بغير الجدول.
 *
 * و`alias` كليك شرطُ الخلفية (`withdrawals.create_request`)، فمن لا alias له يضعه من هنا بدل أن يُرسل طلباً يُرفض.
 *
 * **وفي سوقٍ بلا كليك** (الجزائر، SPEC §٧٣-هـ المرحلة ٤) تعرض الورقةُ **قنواتِ سوقه** كما تنشرها الخلفية (`withdrawal_methods`): BaridiMob
 * برقم RIP، وCCP برقمه ومفتاحه، والبنكُ برقم RIB، **وكاشُ المكتب بلا وجهة** — **والوجهةُ تُكتب مع الطلب وتُجمَّد عليه**. **والشكلُ يُفحص
 * في الخلفية لا هنا**: الحقلُ يقبل ما يُكتب على الورق (مسافاتٌ و«clé»)، والخلفيةُ تطبّعه أو تردّه بنصّه. **وسوقٌ فيها كليك ترى الورقةَ
 * كما كانت حرفاً.**
 *
 * **ولغتُها أوراقُ الكبتن** (C07: سطحٌ بحافّةٍ علويةٍ وزاوية ٣٠ ومقبض)، **والبلاطتان بلاطتا «الدفع من» في C10** — بالرموز وحدَها،
 * **فلا تحتاج جسرَ الألوان القائمة** (`.t2-legacy`) الذي كان يلفّها في C09.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { requestWithdrawal, updateDriver } from "@/api/endpoints";
import type { DriverWallet, WithdrawalMethod } from "@/api/types";
import { useCountryConfig } from "@/lib/config";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { useSession } from "@/lib/session";
import { currencyDecimals, digits, zeroAmount } from "@/lib/utils";
import { WITHDRAWAL_METHOD_LABEL } from "@/lib/walletFormat";
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

/** **حقلُ الوجهة لكلِّ قناةٍ جزائريّة** — اسمُه وتلميحُه ومثالُه؛ وكاشُ المكتب بلا حقل. */
const DESTINATION: Partial<Record<WithdrawalMethod, { label: string; hint: string; placeholder: string }>> = {
  baridimob: { label: "رقم RIP", hint: "عشرون خانة كما في تطبيق بريدي موب.", placeholder: "00799999…" },
  ccp: { label: "رقم CCP ومفتاحه", hint: "رقمُ الحساب ثمّ المفتاح (خانتان) كما في دفتر الصكوك البريديّة.", placeholder: "0012345678 90" },
  bank: { label: "رقم RIB", hint: "عشرون خانة كما في كشف حسابك البنكيّ.", placeholder: "…" },
};

/** المبلغ كما يكتبه الكبتن: خاناتٌ ونقطةٌ واحدة، بلا `Number` ولا تقريب — **وبخانات عملته** (ثلاثٌ للأردنيّ كما كانت، ولا نقطةَ
 *  للجزائريّ — SPEC §٧٣-ج/١٢). */
function cleanAmount(raw: string, places: number): string {
  const digits = raw.replace(/[^0-9.]/g, "");
  const [whole, ...rest] = digits.split(".");
  if (places === 0) return whole;
  return rest.length > 0 ? `${whole}.${rest.join("").slice(0, places)}` : whole;
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
  // **المسحوبُ مضاعفٌ لوحدة التقريب حين تكون مشتعلة** (SPEC §٧٠-ج/٦، المثال ج) — و«كلُّ المتاح» يصل من الخلفية أكبرَ مضاعفٍ
  // فيُختار كما هو؛ والمكتوبُ بيده يُفحص هنا قبل أن تردّه الخلفية، **والكسرُ الباقي له في محفظته**
  const { user } = useSession();
  const unit = roundingUnit(useCountryConfig(user?.country_code));
  const unitError = notMultipleMessage(amount, unit, currencyLabel);

  const hasAlias = (cliqAlias ?? "").trim().length > 0;
  // **سوقٌ بلا كليك** (الجزائر) — ومن لا تصله القائمةُ يبقى على كليك كما كان
  const methods = wallet.withdrawal_methods ?? [];
  const local = methods.length > 0 && !methods.includes("cliq");
  const [method, setMethod] = useState<WithdrawalMethod>(local ? methods[0] : "cliq");
  const [account, setAccount] = useState("");
  const [holder, setHolder] = useState("");
  const field = DESTINATION[method];
  const destinationMissing = local && field !== undefined && (account.trim().length === 0 || holder.trim().length < 3);

  async function submit() {
    setBusy(true);
    setError(null);
    if (local) {
      try {
        await requestWithdrawal(
          amount,
          method,
          field ? { payout_account: account.trim(), payout_holder: holder.trim() } : undefined,
        );
        onDone();
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب");
      } finally {
        setBusy(false);
      }
      return;
    }
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
          {local
            ? "يصلك بالطريقة التي تختارها بعد موافقة الإدارة، ويُخصم من رصيدك عند الدفع لا عند الطلب."
            : "يصلك عبر كليك بعد موافقة الإدارة، ويُخصم من رصيدك عند الدفع لا عند الطلب."}
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
          placeholder={zeroAmount(wallet.currency)}
          value={amount}
          onChange={(event) => setAmount(cleanAmount(event.target.value, currencyDecimals(wallet.currency)))}
        />
        {unitError ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" fill />
            {unitError}
          </p>
        ) : unit !== null ? (
          <p className="t2-fld-hint">{unitHint(unit, currencyLabel)}</p>
        ) : null}

        {local ? (
          <>
            <p className="t2-fld-label">كيف يصلك</p>
            <div className="t2-wds-methods" role="radiogroup" aria-label="طريقة السحب">
              {methods.map((key) => (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={method === key}
                  aria-pressed={method === key}
                  className="t2-wds-tile"
                  onClick={() => {
                    setMethod(key);
                    setAccount("");
                  }}
                >
                  <span className="t2-wds-tile-k">{WITHDRAWAL_METHOD_LABEL[key]}</span>
                </button>
              ))}
            </div>
            {field ? (
              <div className="t2-wds-aliasfield">
                <label className="t2-fld-label" htmlFor="withdraw-account">
                  {field.label}
                </label>
                <input
                  id="withdraw-account"
                  className="t2-fld on-card"
                  dir="ltr"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder={field.placeholder}
                  value={account}
                  onChange={(event) => setAccount(event.target.value)}
                />
                <p className="t2-fld-hint">{field.hint}</p>
                <label className="t2-fld-label" htmlFor="withdraw-holder">
                  اسم صاحب الحساب
                </label>
                <input
                  id="withdraw-holder"
                  className="t2-fld on-card"
                  autoComplete="name"
                  value={holder}
                  onChange={(event) => setHolder(event.target.value)}
                />
                <p className="t2-fld-hint">كما هو مكتوب في الحساب — الحوالةُ إلى غير صاحبه تُردّ.</p>
              </div>
            ) : (
              <p className="t2-wds-alias">
                تستلم المبلغ نقداً من مكتب TAXO بعد موافقة الإدارة — احمل بطاقة هويّتك.
              </p>
            )}
          </>
        ) : hasAlias ? (
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
            unitError !== null ||
            destinationMissing ||
            (!local && !hasAlias && alias.trim().length === 0)
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
