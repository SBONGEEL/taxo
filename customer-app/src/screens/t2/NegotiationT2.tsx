/** **«تفاوض»** — الراكبُ يقترح سعرَه، وكبتنٌ واحدٌ في كلِّ مرّةٍ يقبله أو يعرض سعراً آخر (SPEC §٩٢، `design/NEGOTIATE.md`).
 *
 * **لا لوحةَ له في التصميم** — فبلغة الورقة القائمة: كتلةٌ بمفتاحٍ كـ«حجزٌ مضمون» في ورقة الطلب، وبطاقةٌ في ورقة البحث.
 *
 * **ولا حسابَ مالٍ هنا** (§١٤): الحدُّ الأدنى وخطوتُه من التقدير، والعرضُ المقابلُ ومهلتُه من الخلفية، **والرقمُ المكتوبُ يُرسل كما
 * كُتب** — والخلفيةُ تقبله أو تردّه بنصّها (تحت الحدّ · ليس مضاعفاً للوحدة · فوق خمسة أضعاف التقدير).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { acceptCounter, changeOffer, getNegotiation, rejectCounter } from "@/api/endpoints";
import type { NegotiationState, Ride, RideEstimate } from "@/api/types";
import { ErrorNote } from "@/components/ui/Feedback";
import { formatMoney } from "@/lib/utils";
import { Icon, Switch } from "@/taxo2";
import { tr } from "@/lib/i18n";

/** **اسمُ الحدث الذي يمرّر به مقبسُ الراكب العرضَ المقابل** (`lib/ride.tsx`) — فتُسأل الحالُ فوراً لا عند الدورة التالية */
export const FARE_COUNTER_EVENT = "taxo:fare-counter";

/** **كتلةُ «تفاوض» في ورقة الطلب** — حيث نشر التقديرُ حدَّها وحدَه (السوقُ مشتعلٌ والفئةُ داخلة). `offer === null` مطفأة. */
export function NegotiateBlockT2({
  estimate,
  offer,
  onChange,
}: {
  estimate: RideEstimate;
  offer: string | null;
  onChange: (next: string | null) => void;
}) {
  const on = offer !== null;
  return (
    <div className="t2-schedule">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        className="t2-guarantee"
        // **يبدأ من السعر المقدَّر** — والراكبُ ينقصه أو يزيده بيده
        onClick={() => onChange(on ? null : estimate.estimated_fare)}
      >
        <span className="t2-share-main">
          <span className="t2-share-title">
            <Icon name="sell" />
            {tr("تفاوض على السعر")}
          </span>
          <span className="t2-share-body">
            {tr("يُعرض عرضُك على كبتنٍ واحدٍ في كلِّ مرّة — يقبله، أو يعرض سعراً آخر تقبله أو ترفضه.")}
          </span>
        </span>
        <Switch on={on} />
      </button>
      {on ? (
        <>
          <label className="t2-coupon-label" htmlFor="bargain">
            {tr("عرضك في التفاوض")}
          </label>
          <div className="t2-coupon-row">
            <input
              id="bargain"
              dir="ltr"
              inputMode="decimal"
              className="t2-input t2-coupon-input"
              value={offer}
              onChange={(event) => onChange(event.target.value.trim())}
            />
          </div>
          <p className="t2-sheet-fine">
            {tr("أقلُّ عرضٍ لهذه الرحلة")}{" "}{formatMoney(estimate.negotiation_minimum, estimate.currency)}
            {estimate.negotiation_min_amount
              ? <>{" — "}{tr("ولا يقلّ عن")}{" "}{formatMoney(estimate.negotiation_min_amount, estimate.currency)}</>
              : null}
            {estimate.negotiation_step
              ? <>{" · "}{tr("بمضاعفات")}{" "}{formatMoney(estimate.negotiation_step, estimate.currency)}</>
              : null}
          </p>
        </>
      ) : null}
    </div>
  );
}

/** **ثوانٍ باقيةٌ على العرض المقابل** — من مهلة الخلفية لحظةَ وصولها، **وقتٌ يُعدّ لا مالٌ يُحسب** */
function useCountdown(seconds: number | null): number | null {
  const [deadline, setDeadline] = useState<number | null>(null);
  const [, tick] = useState(0);
  useEffect(() => {
    setDeadline(seconds === null ? null : Date.now() + seconds * 1000);
  }, [seconds]);
  useEffect(() => {
    if (deadline === null) return;
    const timer = window.setInterval(() => tick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [deadline]);
  return deadline === null ? null : Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
}

/** **أثناء البحث**: عرضُك وتغييرُه، **والعرضُ المقابلُ بقبوله ورفضه** — والحالُ من `GET /rides/{id}/negotiation` لا من المقبس وحدَه
 *  (يُسأل عند الحدث، وكلَّ أربع ثوانٍ لمن فاته الحدث). */
export function NegotiationTrackT2({ ride, onChanged }: { ride: Ride; onChanged: () => void }) {
  const [state, setState] = useState<NegotiationState | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getNegotiation(ride.id)
      .then(setState)
      .catch(() => undefined);
  }, [ride.id]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 4000);
    window.addEventListener(FARE_COUNTER_EVENT, load);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(FARE_COUNTER_EVENT, load);
    };
  }, [load]);

  const counter = state?.counter ?? null;
  const left = useCountdown(counter ? counter.expires_in_seconds : null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setEditing(null);
      onChanged();
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر إرسال الجواب"));
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-schedule">
      {counter && left !== 0 ? (
        <div className="t2-callout" role="alert">
          <Icon name="sell" />
          <div className="t2-callout-main">
            <div className="t2-callout-title">
              {tr("{0} يعرض", { 0: counter.driver.name || tr("كبتن") })}{" "}{formatMoney(counter.amount, ride.currency)}
            </div>
            <p className="t2-callout-body">
              {[counter.driver.vehicle, counter.driver.color].filter(Boolean).join(" · ")}
              {counter.driver.rating ? ` · ★ ${counter.driver.rating}` : ""}
              {left !== null ? tr(" · يبقى {0} ث", { 0: left }) : ""}
            </p>
            <div className="t2-schedule-row">
              <button
                type="button"
                className="t2-button primary"
                disabled={busy}
                aria-busy={busy}
                onClick={() => void run(() => acceptCounter(ride.id))}
              >
                {tr("اقبل")}{" "}{formatMoney(counter.amount, ride.currency)}
              </button>
              <button
                type="button"
                className="t2-button secondary"
                disabled={busy}
                onClick={() => void run(() => rejectCounter(ride.id))}
              >
                {tr("ارفض — كبتنٌ آخر بعرضي")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {editing === null ? (
        <button type="button" className="t2-button secondary" disabled={busy} onClick={() => setEditing(ride.negotiation_offer ?? "")}>
          {tr("غيّر عرضك")}
        </button>
      ) : (
        <>
          <label className="t2-coupon-label" htmlFor="bargain-change">
            {tr("عرضك الجديد — يبدأ البحثُ من جديد")}
          </label>
          <div className="t2-coupon-row">
            <input
              id="bargain-change"
              dir="ltr"
              inputMode="decimal"
              autoFocus
              className="t2-input t2-coupon-input"
              value={editing}
              onChange={(event) => setEditing(event.target.value.trim())}
            />
            <button
              type="button"
              className="t2-button primary t2-coupon-apply"
              disabled={busy || editing === ""}
              onClick={() => void run(() => changeOffer(ride.id, editing))}
            >
              {tr("أرسل")}
            </button>
          </div>
        </>
      )}
      <ErrorNote message={error} className="t2-error" />
    </div>
  );
}
