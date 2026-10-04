/** **C05 — طلبٌ وارد والتطبيقُ مفتوح** (TAXO 2.0، الليليُّ المرسوم وحدَه — §٦١-د).
 *
 * **البطاقةُ كما رُسمت**: الحلقةُ بثوانيها، و«طلب جديد · الفئة» والأجرةُ بخطّ الأرقام، والمسافةُ إلى الراكب، والطريقُ بنقطتيه
 * ومسافةِ الرحلة وزمنها، و«رفض» و«قبول». **والعدّادُ والمهلةُ من بيتهما** (`useOfferCountdown` — من لحظة الانتهاء لا عدٌّ
 * ينجرف)، **والقبولُ والرفضُ هما نداءا الشاشة القائمة** (يمرّرهما `HomeT2`).
 *
 * **وما رسمته اللوحةُ ولا مصدرَ له لا يُرسم مكانَه شيء** (§٦١-د/د):
 * - **«كاش»**: طريقةُ الدفع يختارها الراكبُ بعد الرحلة (§6) — لا تُعرف لحظةَ العرض (`methodLabel={null}` في الشاشة القائمة).
 * - **«4 د» حتى الراكب**: لا مهلةَ قيادةٍ إليه في العرض — المسافةُ وحدَها (`distance_to_pickup_km`).
 * - **صفُّ الراكب** («ليلى · 4.8 · 36 رحلة»): **العرضُ لا يحمل هويةَ الراكب** عمداً (الشاشةُ القائمة) — لا اسمَ ولا تقييم.
 *
 * **وما في الشاشة القائمة ولم يُرسم — باقٍ بلغة اللوحة**: شاراتُ الطلب (نسائي · مشتركة · محجوزة · المحطات · مبلغٌ لكبتنٍ
 * آخر) **بنصّها وشرطها حرفاً** — تُقرأ قبل القبول — و«نغمة + اهتزاز» فوق البطاقة.
 */

import type { Offer } from "@/lib/ride";
import { useOfferCountdown } from "@/components/OfferSheet";
import { bookedTime, trimDistance } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** محيطُ الحلقة كما رُسمت: `r=25` ⇒ ٢π×٢٥ ≈ ١٥٧ (`stroke-dasharray="157"` في اللوحة). */
const DASH = 157;

export function OfferT2({
  offer,
  currencyLabel,
  categoryLabel,
  busy,
  over,
  onAccept,
  onDecline,
}: {
  offer: Offer;
  currencyLabel: string;
  categoryLabel: string;
  busy: boolean;
  /** **فوق رحلةٍ جارية** (مشاركةٌ يُعرض فيها راكبٌ ثانٍ) — تُعتَّم الورقةُ تحتها كما تُعتَّم في الشاشة القائمة. */
  over: boolean;
  onAccept: () => void;
  onDecline: () => void;
}) {
  const left = useOfferCountdown(offer);
  const offset = Math.round((1 - left / offer.totalSeconds) * DASH);
  const { ride } = offer;

  return (
    <>
      {over ? <div className="t2-of-dim" /> : null}
      <div className="t2-of" role="dialog" aria-label="طلب رحلة جديد">
        {/* **«نغمة + اهتزاز»** — حالُ الصوت لا زينة (الشاشةُ القائمة): من رآها ولم يسمع شيئاً عرف أنّ الصوتَ مطفأٌ في هاتفه */}
        <div className="t2-of-ring-note">
          <span className="t2-of-bars" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          نغمة + اهتزاز
        </div>

        <div className="t2-of-card">
          <div className="t2-of-top">
            <div className="t2-of-timer">
              <svg viewBox="0 0 56 56" width="58" height="58" aria-hidden="true">
                <circle className="t2-of-timer-track" cx="28" cy="28" r="25" fill="none" strokeWidth="4" />
                <circle
                  className="t2-of-timer-arc"
                  cx="28"
                  cy="28"
                  r="25"
                  fill="none"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray={DASH}
                  strokeDashoffset={offset}
                />
              </svg>
              <span className="t2-of-timer-num" dir="ltr">
                {digits(String(left))}
              </span>
            </div>
            <div className="t2-of-head">
              <div className="t2-of-kind">طلب جديد · {categoryLabel}</div>
              <div className="t2-of-fare">
                <span className="t2-of-fare-num" dir="ltr">
                  {digits(ride.estimated_fare)}
                </span>
                <span className="t2-of-fare-cur">{currencyLabel}</span>
              </div>
            </div>
          </div>

          {/* **شاراتُ الطلب — بنصّها وشرطها من `OfferSheet` حرفاً**، وتُقرأ قبل القبول لا بعده */}
          <OfferTags offer={offer} currencyLabel={currencyLabel} />

          <div className="t2-of-near">
            <Icon name="near_me" />
            {digits(offer.distanceKm.toFixed(1))} كم حتى الراكب
          </div>

          <div className="t2-of-route">
            <span className="t2-of-from" />
            <div className="t2-of-place">{ride.pickup_address ?? "نقطة الانطلاق"}</div>
            <span className="t2-of-link" />
            {/* **مسافةُ الرحلة وزمنُها كما قدّرتهما الخلفية** (`distance_km` · `duration_min`) — لا حسابَ هنا */}
            <div className="t2-of-trip">
              {trimDistance(ride.distance_km)} كم · {digits(String(Math.round(Number(ride.duration_min))))} د
            </div>
            <span className="t2-of-to" />
            <div className="t2-of-place">{ride.dropoff_address ?? "الوجهة"}</div>
          </div>

          <div className="t2-of-actions">
            <button type="button" className="t2-of-decline" onClick={onDecline} disabled={busy}>
              رفض
            </button>
            <button type="button" className="t2-of-accept" onClick={onAccept} disabled={busy}>
              <Icon name="check" />
              قبول
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

/** شاراتُ ما يُقرأ قبل القبول — **كلُّ شرطٍ ونصٍّ من البطاقة القائمة** (`components/OfferSheet.tsx`)، وعللُها مكتوبةٌ هناك. */
function OfferTags({ offer, currencyLabel }: { offer: Offer; currencyLabel: string }) {
  const { ride } = offer;
  const women = ride.gender_preference !== "any";
  const shared = Number(ride.share_discount_percent) > 0;
  const carried = Number(ride.carried_cancellation_fee ?? 0) > 0;
  if (!women && !shared && !ride.scheduled_for && ride.stops.length === 0 && !carried) return null;
  return (
    <div className="t2-of-tags">
      {women ? <span className="t2-of-tag women">طلب نسائي</span> : null}
      {shared ? <span className="t2-of-tag">مشتركة — قد ينضم راكب ثانٍ</span> : null}
      {ride.scheduled_for ? (
        <span className="t2-of-tag">محجوزة — {bookedTime(ride.scheduled_for)}</span>
      ) : null}
      {ride.stops.length > 0 ? (
        <span className="t2-of-tag">
          {ride.stops.length === 1
            ? "محطة وسيطة واحدة"
            : `${digits(String(ride.stops.length))} محطات وسيطة`}
        </span>
      ) : null}
      {carried ? (
        <span className="t2-of-tag warn">
          تحمل {digits(ride.carried_cancellation_fee ?? "0")} {currencyLabel} لكبتنٍ آخر
        </span>
      ) : null}
    </div>
  );
}
