/** **مستحقّاتُ الكبتن** — TAXO 2.0 «C21» (`design/t2-new/captain/C21-*.dc.html`) — الترحيلة `0061`، قرارُ المالك 2026-08-30.
 *
 * **ونصُّ المحجوب يقول ثلاثةً لا «حسابك مجمَّد»** (نصُّ قراره): **المبلغَ بالضبط**، **وسبيلَ السداد**، **وأن العملَ يعود فور
 * السداد**. والثلاثةُ تأتي من الخلفية ولا تخترعها الشاشة — والرابعُ الذي لا يُقال: **لماذا نشأ**، وهو في كلِّ صفٍّ برحلته.
 *
 * **ولمَ صار للدَّين شاشةٌ أصلاً**: قبل اليوم كانت عمولةُ رحلةِ الكاش تُخصم من المحفظة، فمن لا رصيدَ له **لا يُنهي رحلته** والجملةُ
 * تقول «اشحن المحفظة» **وبابُ الشحن مُلغى**. فصار المستحقُّ في جدولِه، **ولا بدّ لجدولٍ يمنع الناسَ من العمل أن يكون له وجهٌ يُقرأ**.
 *
 * **والسدادُ جزئيٌّ مقبول**: يكتب ما يستطيع ويُنقص دَينَه — **والمنعُ يُرفع عند الصفر لا قبله**، وتقوله الشاشةُ صراحةً.
 *
 * **والمنطقُ هو هو حرفاً** (الطلبان، والحقلُ يُملأ بالمجموع، و«سدّد بكليك» يفتح مطالبةً ثمّ يعيد القراءة، ومطالبةٌ معلّقةٌ تفتح
 * تفاصيلَها). **وما تغيّر طبقةُ العرض**: المجموعُ برقم C09، **والبلاغُ الموقِفُ بحافّة C12 الحمراء**، والسدادُ بطاقةٌ بحقل الدخول
 * وزرّ الجمر — **وكان زرُّه أبيضَ بلا نصٍّ في الداكن** (لونُ العلامة القديم على الإسفلت، قِيس قبل البناء).
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDebtState, listMyDebtClaims, payDebtWithCliq } from "@/api/endpoints";
import type { DebtClaim, DriverDebtSource, DriverDebtState } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { notMultipleMessage, roundingUnit, unitHint } from "@/lib/rounding";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./t2/fields.css";
import "./t2/money.css";

// **خريطةٌ بنوعها لا `as const`** — فمصدرٌ يُضاف في الخلفية ولا اسمَ له هنا يُسقط `check:enum-coverage` بدل أن يُرسم مفتاحُه
const SOURCE_TEXT: Record<DriverDebtSource, string> = {
  ride_commission: "عمولة رحلة قبضتَ أجرتها نقداً",
  // **بين المدن** (§٦٣-ج/٧) — السيارةُ كاملةً قُبضت نقداً، وعمولتُها دَينٌ كعمولة النقد
  intercity_commission: "عمولةُ رحلةٍ بين المدن قُبضت نقداً",
};

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
    // **و«كلُّه» هو `pay_all_amount`** (SPEC §٧٠-ج/٦): الدَّينُ مقرَّباً للأعلى إلى وحدة السوق **محسوباً في الخلفية**، والزائدُ
    // يعود إلى محفظته قيداً صريحاً عند التأكيد. ومطفأً هو `total` حرفاً — فلا يتغيّر شيءٌ في سوقٍ لم يُشعَل
    setAmount((current) => current || next.pay_all_amount);
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
  // **الدفعةُ مضاعفٌ لوحدة التقريب حين تكون مشتعلة** (SPEC §٧٠-ج/٦) — حوالةٌ من بنكه في سوقٍ لا كسورَ فيه، والخلفيةُ تردّ غيرَها
  const { user } = useSession();
  const unit = roundingUnit(useCountryConfig(user?.country_code));
  const unitError = notMultipleMessage(amount, unit, currency);

  return (
    <div className="t2 t2-debt scr">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => goBack()}
        >
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">المستحقّات عليك</h1>
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
      {state === null && !error ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : null}

      {state ? (
        <>
          <section className="t2-debt-total">
            <span className="t2-debt-k">مجموع ما عليك</span>
            <span className="t2-debt-amount">
              <span className="t2-debt-num" dir="ltr">
                {digits(state.total)}
              </span>
              <span className="t2-debt-cur">{currency}</span>
            </span>
            {state.total === "0.000" ? (
              <p className="t2-debt-clear">
                <Icon name="check_circle" fill />
                لا مستحقّات عليك.
              </p>
            ) : null}
          </section>

          {/* **نصُّ المحجوب — ثلاثةٌ في فقرةٍ واحدة، لا «حسابك مجمَّد»** */}
          {state.blocked ? (
            <section className="t2-debt-alarm" role="alert">
              <div className="t2-debt-alarm-head">
                <span className="t2-debt-alarm-icon" aria-hidden="true">
                  <Icon name="lock" />
                </span>
                <h2 className="t2-debt-alarm-title">استقبال الطلبات موقوف</h2>
              </div>
              <p className="t2-debt-alarm-body">
                عليك {digits(state.total)} {currency} من عمولة رحلات قبضتَ
                أجرتها نقداً.
                {state.cliq_alias ? (
                  <>
                    {" "}
                    حوّل المبلغ بكليك إلى{" "}
                    <b dir="ltr" className="t2-debt-alias">
                      {state.cliq_alias}
                    </b>{" "}
                    ثم أكّد من الزرّ أدناه.
                  </>
                ) : (
                  " تواصل مع الإدارة لسداده — لم يُضبط حساب كليك لسوقك بعد."
                )}{" "}
                <b>ويعود العمل فور وصول السداد كاملاً.</b>
              </p>
              {/* **والجزئيُّ يُقال بعينه** فلا ينتظر رفعاً لا يأتي */}
              <p className="t2-debt-alarm-fine">
                السداد الجزئيّ مقبول ويُنقص المبلغ، لكن الاستقبال لا يعود إلا
                عند بلوغه صفراً.
              </p>
            </section>
          ) : null}

          {state.total !== "0.000" ? (
            <section className="t2-debt-pay">
              <label className="t2-fld-label" htmlFor="debt-amount">
                كم تريد أن تسدّد الآن؟
              </label>
              {/* **«سدّد كلَّه» بلاطةُ ورقة السحب نفسُها** (`t2-wds-tile`) — حين يُشعَل التقريبُ وحدَه: رقمُها `pay_all_amount` كما
                  حسبته الخلفية (الدَّينُ مقرَّباً للأعلى)، **وتعيد الحقلَ إليه** إن عدّله. ومطفأً الحقلُ يُملأ بالمستحقّ كما كان */}
              {unit !== null ? (
                <div className="t2-wds-quick">
                  <button
                    type="button"
                    aria-pressed={amount === state.pay_all_amount}
                    onClick={() => setAmount(state.pay_all_amount)}
                    className="t2-wds-tile"
                  >
                    <span className="t2-wds-tile-k">سدّد كلَّه</span>
                    <span className="t2-wds-tile-v">
                      <span className="t2-wds-tile-num" dir="ltr">
                        {digits(state.pay_all_amount)}
                      </span>{" "}
                      <span className="t2-wds-tile-cur">{currency}</span>
                    </span>
                  </button>
                </div>
              ) : null}
              <input
                id="debt-amount"
                className="t2-fld on-card t2-debt-input"
                dir="ltr"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
              {unitError ? (
                <p className="t2-note danger" role="alert">
                  <Icon name="error" fill />
                  {unitError}
                </p>
              ) : unit !== null ? (
                <p className="t2-fld-hint">
                  {unitHint(unit, currency)}
                  {state.pay_all_amount !== state.total
                    ? " — و«سدّد كلَّه» مقرَّبٌ للأعلى، والفرقُ يعود إلى محفظتك قيداً صريحاً عند التأكيد."
                    : ""}
                </p>
              ) : null}
              <p className="t2-fld-hint">
                تُفتح مطالبة بكليك، تحوّل المبلغ إلى الحساب المكتوب فيها، ثم
                يراجعها مشرف خلال {digits(String(state.review_min_minutes))} إلى{" "}
                {digits(String(state.review_max_minutes))} دقائق.
              </p>
              <button
                type="button"
                className="t2-debt-cta"
                onClick={() => void pay()}
                disabled={busy || !state.cliq_alias || unitError !== null}
              >
                {busy ? "جارٍ…" : "سدّد بكليك"}
              </button>
              {!state.cliq_alias ? (
                <p className="t2-debt-warn">
                  لم يُضبط حساب كليك لسوقك بعد — تواصل مع الإدارة.
                </p>
              ) : null}
            </section>
          ) : null}

          {pending.length > 0 ? (
            <>
              <h2 className="t2-section">مطالبة بانتظار التأكيد</h2>
              <div className="t2-debt-list">
                {pending.map((claim) => (
                  <button
                    key={claim.id}
                    type="button"
                    className="t2-debt-claim"
                    onClick={() => navigate(`/debt/cliq/${claim.id}`)}
                  >
                    <span className="t2-debt-claim-icon" aria-hidden="true">
                      <Icon name="schedule" />
                    </span>
                    <span className="t2-debt-claim-amount">
                      <span dir="ltr">{digits(claim.amount)}</span>{" "}
                      {CURRENCY_LABEL[claim.currency]}
                    </span>
                    <span className="t2-debt-claim-open">افتح التفاصيل</span>
                    <Icon name="chevron_left" className="t2-debt-claim-go" />
                  </button>
                ))}
              </div>
            </>
          ) : null}

          {state.rows.length > 0 ? (
            <>
              <h2 className="t2-section">ممّ نشأت</h2>
              <div className="t2-debt-list">
                {state.rows.map((row) => (
                  <div key={row.id} className="t2-debt-row">
                    <span className="t2-debt-row-k">{SOURCE_TEXT[row.source]}</span>
                    <span dir="ltr" className="t2-debt-row-v">
                      {digits(row.amount)}
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
