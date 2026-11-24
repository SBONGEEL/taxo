/** **شاشةُ «البطاقة وحدَها»** — بابُ صفحة البيع `taxo.tajora.ly/driver-access` (أمرُ المالك ٢٠٢٦-١١-٢٤،
 *  `design/OWNER-2026-11-24-DS24-CARD-ONLY-JO.md`).
 *
 * **لا تعرض إلا دفعَ بطاقة Digistore24 للباقة المختارة**: لا محفظةَ ولا كليك ولا نقدَ ولا رابطَ لطريقِ دفعٍ آخر — فصفحةُ البيع لا
 * تقود إلى غير Digistore24 (شرطُ قائمة موافقتهم). **ومرجعُ طلب الكبتن محمولٌ** كما في الشاشة العاديّة: الخادمُ يفتح طلباً باسمه ويضع
 * مرجعَه في `custom`. **وشاشةُ الاشتراك العاديّةُ لا تتغيّر** بطرقها كلِّها.
 *
 * **والأردنُّ وحدَه**: كبتنٌ دولةُ حسابه غيرُ الأردن يرى «هذه الخدمة غير متاحة في بلدك حالياً» ولا زرَّ دفع — **والخادمُ يرفض الدفعَ
 * نفسَه** (`payment_gateways.require_market`)، فالشاشةُ لا تحرس وحدَها. **ولا رابطَ إليها داخل التطبيق**: بابُها صفحةُ البيع وحدَها.
 *
 * `?plan=daily|weekly|monthly` يختار الباقة؛ وبلا معاملٍ تُعرض الباقاتُ التي تُدفع بالبطاقة الآن ليختار منها.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listPaymentMethods, listSubscriptionPlans, openPaymentCheckout } from "@/api/endpoints";
import type { PayMethod, SubscriptionDuration, SubscriptionPlan } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useDriver } from "@/lib/driver";
import { tr } from "@/lib/i18n";
import { goToCheckout } from "@/lib/pay-return";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { formatAmount } from "@/lib/utils";
import { Icon, Wordmark } from "@/taxo2";
import { DIGISTORE24, cardFits, payChannel } from "@/screens/t2/CardPayT2";

import "./t2.css";
import "./fields.css";
import "./money.css";
import "./cardpay.css";

/** **سوقُ Digistore24 الوحيد** — والخادمُ يحرس الشيءَ نفسَه */
export const CARD_PASS_COUNTRY = "JO";

const DURATIONS: readonly SubscriptionDuration[] = ["daily", "weekly", "monthly"];

/** **الباقةُ المطلوبة من الرابط** — قيمةٌ غيرُ معروفةٍ كغيابها */
export function requestedDuration(value: string | null): SubscriptionDuration | null {
  return DURATIONS.find((duration) => duration === value) ?? null;
}

/** **ما يُدفع بهذه البطاقة من الباقات** — الفعّالةُ التي يساوي ما يُدفع فيها مبلغاً ثابتاً للطريقة، يوماً فأسبوعاً فشهراً */
export function passPlans(plans: SubscriptionPlan[], method: PayMethod | null): SubscriptionPlan[] {
  if (!method) return [];
  return plans
    .filter((plan) => plan.is_active && cardFits(method, plan.price_to_pay ?? plan.price))
    .sort((a, b) => DURATIONS.indexOf(a.duration_type) - DURATIONS.indexOf(b.duration_type));
}

export function CardPassT2Screen() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { user } = useSession();
  const { profile } = useDriver();
  const country = profile?.user?.country_code ?? user?.country_code ?? null;
  const allowed = country === CARD_PASS_COUNTRY;
  const wanted = requestedDuration(params.get("plan"));

  const [method, setMethod] = useState<PayMethod | null | undefined>(undefined);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currency, setCurrency] = useState<keyof typeof CURRENCY_LABEL | null>(null);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !allowed) return;
    let alive = true;
    Promise.all([listPaymentMethods("subscription"), listSubscriptionPlans()])
      .then(([body, rows]) => {
        if (!alive) return;
        setCurrency(body.currency);
        // **صفُّ Digistore24 وحدَه** — لا بطاقةَ أخرى ولا غيرُها؛ وإن غاب قيل «غيرُ متاح» ولم يُعرض بديل
        setMethod(body.methods.find((row) => row.code === DIGISTORE24 && row.gateway) ?? null);
        setPlans(rows);
      })
      .catch((caught: unknown) => {
        if (!alive) return;
        setMethod(null);
        setError(caught instanceof ApiError ? caught.message : tr("تعذّرت القراءة"));
      });
    return () => {
      alive = false;
    };
  }, [user, allowed]);

  const offered = useMemo(() => passPlans(plans, method ?? null), [plans, method]);
  const chosen =
    offered.find((plan) => plan.id === chosenId) ??
    (wanted ? offered.find((plan) => plan.duration_type === wanted) : undefined) ??
    (offered.length === 1 ? offered[0] : undefined) ??
    null;
  const label = currency ? CURRENCY_LABEL[currency] : "";

  async function pay() {
    if (!method || !chosen) return;
    setBusy(true);
    setError(null);
    try {
      const opened = await openPaymentCheckout({
        methodId: method.id,
        purpose: "subscription",
        amount: chosen.price_to_pay ?? chosen.price,
        planId: chosen.id,
        channel: payChannel(),
      });
      goToCheckout(opened.request.id, opened.checkout_url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر فتح صفحة الدفع — أعد المحاولة"));
      setBusy(false);
    }
  }

  return (
    <div className="t2 t2-cardpay scr" data-card-pass>
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => navigate("/", { replace: true })}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{tr("الدفع بالبطاقة المصرفية")}</h1>
      </div>

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

      {!user ? (
        <>
          <p className="t2-note">{tr("سجّل الدخول بحساب الكبتن، ثمّ افتح هذا الرابط من جديد.")}</p>
          <button type="button" className="t2-debt-cta" onClick={() => navigate("/login")}>
            {tr("دخول")}
          </button>
        </>
      ) : country === null ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : !allowed ? (
        <p className="t2-note" role="status" data-card-pass-blocked>
          {tr("هذه الخدمة غير متاحة في بلدك حالياً")}
        </p>
      ) : method === undefined ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : method === null || offered.length === 0 ? (
        <p className="t2-note">{tr("الدفع بالبطاقة غير متاح الآن — حاول لاحقاً.")}</p>
      ) : (
        <>
          <div className="t2-sub-plans" role="radiogroup" aria-label={tr("الباقة")}>
            {offered.map((plan) => {
              const on = chosen?.id === plan.id;
              return (
                <button
                  key={plan.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  disabled={busy}
                  className={on ? "t2-sub-plan on" : "t2-sub-plan"}
                  onClick={() => setChosenId(plan.id)}
                >
                  <span className="t2-sub-radio" aria-hidden="true" />
                  <span className="t2-sub-plan-main">
                    <span className="t2-sub-plan-name">{plan.name}</span>
                  </span>
                  <span className="t2-sub-price">
                    <span className="t2-sub-num" dir="ltr">
                      {formatAmount(plan.price_to_pay ?? plan.price, currency)}
                    </span>{" "}
                    {label}
                  </span>
                </button>
              );
            })}
          </div>

          <ul className="t2-cardpay-facts">
            {method.partner ? (
              <li>
                <Icon name="receipt_long" />
                <span>
                  {tr("تُعالج البطاقةَ شركةُ {0}، ورسمُها تتحمّله TAXO: تُخصم بطاقتك مستحقَّك وحدَه. واسمُها ما يظهر في كشف حسابك.", {
                    0: method.partner,
                  })}
                </span>
              </li>
            ) : null}
            <li>
              <Icon name="check_circle" />
              <span>{tr("يُفعَّل اشتراكُك فورَ اكتمال الدفع، ولا يُخصم شيءٌ إن لم يكتمل.")}</span>
            </li>
          </ul>

          <button
            type="button"
            className="t2-debt-cta"
            disabled={busy || !chosen || method.down === true}
            onClick={() => void pay()}
          >
            {busy ? tr("جارٍ…") : chosen ? tr("تابع إلى صفحة البطاقة") : tr("اختر الباقة")}
          </button>
          {method.down ? <p className="t2-note">{tr("صفحة البطاقة متوقّفة الآن — حاول بعد قليل.")}</p> : null}
          <p className="t2-cardpay-fine">{tr("سيتم خصم القيمة من البطاقة بما يعادلها بالدولار")}</p>
          <p className="t2-cardpay-fine">{tr("ستُسأل عن الرمز البريدي لمدينتك، واختر «شخص خاص»")}</p>
        </>
      )}
    </div>
  );
}
