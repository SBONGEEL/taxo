/** **بالساعة** (§٦٣-ج/٥) — وجوهُها في تطبيق الراكب: كتلةُ الساعات في ورقة الطلب «R06»، وكتلتُها في ورقة التتبّع، وساعتُها.
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية كما هي، **ولا شكلَ يُخترع**: رأسُ «اختر الفئة» (`t2-pick-head`)،
 * وبطاقةُ المسار للعدّاد والسعر (`t2-share`)، **وبطاقتا «من يدفع» في الطرد لمن أين يُدفع المحجوز** (`t2-cats t2-fo-payers`)،
 * وكتلةُ «لشخص آخر» في التتبّع (`t2-fo-ride`) بزرّها الثانويّ. **والتخطيطُ وحدَه في `hourly.css`** بالرموز.
 *
 * **ولا مالَ يُحسب هنا** (§14): سعرُ الساعة وكيلومتراتُها وسقفُها والمجموعُ من التقدير، والكيلومتراتُ المشمولةُ من الرحلة —
 * **والعدّادُ يسأل الخلفيةَ بكلِّ ضغطة** (`useConfirmRide`). وما يُحسب هنا وقتٌ: الباقي من الساعات وما زاد عليها (`lib/hourly`).
 */

import type { HourlyPrepay, Ride, RideEstimate, RideHourly } from "@/api/types";
import { ErrorNote } from "@/components/ui/Feedback";
import { forHours, hoursLabel } from "@/lib/hourly";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./t2.css";
import "./for-other.css";
import "./hourly.css";

const PREPAY: Array<{ value: HourlyPrepay; icon: string; label: string; hint: string }> = [
  { value: "wallet", icon: "account_balance_wallet", label: "من المحفظة عند البدء", hint: "تُخصم كاملةً لحظةَ يبدأ الكبتن الرحلة" },
  { value: "cash", icon: "payments", label: "نقداً للكبتن عند البدء", hint: "تسلّمها له بيدك قبل الانطلاق" },
];

/** **كتلةُ الساعات في ورقة الطلب** — العدّادُ (١ إلى سقف السوق)، وسطرُ «8.000 للساعة شاملةً 15 كم»، والمجموعُ «لـ 3 ساعات»،
 *  **ثمّ من أين يُدفع المحجوز**. والسقفُ من التقدير: قبل وصوله لا زيادة، **ولا رقمَ يُخمَّن مكانَه**. */
export function HourlySheetT2({
  estimate,
  loading,
  draft,
  onChange,
  currency,
}: {
  estimate: RideEstimate | null;
  loading: boolean;
  draft: RideHourly;
  onChange: (next: RideHourly) => void;
  currency: string | undefined;
}) {
  const max = estimate?.hourly_max_hours ?? null;
  const rate = estimate?.hourly_rate ?? null;
  const km = estimate?.hourly_km_per_hour ?? null;
  return (
    <>
      <div className="t2-pick-head">
        <span className="t2-pick-title">بالساعة · اقتصادي</span>
      </div>
      <div className="t2-share t2-hr-box">
        <div className="t2-hr-hours">
          <span className="t2-hr-hours-label">
            <Icon name="timer" />
            الساعات
          </span>
          {/* **العدّادُ بين حدّين**: لا أقلَّ من ساعة، ولا فوق سقف السوق — والخلفيةُ ترفض ما خرج عنهما على أيِّ حال */}
          <div className="t2-hr-stepper">
            <button
              type="button"
              className="t2-route-add t2-hr-step"
              aria-label="ساعةٌ أقل"
              disabled={draft.hours <= 1}
              onClick={() => onChange({ ...draft, hours: draft.hours - 1 })}
            >
              <Icon name="remove" />
            </button>
            <span className="t2-hr-count" dir="ltr" aria-live="polite">
              {draft.hours}
            </span>
            <button
              type="button"
              className="t2-route-add t2-hr-step"
              aria-label="ساعةٌ أكثر"
              disabled={max === null || draft.hours >= max}
              onClick={() => onChange({ ...draft, hours: draft.hours + 1 })}
            >
              <Icon name="add" />
            </button>
          </div>
        </div>
        {/* **سعرُ الساعة وكيلومتراتُها من صفِّ الإعدادات الذي يُسعَّر منه** — لا ثابتٌ هنا يفترق عنه أوّلَ تعديل */}
        <p className="t2-share-body t2-hr-rate">
          {rate !== null && km !== null
            ? `${formatMoney(rate, currency)} للساعة شاملةً ${km} كم — وما زاد بالتعرفة العاديّة`
            : "نقرأ سعرَ الساعة…"}
        </p>
        <div className="t2-hr-total">
          <span className="t2-hr-total-label">المجموع</span>
          {/* **ويختفي ما دام يُحسب** — رقمُ ساعاتٍ قديمٍ تحت عددٍ جديدٍ يكذب */}
          <span className="t2-hr-total-value">
            {loading || !estimate ? "نحسب…" : `${formatMoney(estimate.estimated_fare, estimate.currency)} ${forHours(draft.hours)}`}
          </span>
        </div>
        {max !== null ? <p className="t2-hr-cap">حتى {hoursLabel(max)} في الطلب الواحد.</p> : null}
      </div>

      <div className="t2-pick-head">
        <span className="t2-pick-title">دفعُ الساعات المحجوزة</span>
      </div>
      <div className="t2-cats t2-fo-payers" role="radiogroup" aria-label="دفع الساعات المحجوزة">
        {PREPAY.map((option) => {
          const on = option.value === draft.prepay;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "t2-cat on" : "t2-cat"}
              onClick={() => onChange({ ...draft, prepay: option.value })}
            >
              <span className="t2-cat-icon">
                <span className="t2-icon" aria-hidden="true">{option.icon}</span>
              </span>
              <span className="t2-cat-main">
                <span className="t2-cat-name">{option.label}</span>
                <span className="t2-cat-hint">{option.hint}</span>
              </span>
            </button>
          );
        })}
      </div>
      {/* **علّةُ غياب «+» المحطة** — سطرٌ قصيرٌ لا زرٌّ ميّتٌ بلا سبب */}
      <p className="t2-sheet-fine">
        بلا محطاتٍ تُضاف — تقول وجهاتِك للكبتن في الطريق. وما زاد على الساعات يُدفع في النهاية كأيِّ رحلة.
      </p>
    </>
  );
}

/** **كتلةُ الساعات في ورقة التتبّع** (R07–R09): «بالساعة · 3 ساعات · حتى 45 كم» من الصفّ، **وقبل البدء من أين يُدفع المحجوزُ
 *  بزرِّ تبديله** — من وجد رصيدَه لا يكفي يبدّل إلى النقد قبل أن يرفض البدءُ والكبتنُ عند الباب. **وبعد البدء لا تبديل** (الخلفيةُ
 *  ترفضه ٤٠٩) — والساعةُ في إحصاءات R09. ومن الصفّ لا من المفتاح. **والنداءُ عند صاحب الورقة** (`TrackingSheetT2`) كالإلغاء:
 *  الكتلةُ ترسم ولا تنادي. */
export function HourlyTrackT2({
  ride,
  prepaySwitch,
}: {
  ride: Ride;
  /** **تبديلُ من أين يُدفع المحجوز** — حالُه ونداؤه (`PATCH /rides/{id}/hourly-prepay`). */
  prepaySwitch: { busy: boolean; error: string | null; toggle: () => void };
}) {
  if (ride.ride_type !== "hourly" || ride.hourly_hours === null) return null;
  const before = ride.status === "requested" || ride.status === "searching" || ride.status === "accepted" || ride.status === "arrived";
  const prepay = ride.hourly_prepay_method;
  const other: HourlyPrepay = prepay === "cash" ? "wallet" : "cash";

  return (
    <div className="t2-fo-ride">
      <div className="t2-fo-ride-card">
        <div className="t2-fo-ride-name">
          <span className="t2-icon" aria-hidden="true">timer</span>
          <span>
            <b>بالساعة</b> · {hoursLabel(ride.hourly_hours)}
            {ride.hourly_included_km !== null ? ` · حتى ${ride.hourly_included_km} كم` : ""}
          </span>
        </div>
        {before && prepay ? (
          <div className="t2-fo-ride-payer">
            <span className="t2-icon" aria-hidden="true">{prepay === "cash" ? "payments" : "account_balance_wallet"}</span>
            <span>
              {prepay === "cash"
                ? "تدفع الساعاتِ المحجوزة نقداً للكبتن عند البدء"
                : "تُدفع الساعاتُ المحجوزة من محفظتك عند البدء"}
            </span>
          </div>
        ) : null}
      </div>
      {before && prepay ? (
        <button
          type="button"
          className="t2-button secondary t2-fo-link"
          disabled={prepaySwitch.busy}
          aria-busy={prepaySwitch.busy}
          onClick={prepaySwitch.toggle}
        >
          <span className="t2-icon" aria-hidden="true">swap_horiz</span>
          {other === "cash" ? "ادفع الساعاتِ نقداً بدل المحفظة" : "ادفعها من المحفظة بدل النقد"}
        </button>
      ) : null}
      <ErrorNote message={prepaySwitch.error} className="t2-error" />
    </div>
  );
}
