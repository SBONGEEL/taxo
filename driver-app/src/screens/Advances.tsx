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
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getAdvanceState, repayAdvance, requestAdvance } from "@/api/endpoints";
import type { AdvanceRequirement, AdvanceState } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import type { Currency } from "@/api/types";
import { arabicDigits, cn } from "@/lib/utils";

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
    <li className="flex items-center justify-between gap-8 py-6">
      <span className="flex items-center gap-8">
        <span
          className={cn(
            "text-13 font-bold",
            item.met ? "text-ok" : "text-muted",
          )}
        >
          {item.met ? "✓" : "○"}
        </span>
        <span className="text-12.5 text-ink">
          {REQUIREMENT_TEXT[item.key] ?? item.key}
        </span>
      </span>
      {measured ? (
        <span
          className={cn(
            "text-11.5 tabular-nums",
            item.met ? "text-muted" : "text-warn",
          )}
        >
          {arabicDigits(item.value!)} / {arabicDigits(item.needed!)}
        </span>
      ) : null}
    </li>
  );
}

export function AdvancesScreen() {
  const goBack = useGoBack();
  const [state, setState] = useState<AdvanceState | null>(null);
  const [amount, setAmount] = useState("");
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

  if (!state) {
    return (
      <div className="h-full bg-bg px-16 pt-safe">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const currency = CURRENCY_LABEL[state.currency as Currency] ?? state.currency;
  const debt = state.debt;

  return (
    <div className="scr h-full bg-bg px-16 pb-nav pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">السلفة</h1>
      </div>

      {!state.offered ? (
        <section className="card p-15">
          <p className="text-13.5 font-semibold text-ink">السلف غير متاحة</p>
          <p className="mt-6 text-11.5 leading-snug text-muted">
            هذه الخدمة غير مفعّلة في سوقك حالياً.
          </p>
        </section>
      ) : null}

      {debt ? (
        <section
          className={cn(
            "mb-12 rounded-18 p-15",
            debt.overdue ? "border border-danger bg-surface" : "card",
          )}
        >
          <p className="text-13.5 font-semibold text-ink">
            {debt.overdue ? "سلفةٌ تجاوزت مهلتها" : "سلفتُك القائمة"}
          </p>
          <p className="mt-4 text-18 font-bold text-ink">
            {arabicDigits(debt.remaining)}{" "}
            <span className="text-12 font-medium text-muted">{currency}</span>
          </p>
          <p className="mt-6 text-11.5 leading-snug text-muted">
            {debt.overdue
              ? "أُوقفت الطلبات ولا يمكنك شراء اشتراكٍ يوميّ حتى تسدّد. ورحلتُك الجارية إن وُجدت تكمل."
              : `تُقتطع تلقائياً من أرباح رحلاتك، ومهلتُها ${arabicDigits(
                  new Date(debt.advance.due_at).toLocaleDateString("ar"),
                )}.`}
          </p>
          <Button
            className="mt-12"
            variant={debt.overdue ? "danger" : "secondary"}
            loading={busy}
            onClick={() => void run(repayAdvance)}
          >
            سدّد الباقي من المحفظة
          </Button>
        </section>
      ) : null}

      {state.offered && !debt ? (
        <>
          <section className="mb-12 card p-15">
            <p className="text-13.5 font-semibold text-ink">شروطُ السلفة</p>
            <ul className="mt-8 divide-y divide-line">
              {state.requirements.map((item) => (
                <Requirement key={item.key} item={item} />
              ))}
            </ul>
          </section>

          <section className="card p-15">
            <p className="text-13.5 font-semibold text-ink">سقفُك الحالي</p>
            <p className="mt-4 text-18 font-bold text-ink">
              {arabicDigits(state.cap)}{" "}
              <span className="text-12 font-medium text-muted">{currency}</span>
            </p>
            <p className="mb-12 mt-6 text-11.5 leading-snug text-muted">
              يكبر بعد كلِّ سلفةٍ تسدّدها في مهلتها. وما فوقه يحتاج موافقة
              الإدارة.
            </p>
            <Field
              label="المبلغ"
              inputMode="decimal"
              value={amount}
              disabled={busy || !state.eligible}
              onChange={(event) => setAmount(event.target.value)}
            />
            <Button
              className="mt-12"
              loading={busy}
              disabled={!state.eligible}
              onClick={() => void run(() => requestAdvance(amount))}
            >
              اطلب السلفة
            </Button>
          </section>
        </>
      ) : null}

      {error ? (
        <div className="mt-12">
          <ErrorNote message={error} />
        </div>
      ) : null}
    </div>
  );
}
