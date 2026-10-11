/** **الدفعُ بطرق السوق** — نظامُ الدفع الجديد للكبتن (SPEC §٧٣-هـ المرحلة ١)، **بقطع شاشات مال الكبتن** (C19–C22: رأسُ C10،
 * وبطاقةُ C12، وحقلُ C18، ورمزُ كليك C21).
 *
 * **غرضان بصفحةٍ واحدة**: شحنُ المحفظة، أو **اشتراكٌ** يصل من ورقة تأكيد الشراء بخطّته وثمنه — **والثمنُ لا يُكتب هنا** بل يصل من
 * الخلفية كما في الورقة (`price_to_pay`)، **وعند الاعتماد تُشحن المحفظةُ ثمّ يُشترى منها** (§٧٣-هـ/٧): فإن تعذّر الشراءُ بقي المالُ في
 * محفظتك. **ولا رصيدَ يتغيّر قبل أن يعتمده موظّفٌ ماليّ** — والصفحةُ تقول ذلك ولا تَعِد بغيره.
 *
 * **ويُبلغ حيث `payment_requests_enabled` مشتعلٌ وحدَه** — والأردنُ وليبيا مطفآن فلا يبلغونها. **ولا مبالغَ مقترحة**: أرقامٌ لم يضعها المالك.
 */

import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { createPaymentRequest, listPaymentMethods, openPaymentCheckout, paymentMethodQr } from "@/api/endpoints";
import type { PayMethod, PaymentRequestPurpose } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { currencyDecimals, digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./fields.css";
import "./money.css";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

const KIND_ICON: Record<PayMethod["kind"], string> = {
  cash: "payments",
  bank_transfer: "account_balance",
  purchase_code: "confirmation_number",
  phone_number: "smartphone",
};

/** **الخاناتُ والنقطةُ وحدَها، وبخانات العملة** — «150» للجزائريّ بلا كسور */
function cleanAmount(raw: string, places: number): string {
  const kept = raw.replace(/[^\d.]/g, "");
  const [whole, ...rest] = kept.split(".");
  if (places === 0) return whole;
  return rest.length ? `${whole}.${rest.join("").slice(0, places)}` : whole;
}

export function PayRequestT2Screen() {
  const navigate = useNavigate();
  const { profile } = useDriver();
  const country = useCountryConfig(profile?.user?.country_code);
  const handoff = (useLocation().state ?? null) as {
    purpose?: PaymentRequestPurpose;
    planId?: string;
    planName?: string;
    amount?: string;
  } | null;
  const purpose: PaymentRequestPurpose = handoff?.purpose === "subscription" && handoff.planId ? "subscription" : "wallet_topup";
  const goBack = useGoBack(purpose === "subscription" ? "/subscription" : "/wallet");

  const [methods, setMethods] = useState<PayMethod[] | null>(null);
  const [cardMethod, setCardMethod] = useState(false);
  const [methodId, setMethodId] = useState("");
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
  const label = currency ? CURRENCY_LABEL[currency] : "";
  const unit = roundingUnit(country);
  const unitError = purpose === "subscription" ? null : notMultipleMessage(amount, unit, label);

  useEffect(() => {
    listPaymentMethods(purpose)
      .then((body) => {
        // **بطاقةُ TAXO تُدخل برمزها في صفحتها** (`/wallet/card`) — بابٌ فوق الطرق لا طريقةٌ تُراجَع
        setCardMethod(body.methods.some((row) => row.kind === "purchase_code"));
        const reviewed = body.methods.filter((row) => row.kind !== "purchase_code");
        setMethods(reviewed);
        setMethodId((current) => current || reviewed[0]?.id || "");
      })
      .catch((caught: unknown) => {
        setMethods([]);
        setError(caught instanceof ApiError ? caught.message : tr("تعذّر قراءة طرق الدفع"));
      });
  }, [purpose]);

  const method = methods?.find((row) => row.id === methodId) ?? null;

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
      // **الوسيطُ الآليّ** (المرحلة ٣) — صفحتُه ثمّ العودةُ تسأل عن الحال
      setBusy(true);
      setError(null);
      try {
        const opened = await openPaymentCheckout({
          methodId: method.id,
          purpose,
          amount,
          planId: purpose === "subscription" ? handoff?.planId : undefined,
        });
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
          purpose,
          amount,
          reference: reference.trim() || undefined,
          planId: purpose === "subscription" ? handoff?.planId : undefined,
          wallet: "driver",
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

  const title = purpose === "subscription" ? tr("دفع الاشتراك") : tr("شحن الرصيد");

  return (
    <div className="t2 t2-clq-page scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{title}</h1>
      </div>

      {done ? (
        <div className="t2-wdl-card t2-pr-done">
          <Icon name="schedule" />
          <h2 className="t2-pr-done-title">{tr("أرسلنا طلبك")}</h2>
          <p className="t2-pr-done-text">
            {purpose === "subscription"
              ? tr("يراجعه فريقُ المالية، وعند اعتماده تُشحن محفظتُك ويُفعَّل {0} منها.", { 0: handoff?.planName ?? tr("اشتراكك") })
              : tr("يراجعه فريقُ المالية ويُضاف {0} {1} إلى رصيدك بعد اعتماده.", { 0: digits(amount), 1: label })}
          </p>
          <button type="button" className="t2-clq-cta t2-pr-gap" onClick={() => navigate("/wallet")}>
            {tr("إلى المحفظة")}
          </button>
        </div>
      ) : methods === null ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : methods.length === 0 ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error ?? tr("لا طريقةَ دفعٍ متاحةٌ في بلدك الآن.")}
        </p>
      ) : (
        <>
          {purpose === "subscription" ? (
            <div className="t2-wdl-card">
              <span className="t2-pr-k">{handoff?.planName ?? tr("الاشتراك")}</span>
              <div className="t2-pr-amount">
                <span className="t2-pr-amount-num" dir="ltr">
                  {digits(amount)}
                </span>
                <span className="t2-pr-amount-cur">{label}</span>
              </div>
              <p className="t2-fld-hint">{tr("تُشحن محفظتُك بالمبلغ عند الاعتماد ثمّ يُشترى الاشتراكُ منها.")}</p>
            </div>
          ) : null}

          {cardMethod && purpose === "wallet_topup" ? (
            <button type="button" className="t2-wal-door t2-pr-gap" onClick={() => navigate("/wallet/card")}>
              <span className="t2-wal-txicon" aria-hidden="true">
                <span className="t2-icon">confirmation_number</span>
              </span>
              <span className="t2-wal-door-title">{tr("لديك بطاقة TAXO؟ أدخل رمزها")}</span>
              <span className="t2-icon t2-wal-door-go" aria-hidden="true">
                arrow_back
              </span>
            </button>
          ) : null}
          <div className="t2-section">{tr("طريقة الدفع")}</div>
          <div className="t2-list" role="radiogroup" aria-label={tr("طريقة الدفع")}>
            {methods.map((row) => (
              <button
                key={row.id}
                type="button"
                role="radio"
                aria-checked={row.id === methodId}
                className={row.id === methodId ? "t2-row t2-pr-opt on" : "t2-row t2-pr-opt"}
                onClick={() => {
                  setMethodId(row.id);
                  setReceipt(null);
                }}
              >
                <Icon name={KIND_ICON[row.kind]} />
                <span className="t2-row-main">
                  <span className="t2-row-title">{row.name}</span>
                  <span className="t2-row-body">
                    {row.gateway
                      ? tr("ادفع بالبطاقة في صفحة الوسيط — يُضاف فورَ تأكيده")
                      : row.requires_receipt
                        ? tr("حوّل ثمّ أرفق الإيصال — يُضاف بعد المراجعة")
                        : tr("ادفع ثمّ يُضاف بعد المراجعة")}
                  </span>
                </span>
                <Icon name={row.id === methodId ? "radio_button_checked" : "radio_button_unchecked"} />
              </button>
            ))}
          </div>

          {method && !method.gateway ? (
            <div className="t2-wdl-card t2-pr-gap t2-pr-dest" aria-label={tr("إلى أين تدفع")}>
              {method.account_number ? (
                <div className="t2-pr-line">
                  <span className="t2-pr-k">{method.kind === "phone_number" ? tr("رقم الهاتف") : tr("رقم الحساب")}</span>
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
                  <span className="t2-pr-k">{tr("باسم")}</span>
                  <span className="t2-pr-text">{method.account_holder}</span>
                </div>
              ) : null}
              {method.bank_name ? (
                <div className="t2-pr-line">
                  <span className="t2-pr-k">{tr("البنك")}</span>
                  <span className="t2-pr-text">{method.bank_name}</span>
                </div>
              ) : null}
              {method.instructions ? <p className="t2-pr-instructions">{method.instructions}</p> : null}
              {qrUrl ? <img className="t2-clq-qr" src={qrUrl} alt={tr("رمز QR لـ{0}", { 0: method.name })} /> : null}
            </div>
          ) : null}

          {purpose === "wallet_topup" ? (
            <div className="t2-pr-gap-lg">
              <label className="t2-fld-label" htmlFor="pay-request-amount">
                {tr("المبلغ (")}{label})
              </label>
              <input
                id="pay-request-amount"
                className="t2-fld"
                inputMode="decimal"
                dir="ltr"
                value={amount}
                onChange={(event) => setAmount(cleanAmount(event.target.value, currencyDecimals(currency)))}
              />
              {unitError ? (
                <p className="t2-note danger" role="alert">
                  <Icon name="error" fill />
                  {unitError}
                </p>
              ) : unit !== null ? (
                <p className="t2-fld-hint">{unitHint(unit, label)}</p>
              ) : null}
            </div>
          ) : null}

          {needsReceipt ? (
            <div className="t2-pr-gap-lg">
              <label className="t2-fld-label" htmlFor="pay-request-reference">
                {tr("رقم التحويل")}
              </label>
              <input
                id="pay-request-reference"
                className="t2-fld"
                dir="ltr"
                autoComplete="off"
                value={reference}
                onChange={(event) => setReference(event.target.value)}
              />
              <p className="t2-fld-hint">{tr("كما يظهر في الإيصال")}</p>

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

          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}
          {progress !== null && progress < 100 ? (
            <p className="t2-fld-hint">
              {tr("يُرفع الإيصال…")}{" "}<span dir="ltr">{progress}%</span>
            </p>
          ) : null}

          <button
            type="button"
            className="t2-clq-cta t2-pr-gap-lg"
            disabled={busy || !ready}
            aria-busy={busy}
            onClick={submit}
          >
            {busy ? tr("يُرسل…") : method?.gateway ? tr("ادفع في صفحة الوسيط") : tr("أرسل للمراجعة")}
          </button>
        </>
      )}
    </div>
  );
}
