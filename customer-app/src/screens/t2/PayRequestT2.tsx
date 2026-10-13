/** **الشحنُ بطرق السوق** — نظامُ الدفع الجديد (SPEC §٧٣-هـ المرحلة ١)، **بقطع شاشات المال نفسِها** (R16 · R16b).
 *
 * **يُفتح من ورقة الشحن وحدَها، وحيث `payment_requests_enabled` مشتعلٌ وحدَه** — والأردنُ وليبيا مطفآن، فلا يبلغونها ولا يتغيّر ما يرونه.
 *
 * **ثلاثُ خطواتٍ في صفحةٍ واحدة**: الطريقةُ وتفاصيلُها (إلى من تحوّل: الاسمُ والرقمُ بزرِّ نسخ، والبنك، والتعليمات، ورمزُ QR إن رُفع)،
 * ثمّ المبلغ، ثمّ **رقمُ التحويل وصورةُ الإيصال — إجباريّان في التحويلات** (قرارُ المالك؛ والخادمُ يرفض من دونهما). **ولا رصيدَ يتغيّر
 * قبل أن يعتمده موظّفٌ ماليّ** — والصفحةُ تقول ذلك ولا تَعِد بغيره.
 *
 * **ولا مبالغَ سريعة**: اقتراحُ مبالغَ لسوقٍ جديدٍ اختراعُ أرقامٍ لم يضعها المالك — والحقلُ فارغٌ حتى يكتب صاحبُه.
 */

import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { createPaymentRequest, listPaymentMethods, openPaymentCheckout, paymentMethodQr } from "@/api/endpoints";
import type { PayMethod } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import { AmountCardT2, BannerT2, BusyLabel, HeadT2, QuickAmountsT2, UnitNoteT2, WaitT2 } from "./MoneyT2";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

/** أيقونةُ كلِّ نوع — **الكاشُ يدٌ تسلّم، والتحويلُ بنك، ورقمُ الهاتف هاتف** */
const KIND_ICON: Record<PayMethod["kind"], string> = {
  cash: "payments",
  bank_transfer: "account_balance",
  purchase_code: "confirmation_number",
  phone_number: "smartphone",
};

export function PayRequestT2Screen() {
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);
  const goBack = useGoBack("/wallet");
  const navigate = useNavigate();
  const handoff = (useLocation().state ?? null) as { amount?: string; methodId?: string } | null;

  const [methods, setMethods] = useState<PayMethod[] | null>(null);
  const [choices, setChoices] = useState<string[]>([]);
  const [methodId, setMethodId] = useState(handoff?.methodId ?? "");
  const [amount, setAmount] = useState(handoff?.amount ?? "");
  const [reference, setReference] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const currency = country?.currency;
  const unit = roundingUnit(country);
  const unitError = notMultipleMessage(amount, unit, currency);

  useEffect(() => {
    listPaymentMethods("wallet_topup")
      .then((body) => {
        // **بطاقةُ TAXO تُدخل برمزها في صفحتها** (`/wallet/card`) — لا طلبَ يُراجَع
        setMethods(body.methods.filter((row) => row.kind !== "purchase_code"));
        setChoices(body.topup_choices ?? []);
        setMethodId((current) => current || body.methods.find((row) => row.kind !== "purchase_code")?.id || "");
      })
      .catch((caught: unknown) => {
        setMethods([]);
        setError(caught instanceof ApiError ? caught.message : tr("تعذّر قراءة طرق الدفع"));
      });
  }, []);

  const method = methods?.find((row) => row.id === methodId) ?? null;
  // **الشحنُ عند الوسيط خياراتٌ ثابتةٌ إن ضبطها السوق** (SPEC §٧٤-ط/٥) — فلا يُكتب مبلغ، ويُختار واحدٌ منها؛ والخادمُ يردّ غيرَها
  const fixed = method?.gateway === true && choices.length > 0;

  // **صورةُ الرمز بجلسة صاحبها** — `Blob` يصير رابطاً محلّيّاً ويُحرَّر حين تتبدّل الطريقة
  useEffect(() => {
    setQrUrl(null);
    if (!method?.has_qr) return;
    let url: string | null = null;
    let cancelled = false;
    paymentMethodQr(method.id)
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setQrUrl(url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [method?.id, method?.has_qr]);

  const needsReceipt = method?.requires_receipt === true;
  const ready =
    method !== null &&
    Number(amount) > 0 &&
    unitError === null &&
    (!needsReceipt || (receipt !== null && reference.trim().length >= 3));

  async function copyNumber() {
    if (!method?.account_number) return;
    try {
      await navigator.clipboard.writeText(method.account_number);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* الحافظةُ ممنوعة — الرقمُ مرئيٌّ يُنسخ باليد */
    }
  }

  async function submit() {
    if (!method) return;
    if (method.gateway) {
      // **الوسيطُ الآليّ** (المرحلة ٣) — صفحتُه ثمّ العودةُ إلى `/wallet/pay/return` تسأل عن الحال؛ **ولا وعدَ قبل أن يقول الوسيط**
      setBusy(true);
      setError(null);
      try {
        const opened = await openPaymentCheckout({ methodId: method.id, purpose: "wallet_topup", amount });
        window.location.assign(opened.checkout_url);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : tr("تعذّر فتح صفحة الدفع — أعد المحاولة"));
        setBusy(false);
      }
      return;
    }
    setBusy(true);
    setError(null);
    setProgress(null);
    try {
      await createPaymentRequest(
        {
          methodId: method.id,
          purpose: "wallet_topup",
          amount,
          reference: reference.trim() || undefined,
          wallet: "rider",
          receipt,
        },
        { onProgress: setProgress },
      );
      setDone(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر إرسال الطلب — أعد المحاولة"));
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  if (done) {
    return (
      <div className="t2 t2-m-page">
        <HeadT2 title={tr("شحن الرصيد")} onBack={goBack} />
        <section className="t2-m-card t2-pr-done">
          <Icon name="schedule" />
          <h2 className="t2-pr-done-title">{tr("أرسلنا طلبك")}</h2>
          <p className="t2-pr-done-text">
            {tr("يراجعه فريقُ المالية ويُضاف")}{" "}{formatMoney(amount, currency)}{" "}{tr("إلى رصيدك بعد اعتماده. ستجد حالَه في المحفظة.")}
          </p>
          <button type="button" className="t2-button primary t2-m-cta t2-m-gap" onClick={() => navigate("/wallet")}>
            {tr("إلى المحفظة")}
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="t2 t2-m-page">
      <HeadT2 title={tr("شحن الرصيد")} onBack={goBack} />

      {methods === null ? (
        <WaitT2 />
      ) : methods.length === 0 ? (
        <BannerT2 tone="danger" message={error ?? tr("لا طريقةَ دفعٍ متاحةٌ في بلدك الآن.")} />
      ) : (
        <>
          <h2 className="t2-section">{tr("طريقة الدفع")}</h2>
          <div className="t2-m-chans" role="radiogroup" aria-label={tr("طريقة الدفع")}>
            {methods.map((row) => (
              <button
                key={row.id}
                type="button"
                role="radio"
                aria-checked={row.id === methodId}
                onClick={() => {
                  setMethodId(row.id);
                  setReceipt(null);
                  if (row.gateway && choices.length > 0 && !choices.includes(amount)) setAmount("");
                }}
                className={row.id === methodId ? "t2-m-chan on" : "t2-m-chan"}
              >
                <span className="t2-m-chan-icon">
                  <Icon name={KIND_ICON[row.kind]} />
                </span>
                <span className="t2-m-chan-main">
                  <span className="t2-m-chan-title">{row.name}</span>
                  <span className="t2-m-chan-hint">
                    {row.gateway
                      ? tr("ادفع بالبطاقة في صفحة الوسيط — يُضاف فورَ تأكيده")
                      : row.requires_receipt
                        ? tr("حوّل ثمّ أرفق الإيصال — يُضاف بعد المراجعة")
                        : tr("ادفع ثمّ يُضاف بعد المراجعة")}
                  </span>
                </span>
              </button>
            ))}
          </div>

          {method && !method.gateway ? (
            <section className="t2-m-card t2-m-gap t2-pr-dest" aria-label={tr("إلى أين تدفع")}>
              {method.account_number ? (
                <div className="t2-pr-line">
                  <span className="t2-m-label">{method.kind === "phone_number" ? tr("رقم الهاتف") : tr("رقم الحساب")}</span>
                  <span className="t2-pr-value">
                    <span dir="ltr" className="t2-pr-number">
                      {method.account_number}
                    </span>
                    <button type="button" className="t2-pr-copy" onClick={copyNumber} aria-label={tr("نسخ الرقم")}>
                      <Icon name={copied ? "check" : "content_copy"} />
                    </button>
                  </span>
                </div>
              ) : null}
              {method.account_holder ? (
                <div className="t2-pr-line">
                  <span className="t2-m-label">{tr("باسم")}</span>
                  <span className="t2-pr-text">{method.account_holder}</span>
                </div>
              ) : null}
              {method.bank_name ? (
                <div className="t2-pr-line">
                  <span className="t2-m-label">{tr("البنك")}</span>
                  <span className="t2-pr-text">{method.bank_name}</span>
                </div>
              ) : null}
              {method.instructions ? <p className="t2-pr-instructions">{method.instructions}</p> : null}
              {qrUrl ? (
                <div className="t2-pr-qr">
                  <img src={qrUrl} alt={tr("رمز QR لـ{0}", { 0: method.name })} />
                </div>
              ) : null}
            </section>
          ) : null}

          <div className="t2-m-gap-lg">
            <AmountCardT2
              id="pay-request-amount"
              label={fixed ? tr("اختر مبلغ الشحن") : tr("المبلغ")}
              value={amount}
              onChange={setAmount}
              currency={currency}
              disabled={fixed}
            >
              {fixed ? (
                <QuickAmountsT2
                  amounts={choices}
                  value={amount}
                  onPick={setAmount}
                  label={(choice) => formatMoney(choice, currency)}
                />
              ) : null}
            </AmountCardT2>
            {fixed ? null : <UnitNoteT2 hint={unitHint(unit, currency)} error={unitError} />}
            {method?.test_mode ? (
              <BannerT2 tone="ok" message={tr("وضعُ التجربة — مالٌ تجريبيٌّ لا يغادر المنصّة، ولا يُؤخذ من بطاقتك شيء.")} />
            ) : null}
          </div>

          {needsReceipt ? (
            <div className="t2-m-gap-lg">
              <AuthBlock label={tr("رقم التحويل")} htmlFor="pay-request-reference" hint={tr("كما يظهر في الإيصال")}>
                <AuthInput
                  id="pay-request-reference"
                  dir="ltr"
                  autoComplete="off"
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                />
              </AuthBlock>

              <label className="t2-pr-file" htmlFor="pay-request-receipt">
                <Icon name={receipt ? "task" : "add_photo_alternate"} />
                <span className="t2-pr-file-main">
                  <span className="t2-pr-file-title">{receipt ? tr("الإيصال مرفق") : tr("صورة الإيصال")}</span>
                  <span className="t2-pr-file-hint">{receipt ? receipt.name : tr("صورةٌ أو PDF — إجباريّة")}</span>
                </span>
              </label>
              <input
                id="pay-request-receipt"
                className="t2-pr-file-input"
                type="file"
                accept="image/png,image/jpeg,image/webp,application/pdf"
                onChange={(event) => setReceipt(event.target.files?.[0] ?? null)}
              />
            </div>
          ) : null}

          <BannerT2 tone="danger" message={error} />
          {progress !== null && progress < 100 ? (
            <p className="t2-m-hint">
              {tr("يُرفع الإيصال…")}{" "}<span dir="ltr">{progress}%</span>
            </p>
          ) : null}

          <div className="t2-m-actions">
            <button
              type="button"
              className="t2-button primary t2-m-cta"
              disabled={busy || !ready}
              aria-busy={busy}
              onClick={submit}
            >
              <BusyLabel busy={busy}>{method?.gateway ? tr("ادفع في صفحة الوسيط") : tr("أرسل للمراجعة")}</BusyLabel>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
