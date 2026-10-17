/** الاشتراك — TAXO 2.0 «C10» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لا شاشةٌ ثانية**: الحالُ والخططُ والشراءُ وقنواتُه والتجديدُ التلقائيُّ من `useSubscriptionScreen`
 * (`screens/Subscription.tsx`) — **ومالٌ يخرج من محفظة كبتنٍ يمرّ بورقة التأكيد نفسِها** (`ConfirmSubscriptionSheet`) بقنواتها
 * الثلاث وعللها، كما في الشاشة القائمة: اللوحةُ ترسم الاختيارَ ثمّ الزرّ، والزرُّ يفتح التأكيدَ لا يخصم.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`design/TAXO2-DESIGN-CORRECTIONS.md` §٢٦):
 * - **«0%» و«كل أجرة تحصّلها لك كاملة»**: التصحيحاتُ §١ — «عمولة أقل بكثير من السوق» بلا نسبةٍ ولا وعدٍ مطلق.
 * - **«توفّر 6.286 د.أ»**: موازنةُ خطّةٍ بأخرى حسابُ مالٍ في الواجهة (§14) ولا حقلَ له — والخصمُ الحقيقيُّ (العرض) يُرسم في موضعه.
 * - **«الدفع من: المحفظة · بطاقة •••• 1188»**: البطاقةُ اليومَ صفحةُ المزوّد لا بطاقةٌ محفوظة — **فالدفعُ ببطاقةٍ محفوظةٍ مسارُ مالٍ
 *   جديد**؛ والقناةُ تُختار في ورقة التأكيد كما هي اليوم.
 *
 * **وما في الشاشة القائمة ولم يُرسم يبقى بلغة اللوحة**: التجديدُ التلقائيّ · سطرُ القنوات · الاشتراكاتُ السابقة.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listPaymentMethods } from "@/api/endpoints";
import type { PayMethod, SubscriptionDuration, SubscriptionPlan } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { DISPLAY_LOCALE, digits, formatAmount } from "@/lib/utils";
import {
  COPY,
  ConfirmSubscriptionSheet,
  formatRange,
  stateOf,
  useSubscriptionScreen,
  type State,
} from "@/screens/Subscription";

import { countDays, countHours } from "./count";

import "@/taxo2";
import "./t2.css"; import { tr } from "@/lib/i18n";

/** مدّةُ الخطة **كما كتبتها اللوحة** (C10). */
const DURATION_T2: Record<SubscriptionDuration, string> = {
  daily: tr("24 ساعة من لحظة الشراء"),
  weekly: tr("7 أيام"),
  monthly: tr("30 يوماً"),
};

/** **سطرُ الخطّة تحت اسمها** — مدّتُها، ثمّ عرضُها باسمه وموعده، أو ما استنفده منه (البند ٥٤). **بيتٌ واحدٌ لـC10 وC32**
 *  («عرض الباقات» قيد المراجعة): الخطّةُ نفسُها تُقال بالكلمات نفسِها في الصفحتين. **ومن لا يستحقّ لا يُقال له شيء.** */
export function planSubLine(row: SubscriptionPlan): string {
  const offer = row.offer_name
    ? ` · ${row.offer_name}${
        row.offer_ends_at
          ? tr(" — حتى {0}", { 0: digits(
              new Date(row.offer_ends_at).toLocaleDateString(DISPLAY_LOCALE, {
                day: "numeric",
                month: "numeric",
              }),
            ) })
          : ""
      }`
    : row.exhausted_offer_name
      ? tr(" · استفدتَ من «{0}» من قبل", { 0: row.exhausted_offer_name })
      : "";
  return `${DURATION_T2[row.duration_type]}${offer}`;
}

const CHIP: Record<State, { text: string; tone: string }> = {
  active: { text: tr("ساري"), tone: "ok" },
  expiring: { text: tr("ينتهي قريباً"), tone: "warn" },
  expired: { text: tr("منتهٍ"), tone: "danger" },
  none: { text: tr("لا اشتراك"), tone: "" },
};

/** «أسبوعي» ← «الأسبوعي» — والاسمُ المعرَّفُ يبقى كما هو، **واسمٌ لا يبدأ بحرفٍ عربيّ لا يُعرَّف** (§٧٦-ع/٢، المشكلة ٨): كان
 *  «اشترك بالTAXO X1». */
function definite(name: string): string {
  if (!/^[\u0600-\u06FF]/.test(name)) return name;
  return name.startsWith("ال") ? name : tr("ال{0}", { 0: name });
}

/** **ما بقي حتى نهاية التغطية** — وقتٌ لا مال، ومن `coverage_until` (أقصى انتهاءٍ لا الأحدث) كما في الشاشة القائمة. */
function remainingLine(until: string, now: number): string {
  const ms = new Date(until).getTime() - now;
  if (ms <= 0) return tr("انتهى");
  const totalHours = Math.floor(ms / 3_600_000);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  if (days === 0 && hours === 0) return tr("ينتهي خلال أقل من ساعة");
  if (days === 0) return tr("باقٍ {0}", { 0: countHours(hours) });
  if (hours === 0) return tr("باقٍ {0}", { 0: countDays(days) });
  return tr("باقٍ {0} و{1}", { 0: countDays(days), 1: countHours(hours) });
}

/** «ينتهي الخميس 9 أكتوبر · 23:59» — يومٌ وتاريخٌ وساعةٌ بخاناتٍ لاتينية. */
function endsLine(until: string): string {
  const date = new Date(until);
  const day = date.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long" });
  const dm = date.toLocaleDateString(DISPLAY_LOCALE, {
    day: "numeric",
    month: "long",
  });
  const time = date.toLocaleTimeString(DISPLAY_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return tr("ينتهي {0} {1} · {2}", { 0: day, 1: dm, 2: time });
}

export function SubscriptionT2Screen() {
  const s = useSubscriptionScreen();
  const navigate = useNavigate();
  const { profile } = useDriver();
  // **نظامُ الدفع الجديد** (SPEC §٧٣-هـ) — خيارٌ في ورقة التأكيد حيث مفتاحُه مشتعلٌ وحدَه
  const payRequests = useCountryConfig(profile?.user?.country_code)?.features.payment_requests_enabled === true;
  // **طرقُ دفع الاشتراك في السوق** (§٧٦-ع/٢، المشكلة ٦): البطاقةُ عبر Chargily تُفتح من «الدفع ببطاقة» لا من «بتحويلٍ أو نقداً»،
  // والتحويلُ والنقدُ لا يُعرضان إلا إن وُجدت طريقةٌ يدويّة
  const [methods, setMethods] = useState<PayMethod[] | null>(null);
  useEffect(() => {
    if (!payRequests) return;
    let alive = true;
    listPaymentMethods("subscription")
      .then((body) => alive && setMethods(body.methods))
      .catch(() => alive && setMethods([]));
    return () => {
      alive = false;
    };
  }, [payRequests]);
  const gatewayMethod = methods?.find((row) => row.gateway) ?? null;
  const gatewayName = gatewayMethod?.gateway_name ?? "Chargily";
  const hasManual = methods === null || methods.some((row) => !row.gateway && row.kind !== "purchase_code");
  const plans = s.subscription?.plans ?? [];
  const currentName = s.subscription?.current?.plan_name ?? null;
  // **المختارُ افتراضاً خطّتُه الحالية** — فالضغطةُ الأولى تجديدُ ما هو عليه، كما يقع في الشاشة القائمة
  const [picked, setPicked] = useState<string | null>(null);
  useEffect(() => {
    if (picked || plans.length === 0) return;
    setPicked((plans.find((plan) => plan.name === currentName) ?? plans[0]).id);
  }, [picked, plans, currentName]);

  if (s.loading) {
    return (
      <div className="t2 t2-sub t2-sub-loading">
        <Spinner />
      </div>
    );
  }

  const state = stateOf(s.subscription);
  const copy = COPY[state];
  const chip = CHIP[state];
  const current = s.subscription?.current ?? null;
  const until = s.subscription?.coverage_until ?? null;
  const now = Date.now();
  // **الشريطُ ما مضى من الفترة الحالية** — وقتٌ من بدايتها إلى نهايتها، لا مال
  const elapsed =
    current && s.subscription?.is_active
      ? Math.min(
          1,
          Math.max(
            0,
            (now - new Date(current.starts_at).getTime()) /
              (new Date(current.expires_at).getTime() -
                new Date(current.starts_at).getTime()),
          ),
        )
      : null;
  const plan: SubscriptionPlan | null =
    plans.find((row) => row.id === picked) ?? null;

  return (
    <div className="t2 t2-sub">
      <div className="t2-sub-scroll scr">
        <div className="t2-head">
          <button
            type="button"
            className="t2-back"
            aria-label={tr("رجوع")}
            onClick={() => s.goBack()}
          >
            <span className="t2-icon" aria-hidden="true">
              arrow_forward
            </span>
          </button>
          <h1 className="t2-title">{tr("الاشتراك")}</h1>
        </div>

        {/* بطاقةُ الحال: الخطّةُ وحالُها وما بقي ومتى ينتهي — وحالُ «منتهٍ» و«لا اشتراك» بنصّ الشاشة القائمة */}
        <div className="t2-sub-now">
          <div className="t2-sub-now-top">
            <span className="t2-sub-now-name">
              {s.subscription?.is_active && current
                ? current.plan_name
                : copy.title}
            </span>
            <span className={chip.tone ? `t2-chip ${chip.tone}` : "t2-chip"}>
              {chip.text}
            </span>
          </div>
          {s.subscription?.is_active && until ? (
            <>
              <div className="t2-sub-now-left">{remainingLine(until, now)}</div>
              {elapsed !== null ? (
                <div className="t2-sub-track" aria-hidden="true">
                  <div
                    className="t2-sub-fill"
                    style={{ width: `${Math.round(elapsed * 100)}%` }}
                  />
                </div>
              ) : null}
              <div className="t2-sub-now-end">{endsLine(until)}</div>
            </>
          ) : (
            <div className="t2-sub-now-left muted">{copy.body}</div>
          )}
        </div>

        {/* **العمولة بنصّ التصحيحات §١** — بلا نسبةٍ ولا وعدٍ مطلق */}
        <div className="t2-sub-perk">
          <span>
            <b>{tr("عمولة")}</b>{" "}{tr("أقل بكثير من السوق")}
          </span>
        </div>

        <div className="t2-section">{tr("باقتك القادمة")}</div>
        <div className="t2-sub-plans" role="radiogroup" aria-label={tr("الخطط")}>
          {plans.map((row) => {
            const on = row.id === picked;
            const isCurrent = currentName === row.name;
            return (
              <button
                key={row.id}
                type="button"
                role="radio"
                aria-checked={on}
                disabled={s.buying !== null}
                className={on ? "t2-sub-plan on" : "t2-sub-plan"}
                onClick={() => setPicked(row.id)}
              >
                <span className="t2-sub-radio" aria-hidden="true" />
                <span className="t2-sub-plan-main">
                  <span className="t2-sub-plan-name">
                    {row.name}
                    {isCurrent ? (
                      <span className="t2-sub-current">{tr("الحالية")}</span>
                    ) : null}
                  </span>
                  {/* **العرضُ اسمُه وموعدُه** (البند ٥٤) — ومن استنفده يُقال له، ومن لا يستحقّ لا يُرسم له شيء */}
                  <span
                    className={
                      row.offer_name ? "t2-sub-plan-sub ok" : "t2-sub-plan-sub"
                    }
                  >
                    {planSubLine(row)}
                  </span>
                </span>
                <span className="t2-sub-price">
                  {s.buying === row.id ? (
                    "…"
                  ) : (
                    <>
                      {/* **المشطوبُ بجانب المخفَّض** — والمخفَّضُ من الخلفية، فلا طرحَ هنا (§14). **ولا شطبَ بلا عرض**:
                          `price_after_discount` للعرض الحقيقيّ وحدَه، **والمرسومُ ما يُخصم** (`price_to_pay`، مقرَّباً — SPEC §٧٠-ج/٥) */}
                      {row.price_after_discount ? (
                        <span className="t2-sub-was">
                          {formatAmount(row.price, row.currency)}
                        </span>
                      ) : null}
                      <span className="t2-sub-num" dir="ltr">
                        {formatAmount(row.price_to_pay ?? row.price, row.currency)}
                      </span>{" "}
                      <span className="t2-sub-cur">
                        {CURRENCY_LABEL[row.currency]}
                      </span>
                    </>
                  )}
                </span>
              </button>
            );
          })}
        </div>

        {s.error ? (
          <p className="t2-note danger">
            <span className="t2-icon" aria-hidden="true">
              error
            </span>
            {s.error}
          </p>
        ) : null}
        {s.done ? <p className="t2-sub-done">{s.done}</p> : null}

        {/* ── ما في الشاشة القائمة ولم يُرسم: التجديدُ التلقائيّ، والقنوات، والسجلّ ── */}
        <button
          type="button"
          role="switch"
          aria-checked={s.autoRenew}
          aria-label={tr("التجديد التلقائي")}
          disabled={s.savingRenew}
          className="t2-sub-renew"
          onClick={() => void s.toggleRenew()}
        >
          <span className="t2-sub-renew-main">
            <span className="t2-sub-renew-title">{tr("التجديد التلقائي")}</span>
            <span className="t2-sub-renew-hint">
              {tr("يُخصم ثمنُ خطتك من محفظتك قبل الانتهاء بيوم. لا يقع بلا رصيدٍ كافٍ، ونُخبرك إن تعذّر.")}

            </span>
          </span>
          <span
            className={s.autoRenew ? "t2-switch on" : "t2-switch"}
            aria-hidden="true"
          >
            <span className="t2-switch-knob" />
          </span>
        </button>

        <p className="t2-sub-fine">
          {payRequests && gatewayMethod && hasManual
            ? tr("الشراء هنا من محفظتك، أو بالبطاقة عبر {0} ويُفعَّل فورَ تأكيده، أو بتحويلٍ أو نقداً ويُفعَّل بعد اعتماد فريق المالية.", { 0: gatewayName })
            : payRequests && gatewayMethod
            ? tr("الشراء هنا من محفظتك، أو بالبطاقة عبر {0} ويُفعَّل فورَ تأكيده.", { 0: gatewayName })
            : payRequests
            ? tr("الشراء هنا من محفظتك، أو بتحويلٍ أو نقداً بطرق سوقك — ويُفعَّل بعد أن يعتمد فريقُ المالية دفعتَك.")
            : s.cardEnabled
            ? tr("الشراء هنا من محفظتك أو ببطاقتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق.")
            : tr("الشراء هنا من رصيد محفظتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق.")}
        </p>

        {s.history.length > 0 ? (
          <>
            <div className="t2-section">{tr("اشتراكات سابقة")}</div>
            <div className="t2-list">
              {s.history.map((item) => (
                <div key={item.id} className="t2-row t2-sub-past">
                  <span className="t2-row-main">
                    <span className="t2-row-title">{item.plan_name}</span>
                    <span className="t2-row-body">
                      {formatRange(item.starts_at, item.expires_at)}
                    </span>
                    {/* **ما وُفِّر فعلاً** — `discount_amount` كما يصل، ولا طرح */}
                    {Number(item.discount_amount) > 0 ? (
                      <span className="t2-sub-saved">
                        {tr("وفّرتَ")}{" "}{formatAmount(item.discount_amount, item.currency)}{" "}
                        {CURRENCY_LABEL[item.currency]}
                      </span>
                    ) : null}
                  </span>
                  <span className="t2-sub-past-end">
                    <span className="t2-sub-past-amount">
                      {formatAmount(item.amount_paid, item.currency)} {CURRENCY_LABEL[item.currency]}
                    </span>
                    <span
                      className={
                        item.status === "active" ? "t2-chip ok" : "t2-chip"
                      }
                    >
                      {item.status === "active" ? tr("ساري") : tr("منتهٍ")}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>

      {/* **الذيلُ مثبَّتٌ أسفلَ الشاشة كما في اللوحة** — والزرُّ يفتح التأكيدَ لا يخصم: المبلغُ فيه ما يُخصم فعلاً،
          والقناةُ تُختار هناك كما هي اليوم */}
      <div className="t2-sub-foot">
        <button
          type="button"
          className="t2-sub-cta"
          disabled={!plan || s.buying !== null}
          onClick={() => plan && s.setConfirming(plan)}
        >
          {plan
            ? tr("اشترك في {0} · {1} {2}", { 0: definite(plan.name), 1: formatAmount(plan.price_to_pay ?? plan.price, plan.currency), 2: CURRENCY_LABEL[plan.currency] }

)
            : tr("اختر خطة")}
        </button>
        {s.subscription?.is_active && current ? (
          <p className="t2-sub-after">
            {tr("يبدأ بعد انتهاء اشتراكك الحالي، فلا يضيع منه شيء.")}

          </p>
        ) : null}
      </div>

      {s.confirming ? (
        // **ورقةُ التأكيد نفسُها** — بألوان الهوية عبر جسر الألوان القائمة (`.t2-legacy`)
        <div className="t2-legacy t2-sub-sheet">
          <ConfirmSubscriptionSheet
            plan={s.confirming}
            buying={s.buying}
            cardEnabled={s.cardEnabled}
            cliqAlias={s.cliqAlias}
            gateway={gatewayMethod ? { id: gatewayMethod.id, name: gatewayName } : null}
            manual={hasManual}
            onClose={() => s.setConfirming(null)}
            onWallet={s.payFromWallet}
            onCard={s.payByCard}
            onCliq={s.payByCliq}
            onPayRequest={
              payRequests
                ? (chosen, methodId) =>
                    navigate("/wallet/pay", {
                      state: {
                        purpose: "subscription",
                        planId: chosen.id,
                        planName: chosen.name,
                        amount: chosen.price_to_pay ?? chosen.price,
                        methodId,
                      },
                    })
                : undefined
            }
          />
        </div>
      ) : null}
    </div>
  );
}
