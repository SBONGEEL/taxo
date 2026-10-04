/** الاشتراك — TAXO 2.0 «C10» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لا شاشةٌ ثانية**: الحالُ والخططُ والشراءُ وقنواتُه والتجديدُ التلقائيُّ من `useSubscriptionScreen`
 * (`screens/Subscription.tsx`) — **ومالٌ يخرج من محفظة كبتنٍ يمرّ بورقة التأكيد نفسِها** (`ConfirmSubscriptionSheet`) بقنواتها
 * الثلاث وعللها، كما في الشاشة القائمة: اللوحةُ ترسم الاختيارَ ثمّ الزرّ، والزرُّ يفتح التأكيدَ لا يخصم.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`design/drafts/captain-C09-C12.md`):
 * - **«0%» و«كل أجرة تحصّلها لك كاملة»**: التصحيحاتُ §١ — «عمولة أقل بكثير من السوق» بلا نسبةٍ ولا وعدٍ مطلق.
 * - **«توفّر 6.286 د.أ»**: موازنةُ خطّةٍ بأخرى حسابُ مالٍ في الواجهة (§14) ولا حقلَ له — والخصمُ الحقيقيُّ (العرض) يُرسم في موضعه.
 * - **«الدفع من: المحفظة · بطاقة •••• 1188»**: البطاقةُ اليومَ صفحةُ المزوّد لا بطاقةٌ محفوظة — **فالدفعُ ببطاقةٍ محفوظةٍ مسارُ مالٍ
 *   جديد**؛ والقناةُ تُختار في ورقة التأكيد كما هي اليوم.
 *
 * **وما في الشاشة القائمة ولم يُرسم يبقى بلغة اللوحة**: التجديدُ التلقائيّ · سطرُ القنوات · الاشتراكاتُ السابقة.
 */

import { useEffect, useState } from "react";

import type { SubscriptionDuration, SubscriptionPlan } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";
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
import "./t2.css";

/** مدّةُ الخطة **كما كتبتها اللوحة** (C10). */
const DURATION_T2: Record<SubscriptionDuration, string> = {
  daily: "24 ساعة من لحظة الشراء",
  weekly: "7 أيام",
  monthly: "30 يوماً",
};

const CHIP: Record<State, { text: string; tone: string }> = {
  active: { text: "ساري", tone: "ok" },
  expiring: { text: "ينتهي قريباً", tone: "warn" },
  expired: { text: "منتهٍ", tone: "danger" },
  none: { text: "لا اشتراك", tone: "" },
};

/** «أسبوعي» ← «الأسبوعي» — والاسمُ المعرَّفُ يبقى كما هو. */
function definite(name: string): string {
  return name.startsWith("ال") ? name : `ال${name}`;
}

/** **ما بقي حتى نهاية التغطية** — وقتٌ لا مال، ومن `coverage_until` (أقصى انتهاءٍ لا الأحدث) كما في الشاشة القائمة. */
function remainingLine(until: string, now: number): string {
  const ms = new Date(until).getTime() - now;
  if (ms <= 0) return "انتهى";
  const totalHours = Math.floor(ms / 3_600_000);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  if (days === 0 && hours === 0) return "ينتهي خلال أقل من ساعة";
  if (days === 0) return `باقٍ ${countHours(hours)}`;
  if (hours === 0) return `باقٍ ${countDays(days)}`;
  return `باقٍ ${countDays(days)} و${countHours(hours)}`;
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
  return `ينتهي ${day} ${dm} · ${time}`;
}

export function SubscriptionT2Screen() {
  const s = useSubscriptionScreen();
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
            aria-label="رجوع"
            onClick={() => s.goBack()}
          >
            <span className="t2-icon" aria-hidden="true">
              arrow_forward
            </span>
          </button>
          <h1 className="t2-title">الاشتراك</h1>
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
            <b>عمولة</b> أقل بكثير من السوق
          </span>
        </div>

        <div className="t2-section">باقتك القادمة</div>
        <div className="t2-sub-plans" role="radiogroup" aria-label="الخطط">
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
                      <span className="t2-sub-current">الحالية</span>
                    ) : null}
                  </span>
                  {/* **العرضُ اسمُه وموعدُه** (البند ٥٤) — ومن استنفده يُقال له، ومن لا يستحقّ لا يُرسم له شيء */}
                  <span
                    className={
                      row.offer_name ? "t2-sub-plan-sub ok" : "t2-sub-plan-sub"
                    }
                  >
                    {DURATION_T2[row.duration_type]}
                    {row.offer_name
                      ? ` · ${row.offer_name}${
                          row.offer_ends_at
                            ? ` — حتى ${digits(
                                new Date(row.offer_ends_at).toLocaleDateString(
                                  DISPLAY_LOCALE,
                                  {
                                    day: "numeric",
                                    month: "numeric",
                                  },
                                ),
                              )}`
                            : ""
                        }`
                      : row.exhausted_offer_name
                        ? ` · استفدتَ من «${row.exhausted_offer_name}» من قبل`
                        : ""}
                  </span>
                </span>
                <span className="t2-sub-price">
                  {s.buying === row.id ? (
                    "…"
                  ) : (
                    <>
                      {/* **المشطوبُ بجانب المخفَّض** — والمخفَّضُ من الخلفية، فلا طرحَ هنا (§14) */}
                      {row.price_after_discount ? (
                        <span className="t2-sub-was">
                          {digits(row.price)}
                        </span>
                      ) : null}
                      <span className="t2-sub-num" dir="ltr">
                        {digits(row.price_after_discount ?? row.price)}
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
          aria-label="التجديد التلقائي"
          disabled={s.savingRenew}
          className="t2-sub-renew"
          onClick={() => void s.toggleRenew()}
        >
          <span className="t2-sub-renew-main">
            <span className="t2-sub-renew-title">التجديد التلقائي</span>
            <span className="t2-sub-renew-hint">
              يُخصم ثمنُ خطتك من محفظتك قبل الانتهاء بيوم. لا يقع بلا رصيدٍ
              كافٍ، ونُخبرك إن تعذّر.
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
          {s.cardEnabled
            ? "الشراء هنا من محفظتك أو ببطاقتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق."
            : "الشراء هنا من رصيد محفظتك. والكاش وكليك تسجّلهما الإدارة بعد قبض المال — ليست من التطبيق."}
        </p>

        {s.history.length > 0 ? (
          <>
            <div className="t2-section">اشتراكات سابقة</div>
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
                        وفّرتَ {digits(item.discount_amount)}{" "}
                        {CURRENCY_LABEL[item.currency]}
                      </span>
                    ) : null}
                  </span>
                  <span className="t2-sub-past-end">
                    <span className="t2-sub-past-amount">
                      {digits(item.amount_paid)} {CURRENCY_LABEL[item.currency]}
                    </span>
                    <span
                      className={
                        item.status === "active" ? "t2-chip ok" : "t2-chip"
                      }
                    >
                      {item.status === "active" ? "ساري" : "منتهٍ"}
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
            ? `اشترك ب${definite(plan.name)} — ${digits(plan.price_after_discount ?? plan.price)} ${
                CURRENCY_LABEL[plan.currency]
              }`
            : "اختر خطة"}
        </button>
        {s.subscription?.is_active && current ? (
          <p className="t2-sub-after">
            يبدأ بعد انتهاء {definite(current.plan_name)} الحالي، فلا يضيع منه
            شيء.
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
            onClose={() => s.setConfirming(null)}
            onWallet={s.payFromWallet}
            onCard={s.payByCard}
            onCliq={s.payByCliq}
          />
        </div>
      ) : null}
    </div>
  );
}
