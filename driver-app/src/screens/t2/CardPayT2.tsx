/** **الدفعُ بالبطاقة المصرفية** — اشتراكُ الكبتن ومستحقّاتُه ببطاقته البنكيّة (أمرُ المالك ٢٠٢٦-١١-١١، الأردن).
 *
 * **ما تقوله الصفحةُ قبل أن يدفع** — وكلُّه كما يصل من الخلفية، لا حسابَ هنا: المبلغُ بعملة سوقه، **وأنّ البطاقةَ تُخصم بالدولار** وبكم
 * لكلِّ دينار، **واسمُ شريك البطاقة ورسمُه على الدافع**، وأنّ الشريكَ قد يطلب هويّتَه أوّلَ مرّة، **وأنّ المبلغَ يصل TAXO أصلاً رقميّاً**.
 * **فلا يفاجئه شيءٌ في صفحة الشريك ولا في كشف حسابه** — والصدقُ في هذا شرطٌ دائمٌ لا يُرفع.
 *
 * **وصفحةُ البطاقة نفسُها صفحةُ الشريك** تُفتح كما تُفتح صفحاتُ الوسطاء (`goToCheckout`): **لا تمرّ بياناتُ البطاقة بخوادم TAXO**، والشريكُ
 * يمنع فتحَها داخل إطار (قِيس: `X-Frame-Options: DENY`) ويحتاج الكاميرا للتحقّق. **وشريطُ TAXO هنا** قبلها، والعودةُ إلى «نتيجة الدفع».
 *
 * **ولا شيءَ يتغيّر قبل أن يقول الوسيطُ «اكتمل»**: الاشتراكُ يُفعَّل أو المستحقّاتُ تُسدَّد في معاملة الاعتماد نفسِها.
 */

import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listPaymentMethods, openPaymentCheckout } from "@/api/endpoints";
import type { PayMethod, PaymentRequestPurpose } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { goToCheckout } from "@/lib/pay-return";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon, Wordmark } from "@/taxo2";

import "./fields.css";
import "./money.css";
import "./cardpay.css";
import { tr } from "@/lib/i18n";

/** **ما تحمله الشاشةُ التي فتحتها** — الغرضُ والمبلغُ كما حسبته الخلفية، والخطّةُ للاشتراك */
export interface CardPayHandoff {
  purpose: PaymentRequestPurpose;
  amount: string;
  planId?: string;
  planName?: string;
}

/** **طريقةُ البطاقة المصرفية من طرق السوق** — هي وحدَها تحمل عملةَ خصمٍ أخرى */
export function bankCardMethod(methods: PayMethod[] | null | undefined): PayMethod | null {
  return methods?.find((row) => row.gateway && row.charge_currency) ?? null;
}

export function CardPayT2Screen() {
  const location = useLocation();
  const navigate = useNavigate();
  const handoff = (location.state ?? null) as CardPayHandoff | null;
  const goBack = useGoBack(handoff?.purpose === "subscription" ? "/subscription" : "/account/debt");
  const [method, setMethod] = useState<PayMethod | null | undefined>(undefined);
  const [currency, setCurrency] = useState<keyof typeof CURRENCY_LABEL | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!handoff) return;
    let alive = true;
    listPaymentMethods(handoff.purpose)
      .then((body) => {
        if (!alive) return;
        setCurrency(body.currency);
        setMethod(bankCardMethod(body.methods));
      })
      .catch((caught: unknown) => {
        if (!alive) return;
        setMethod(null);
        setError(caught instanceof ApiError ? caught.message : tr("تعذّرت القراءة"));
      });
    return () => {
      alive = false;
    };
  }, [handoff]);

  async function pay() {
    if (!handoff || !method) return;
    setBusy(true);
    setError(null);
    try {
      const opened = await openPaymentCheckout({
        methodId: method.id,
        purpose: handoff.purpose,
        amount: handoff.amount,
        planId: handoff.purpose === "subscription" ? handoff.planId : undefined,
      });
      goToCheckout(opened.request.id, opened.checkout_url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر فتح صفحة الدفع — أعد المحاولة"));
      setBusy(false);
    }
  }

  const label = currency ? CURRENCY_LABEL[currency] : "";
  // **أقلُّ دفعٍ بالبطاقة** (قرارُ المالك ٢٠٢٦-١١-١١، حدُّ الطريقة من اللوحة) — تحتَه لا يُفتح الدفع ويُقال لماذا
  const floor = method?.min_amount ?? null;
  const belowFloor = handoff !== null && floor !== null && Number(handoff.amount) < Number(floor);

  return (
    <div className="t2 t2-cardpay scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{tr("الدفع بالبطاقة المصرفية")}</h1>
      </div>

      {/* **شريطُ TAXO** — قبل صفحة الشريك: من يدفع لمن، وأنّ البطاقةَ لا تصلنا */}
      <div className="t2-cardpay-bar">
        <Wordmark size={18} />
        <span className="t2-cardpay-bar-text">{tr("دفعٌ آمن — بياناتُ بطاقتك لا تصل إلى TAXO")}</span>
        <Icon name="lock" />
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}

      {!handoff ? (
        <p className="t2-note">{tr("افتح الدفعَ من صفحة الاشتراك أو من «المستحقّات عليك».")}</p>
      ) : method === undefined ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : method === null ? (
        <p className="t2-note">{tr("الدفع بالبطاقة المصرفية غير متاح الآن — ادفع بكليك أو حاول لاحقاً.")}</p>
      ) : (
        <>
          <section className="t2-cardpay-total">
            <span className="t2-cardpay-k">
              {handoff.purpose === "subscription"
                ? tr("اشتراك {0}", { 0: handoff.planName ?? "" })
                : tr("سداد المستحقّات")}
            </span>
            <span className="t2-cardpay-amount">
              <span className="t2-cardpay-num" dir="ltr">
                {digits(handoff.amount)}
              </span>
              <span className="t2-cardpay-cur">{label}</span>
            </span>
          </section>

          <ul className="t2-cardpay-facts">
            {method.charge_rate ? (
              <li>
                <Icon name="credit_card" />
                <span>
                  {tr("تُخصم بطاقتك بالدولار الأمريكي: الدينار الواحد = {0} دولار.", { 0: digits(method.charge_rate) })}
                </span>
              </li>
            ) : null}
            {method.partner ? (
              <li>
                <Icon name="receipt_long" />
                <span>
                  {method.fee_payer === "taxo"
                    ? tr("تُعالج البطاقةَ شركةُ {0}، ورسمُها تتحمّله TAXO: تُخصم بطاقتك مستحقَّك وحدَه. واسمُها ما يظهر في كشف حسابك.", {
                        0: method.partner,
                      })
                    : tr("تُعالج البطاقةَ شركةُ {0}، ورسمُها على الدافع: {1}. واسمُها ما يظهر في كشف حسابك.", {
                        0: method.partner,
                        1: method.partner_fee ?? "",
                      })}
                </span>
              </li>
            ) : null}
            {method.charge_rate ? (
              <li>
                <Icon name="account_balance" />
                <span>{tr("وقد يضيف بنكُك رسمَ تحويل العملة، فيختلف ما في كشف حسابك قليلاً.")}</span>
              </li>
            ) : null}
            <li>
              <Icon name="badge" />
              <span>{tr("قد يطلب الشريكُ أوّلَ مرّةٍ صورةَ هويّتك وصورةً شخصيّة للتحقّق.")}</span>
            </li>
            <li>
              <Icon name="info" />
              <span>{tr("يحوّل الشريكُ المبلغَ إلى أصلٍ رقميٍّ يصل حسابَ TAXO.")}</span>
            </li>
            <li>
              <Icon name="check_circle" />
              <span>
                {handoff.purpose === "subscription"
                  ? tr("يُفعَّل اشتراكُك فورَ اكتمال الدفع. وإن لم يكتمل لا يُخصم شيءٌ من محفظتك.")
                  : tr("تُخصم مستحقّاتُك فورَ اكتمال الدفع، ويعود استقبالُ الطلبات حين تبلغ صفراً.")}
              </span>
            </li>
          </ul>

          {belowFloor && floor !== null ? (
            <p className="t2-note">{tr("أقلُّ دفعٍ بالبطاقة {0} {1} — للمبالغ الأصغر ادفع بكليك.", { 0: digits(floor), 1: label })}</p>
          ) : (
            <button type="button" className="t2-debt-cta" disabled={busy || method.down === true} onClick={() => void pay()}>
              {busy ? tr("جارٍ…") : tr("تابع إلى صفحة البطاقة")}
            </button>
          )}
          {method.down ? (
            <p className="t2-note">{tr("صفحة البطاقة متوقّفة الآن — حاول بعد قليل أو ادفع بكليك.")}</p>
          ) : null}
          <button type="button" className="t2-link" onClick={() => navigate(-1)}>
            {tr("تراجع")}
          </button>
        </>
      )}
    </div>
  );
}
