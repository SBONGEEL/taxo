/** **مستحقّاتُ الكبتن** — الترحيلة `0061`، قرارُ المالك 2026-08-30.
 *
 * **ونصُّ المحجوب يقول ثلاثةً لا «حسابك مجمَّد»** (نصُّ قراره): **المبلغَ
 * بالضبط**، **وسبيلَ السداد**، **وأن العملَ يعود فور السداد**. والثلاثةُ
 * تأتي من الخلفية ولا تخترعها الشاشة — والرابعُ الذي لا يُقال: **لماذا نشأ**،
 * وهو في كلِّ صفٍّ برحلته.
 *
 * **ولمَ صار للدَّين شاشةٌ أصلاً**: قبل اليوم كانت عمولةُ رحلةِ الكاش تُخصم
 * من المحفظة، فمن لا رصيدَ له **لا يُنهي رحلته** والجملةُ تقول «اشحن
 * المحفظة» **وبابُ الشحن مُلغى**. فصار المستحقُّ في جدولِه، **ولا بدّ لجدولٍ
 * يمنع الناسَ من العمل أن يكون له وجهٌ يُقرأ**.
 *
 * **والسدادُ جزئيٌّ مقبول**: يكتب ما يستطيع ويُنقص دَينَه — **والمنعُ يُرفع
 * عند الصفر لا قبله**، وتقوله الشاشةُ صراحةً فلا ينتظر ما لا يأتي.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDebtState, listMyDebtClaims, payDebtWithCliq } from "@/api/endpoints";
import type { DebtClaim, DriverDebtState } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

const SOURCE_TEXT = {
  ride_commission: "عمولة رحلة قبضتَ أجرتها نقداً",
} as const;

export function DebtScreen() {
  const goBack = useGoBack("/account");
  const navigate = useNavigate();
  const [state, setState] = useState<DriverDebtState | null>(null);
  const [claims, setClaims] = useState<DebtClaim[]>([]);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [next, rows] = await Promise.all([getDebtState(), listMyDebtClaims()]);
    setState(next);
    setClaims(rows);
    // **الحقلُ يُملأ بالمستحقّ كلِّه** — والأغلبُ أن يسدّده كاملاً، ومن أراد
    // أقلَّ عدّله. **ولا يُقفل**: الجزئيُّ مقبولٌ بقرار المالك.
    setAmount((current) => current || next.total);
  }, []);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّرت القراءة"),
    );
  }, [load]);

  const pay = async () => {
    setBusy(true);
    setError(null);
    try {
      await payDebtWithCliq(amount);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر فتح المطالبة");
    } finally {
      setBusy(false);
    }
  };

  const currency = state ? CURRENCY_LABEL[state.currency] : "";
  const pending = claims.filter((claim) => claim.status === "created");

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">المستحقّات عليك</h1>
      </div>

      <ErrorNote message={error} />
      {state === null && !error ? <Spinner className="mx-auto" /> : null}

      {state ? (
        <>
          <section className="mb-12 rounded-20 border border-line bg-surface p-20 text-center">
            <div className="text-12 text-muted">مجموع ما عليك</div>
            <div className="mt-4 text-34 font-bold leading-hero text-ink">
              {digits(state.total)} {currency}
            </div>
            {state.total === "0.000" ? (
              <p className="mt-10 text-12 text-ok">لا مستحقّات عليك.</p>
            ) : null}
          </section>

          {/* **نصُّ المحجوب — ثلاثةٌ في فقرةٍ واحدة، لا «حسابك مجمَّد»** */}
          {state.blocked ? (
            <section
              className="mb-12 rounded-20 border border-danger bg-surface p-20"
              role="alert"
            >
              <h2 className="text-15 font-bold text-danger">
                استقبال الطلبات موقوف
              </h2>
              <p className="mt-8 text-12.5 leading-note text-ink">
                عليك {digits(state.total)} {currency} من عمولة رحلات قبضتَ
                أجرتها نقداً.
                {state.cliq_alias ? (
                  <>
                    {" "}
                    حوّل المبلغ بكليك إلى{" "}
                    <span dir="ltr" className="select-all font-bold">
                      {state.cliq_alias}
                    </span>{" "}
                    ثم أكّد من الزرّ أدناه.
                  </>
                ) : (
                  " تواصل مع الإدارة لسداده — لم يُضبط حساب كليك لسوقك بعد."
                )}{" "}
                <span className="font-bold">
                  ويعود العمل فور وصول السداد كاملاً.
                </span>
              </p>
              {/* **والجزئيُّ يُقال بعينه** فلا ينتظر رفعاً لا يأتي */}
              <p className="mt-8 text-11 leading-note text-muted">
                السداد الجزئيّ مقبول ويُنقص المبلغ، لكن الاستقبال لا يعود إلا
                عند بلوغه صفراً.
              </p>
            </section>
          ) : null}

          {state.total !== "0.000" ? (
            <section className="mb-12 rounded-20 border border-line bg-surface p-20">
              <label
                htmlFor="debt-amount"
                className="text-12.5 font-bold text-ink"
              >
                كم تريد أن تسدّد الآن؟
              </label>
              <input
                id="debt-amount"
                dir="ltr"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="mt-8 w-full rounded-14 border border-line bg-surface-2 px-14 py-12 text-center text-18 font-bold text-ink"
              />
              <p className="mt-8 text-11 leading-note text-muted">
                تُفتح مطالبة بكليك، تحوّل المبلغ إلى الحساب المكتوب فيها، ثم
                يراجعها مشرف خلال {digits(String(state.review_min_minutes))} إلى{" "}
                {digits(String(state.review_max_minutes))} دقائق.
              </p>
              <button
                type="button"
                onClick={() => void pay()}
                disabled={busy || !state.cliq_alias}
                className="pressable mt-12 w-full rounded-14 bg-brand px-16 py-14 text-14 font-bold text-on-brand disabled:opacity-50"
              >
                {busy ? "جارٍ…" : "سدّد بكليك"}
              </button>
              {!state.cliq_alias ? (
                <p className="mt-8 text-11 leading-note text-warn">
                  لم يُضبط حساب كليك لسوقك بعد — تواصل مع الإدارة.
                </p>
              ) : null}
            </section>
          ) : null}

          {pending.length > 0 ? (
            <section className="mb-12 rounded-20 border border-line bg-surface p-20">
              <h2 className="text-13.5 font-bold text-ink">
                مطالبة بانتظار التأكيد
              </h2>
              {pending.map((claim) => (
                <button
                  key={claim.id}
                  type="button"
                  onClick={() => navigate(`/debt/cliq/${claim.id}`)}
                  className="pressable mt-10 flex w-full items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12"
                >
                  <span className="text-13 font-bold text-ink">
                    {digits(claim.amount)} {CURRENCY_LABEL[claim.currency]}
                  </span>
                  <span className="text-11.5 text-warn">افتح التفاصيل ←</span>
                </button>
              ))}
            </section>
          ) : null}

          {state.rows.length > 0 ? (
            <section className="rounded-20 border border-line bg-surface p-20">
              <h2 className="text-13.5 font-bold text-ink">ممّ نشأت</h2>
              {state.rows.map((row) => (
                <div
                  key={row.id}
                  className="mt-10 flex items-baseline justify-between border-t border-line pt-10 first:border-0 first:pt-0"
                >
                  <span className="text-11.5 leading-note text-muted">
                    {SOURCE_TEXT[row.source]}
                  </span>
                  <span dir="ltr" className="text-13 font-bold text-ink">
                    {digits(row.amount)}
                  </span>
                </div>
              ))}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
