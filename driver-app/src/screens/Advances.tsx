/** سلفةُ الكبتن (البند ١٥) — الشروطُ بأسمائها، والسقفُ، والدَّينُ ومهلتُه.
 *
 * **وهذه الشاشةُ هي القرار ١ في شكله المرئي**: كلُّ شرطٍ سطرٌ باسمه ورقمه
 * وعلامته. ورقمٌ مركَّبٌ واحد («مصداقيتك ٣٫٢») يجعل من مُنع لا يعرف ماذا يفعل،
 * فيتّصل بالدعم — وهو ما تمنعه قائمةٌ يقرأ فيها «رحلاتٌ مكتملة ٣١ من ٥٠».
 *
 * وثلاثةُ فروقٍ في النصِّ مقصودةٌ كلُّها:
 *
 * ١. **«غيرُ معروضة» غيرُ «رُفضتَ»**: بابٌ لا وجودَ له في هذا السوق، لا بابٌ
 *    يُفتح بعملٍ يقوم به. وخلطُهما يجعله يسعى إلى شرطٍ لن يفتح شيئاً.
 * ٢. **والمهلةُ تُقال بتاريخها**، لا «باقٍ أيام»: التاريخُ يُكتب في مفكرةٍ،
 *    والعدُّ التنازليُّ يُقرأ مرةً ويُنسى.
 * ٣. **والإيقافُ يُقال بسببه ومقداره وطريقِ الخروج منه** — «حسابك موقوف» وحدها
 *    تذكرةُ دعمٍ مضمونة.
 *
 * **بلغة TAXO 2.0** «C24» (`design/t2-new/captain/C24*.dc.html`): الشروطُ صفوفُ «CW1» (الشروط)، والسقفُ والدَّينُ بأرقام «C09»،
 * والطلبُ زرُّ الجمر في ذيلٍ مثبَّت (C10) **يفتح ورقةَ التأكيد ولا يطلب** — والمنطقُ حرفاً: النداءاتُ الثلاثة، وشرطا تعطيل
 * الحقل والزرّ، وورقةُ التأكيد بالمبلغ وشرطِ السداد قبل الموافقة.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getAdvanceState, repayAdvance, requestAdvance } from "@/api/endpoints";
import type { AdvanceRequirement, AdvanceState } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import type { Currency } from "@/api/types";
import { digits,
  DISPLAY_LOCALE,
} from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

/** **النصُّ هنا والرمزُ من الخلفية** — كموانع إلغاء التفعيل تماماً. */
const REQUIREMENT_TEXT: Record<string, string> = {
  approved: "حسابٌ معتمد",
  past_subscription: "اشتراكٌ أسبوعيٌّ أو شهريٌّ سابق",
  completed_rides: "رحلاتٌ مكتملة",
  rating: "متوسّطُ التقييم",
  no_open_dispute: "لا نزاعَ مفتوح",
  no_outstanding_advance: "لا سلفةَ قائمة",
};

function Requirement({ item }: { item: AdvanceRequirement }) {
  // **وشرطٌ حدُّه صفرٌ ليس شرطاً**: «رحلاتٌ مكتملة ٧ / ٠» تخترع مقارنةً حيث
  // لا مطلوب، فيقرؤها صاحبُها عتبةً لا يفهمها. فيُعرض الرقمُ وحدَه
  const measured = item.value !== null && Number(item.needed ?? 0) > 0;
  return (
    <li className={item.met ? "t2-adv-req met" : "t2-adv-req"}>
      {/* **علامةٌ لا لونٌ وحدَه** — ممتلئةٌ لما استُوفي، ودائرةٌ فارغةٌ لما ينقص */}
      <Icon
        name={item.met ? "check_circle" : "radio_button_unchecked"}
        fill={item.met}
      />
      <span className="t2-adv-req-label">
        {REQUIREMENT_TEXT[item.key] ?? item.key}
      </span>
      {measured ? (
        <span className="t2-adv-req-value" dir="ltr">
          {digits(item.value!)} / {digits(item.needed!)}
        </span>
      ) : null}
    </li>
  );
}

/** المبلغُ بخطّ الأرقام وعملتُه — كما يصل من الخلفية، بلا حساب. */
function Money({ value, currency }: { value: string; currency: string }) {
  return (
    <div className="t2-ax-money">
      <span className="t2-ax-money-num" dir="ltr">
        {digits(value)}
      </span>
      <span className="t2-ax-money-cur">{currency}</span>
    </div>
  );
}

export function AdvancesScreen() {
  const goBack = useGoBack();
  const [state, setState] = useState<AdvanceState | null>(null);
  const [amount, setAmount] = useState("");
  // **ورقةُ تأكيدٍ لأنها تُنشئ ديناً لا تُنفق رصيداً** (قرارُ المالك
  // 2026-08-19): من يوافق يجب أن يرى **كيف يُسترجَع** قبل الموافقة لا بعدها —
  // وكانت الشاشةُ تطلب المبلغ ولا تقول شيئاً عن الاقتطاع.
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getAdvanceState()
      .then((next) => {
        setState(next);
        setAmount((current) => current || next.cap);
      })
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, []);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  const header = (
    <div className="t2-head">
      <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
        <Icon name="arrow_forward" />
      </button>
      <h1 className="t2-title">السلفة</h1>
    </div>
  );

  const errorNote = error ? (
    <p className="t2-note danger" role="alert">
      <Icon name="error" />
      {error}
    </p>
  ) : null;

  if (!state) {
    return (
      <div className="t2 t2-ax">
        <div className="t2-ax-scroll">
          {header}
          {error ? (
            errorNote
          ) : (
            <div className="t2-ax-center">
              <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
            </div>
          )}
        </div>
      </div>
    );
  }

  const currency = CURRENCY_LABEL[state.currency as Currency] ?? state.currency;
  const debt = state.debt;
  // **الطلبُ ذيلٌ مثبَّتٌ لمن عُرضت عليه ولا دَينَ عليه** — شرطُ قسم الطلب نفسُه
  const asking = state.offered && !debt;

  return (
    <div className="t2 t2-ax">
      <div className={asking ? "t2-ax-scroll has-foot" : "t2-ax-scroll"}>
        {header}

        {!state.offered ? (
          <section className="t2-empty t2-ax-empty">
            <b>السلف غير متاحة</b>
            <span>هذه الخدمة غير مفعّلة في سوقك حالياً.</span>
          </section>
        ) : null}

        {debt ? (
          <section
            className={debt.overdue ? "t2-ax-card t2-adv-debt overdue" : "t2-ax-card t2-adv-debt"}
          >
            <p className={debt.overdue ? "t2-adv-k danger" : "t2-adv-k"}>
              {debt.overdue ? "سلفةٌ تجاوزت مهلتها" : "سلفتُك القائمة"}
            </p>
            <Money value={debt.remaining} currency={currency} />
            {debt.overdue ? (
              <p className="t2-adv-stop">
                <Icon name="error" fill />
                <span>أُوقفت الطلبات ولا يمكنك شراء اشتراكٍ يوميّ حتى تسدّد. ورحلتُك الجارية إن وُجدت تكمل.</span>
              </p>
            ) : (
              <p className="t2-adv-line">
                {`تُقتطع تلقائياً من أرباح رحلاتك، ومهلتُها ${digits(
                  new Date(debt.advance.due_at).toLocaleDateString(DISPLAY_LOCALE),
                )}.`}
              </p>
            )}
            <button
              type="button"
              className={debt.overdue ? "t2-ax-danger t2-adv-repay" : "t2-ax-ghost t2-adv-repay"}
              disabled={busy}
              onClick={() => void run(repayAdvance)}
            >
              {busy ? "…" : "سدّد الباقي من المحفظة"}
            </button>
          </section>
        ) : null}

        {asking ? (
          <>
            <section aria-labelledby="t2-adv-reqs">
              <h2 id="t2-adv-reqs" className="t2-adv-reqs-label">شروطُ السلفة</h2>
              <ul className="t2-adv-reqs">
                {state.requirements.map((item) => (
                  <Requirement key={item.key} item={item} />
                ))}
              </ul>
            </section>

            <section className="t2-ax-card t2-adv-cap">
              <p className="t2-adv-k">سقفُك الحالي</p>
              <Money value={state.cap} currency={currency} />
              <p className="t2-ax-hint">
                يكبر بعد كلِّ سلفةٍ تسدّدها في مهلتها. وما فوقه يحتاج موافقة
                الإدارة.
              </p>
              <label className="t2-ax-label" htmlFor="t2-adv-amount">
                المبلغ
              </label>
              <input
                id="t2-adv-amount"
                className="t2-ax-field"
                inputMode="decimal"
                value={amount}
                disabled={busy || !state.eligible}
                onChange={(event) => setAmount(event.target.value)}
              />
            </section>
          </>
        ) : null}

        {errorNote}
      </div>

      {asking ? (
        <div className="t2-ax-foot">
          <button
            type="button"
            className="t2-ax-cta"
            disabled={busy || !state.eligible || Number(amount) <= 0}
            onClick={() => setConfirming(true)}
          >
            {busy ? "…" : "اطلب السلفة"}
          </button>
        </div>
      ) : null}

      {confirming && state ? (
        <div
          className="t2-ax-sheet"
          onClick={() => setConfirming(false)}
        >
          <div
            className="t2-ax-sheet-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="t2-adv-confirm"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="t2-ax-grab" aria-hidden="true" />
            <h2 id="t2-adv-confirm" className="t2-ax-sheet-title">تأكيد طلب السلفة</h2>
            {/* **الجملةُ تقول إنه دَين، لا «سيصلك مبلغ»** */}
            <p className="t2-adv-sub">
              هذه سلفةٌ تُسترجَع من دخلك، لا رصيدٌ يُمنح.
            </p>

            <div className="t2-adv-box">
              <div className="t2-adv-box-row">
                <span>المبلغ</span>
                <Money value={amount} currency={currency} />
              </div>
              <div className="t2-adv-box-rule" />
              <p className="t2-adv-box-title">شرطُ السداد</p>
              {/* **وحدٌّ أدنى صفرُه لا يُنطق شرطاً** — نفسُ قاعدة قائمة
                  الشروط أعلاه، حيث «٧ / ٠» تُخفى لأنها تخترع مقارنةً حيث لا
                  مطلوب. وهنا أسوأ: «ويبقى لك ٠٫٠٠٠ على الأقل» جملةٌ تَعِد
                  بشيءٍ وتعطي لا شيء، فيقرؤها صاحبُها ضماناً لا وجودَ له */}
              <p className="t2-adv-box-text">
                يُقتطع {digits(String(state.deduction_percent))}٪ من كل
                رحلةٍ يدخل مالُها محفظتَك
                {Number(state.min_kept_amount) > 0
                  ? `، ويبقى لك منها ${digits(
                      state.min_kept_amount,
                    )} ${currency} على الأقل.`
                  : "."}
                {state.term_days
                  ? ` والمهلةُ ${digits(String(state.term_days))} يوماً.`
                  : ""}
              </p>
            </div>

            <div className="t2-ax-sheet-actions">
              <button
                type="button"
                className="t2-ax-cta"
                disabled={busy}
                onClick={() => {
                  setConfirming(false);
                  void run(() => requestAdvance(amount));
                }}
              >
                {busy ? "…" : "أوافق — اطلب السلفة"}
              </button>
              <button
                type="button"
                className="t2-ax-quiet"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                رجوع
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
