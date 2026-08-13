/** بطاقة الطلب الواردة — SPEC القسم 12/3، وشكلُها من `DESIGN.md` §2.10/5.3.
 *
 * **العدّاد يُحسب من لحظة الانتهاء لا بعدّ تنازلي مستقل**: عدّادٌ ينقص كل
 * ثانية ينجرف مع كل إعادة رسم، وبطاقةٌ مهلتُها عشرون ثانية لا تحتمل انجرافاً.
 * والمهلة نفسها من الخلفية (`expires_in_seconds`) لا رقمٌ مكتوبٌ هنا.
 *
 * والحلقة من §2.10 حرفاً: SVG بـ`viewBox="0 0 56 56"` مُدارةٌ `-90deg`،
 * دائرتان `r=26` بعرض 3.5، و`stroke-dasharray: 163`، والإزاحة
 * `(1 − المتبقي/الكل) × 163` بانتقالٍ `1s linear`.
 *
 * ولا تحمل هوية الراكب: نقطةُ الانطلاق والمسافة إليها والسعر والمهلة فقط.
 */

import { useEffect, useState } from "react";

import type { Offer } from "@/lib/ride";
import { bookedTime } from "@/lib/rideFormat";
import { arabicDigits } from "@/lib/utils";

const DASH = 163;

interface Props {
  offer: Offer;
  currencyLabel: string;
  categoryLabel: string;
  busy: boolean;
  onAccept: () => void;
  onDecline: () => void;
}

export function OfferSheet({
  offer,
  currencyLabel,
  categoryLabel,
  busy,
  onAccept,
  onDecline,
}: Props) {
  const [left, setLeft] = useState(() =>
    Math.max(0, Math.ceil((offer.expiresAt - Date.now()) / 1_000)),
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setLeft(Math.max(0, Math.ceil((offer.expiresAt - Date.now()) / 1_000)));
    }, 250);
    return () => window.clearInterval(timer);
  }, [offer.expiresAt]);

  const offset = Math.round((1 - left / offer.totalSeconds) * DASH);

  return (
    <div className="absolute inset-0 z-50 animate-fadein bg-dim">
      <div className="absolute inset-x-0 bottom-0 animate-slideup rounded-t-24 border-t border-line bg-surface px-18 pb-22 pt-18">
        <div className="mb-15 flex items-center gap-13">
          <div className="relative size-54 shrink-0">
            <svg
              width="54"
              height="54"
              viewBox="0 0 56 56"
              className="-rotate-90"
            >
              <circle
                cx="28"
                cy="28"
                r="26"
                fill="none"
                stroke="var(--brd)"
                strokeWidth="3.5"
              />
              <circle
                cx="28"
                cy="28"
                r="26"
                fill="none"
                stroke="var(--tx)"
                strokeWidth="3.5"
                strokeDasharray={DASH}
                strokeDashoffset={offset}
                style={{ transition: "stroke-dashoffset 1s linear" }}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-17 font-bold text-ink">
              {arabicDigits(String(left))}
            </span>
          </div>

          <div className="flex-1">
            {/* شارةُ الطلب النسائي (المرحلة 10-ج): وصفُ الطلب لا هويةُ صاحبته.
                ومكانُها فوق السعر لأنها تُقرأ **قبل** قرار القبول لا بعده —
                كبتنٌ يقبل ثم يكتشف أنه ليس أهلاً للطلب يُلغي، وإلغاءٌ كان
                يمكن تجنّبه ببضع بكسلات. ولا تظهر على طلبٍ بلا تفضيل */}
            {offer.ride.gender_preference !== "any" ? (
              <span className="mb-4 inline-block rounded-full border border-brand-brd bg-brand-soft px-9 py-3 text-10 font-bold text-brand">
                طلب نسائي
              </span>
            ) : null}
            {/* شارةُ الحجز (12-ط) — **بموعدها لا بكلمة «مجدولة» وحدها**: الكلمةُ
                تُخبر والموعدُ يُفيد. كبتنٌ يصل قبل الموعد فيجد الراكبَ غير جاهزٍ
                يُلغي ويتذمّر، ومن يقرأ «موعدها ٧:٠٠» يعرف قبل أن يقبل. ومكانُها
                فوق السعر لأنها تُقرأ **قبل** قرار القبول كشارة الطلب النسائي */}
            {/* شارةُ المشاركة (12-ي) — **وهي شرطُ صحّةِ ما يقع بعدها**: راكبٌ
                ثانٍ قد يُضاف إلى هذه الرحلة بلا استئذانٍ ثانٍ، وما يجعل ذلك
                مقبولاً أنه مكتوبٌ هنا **قبل** القبول. فقبولُها قبولٌ بالمقعد
                الثاني، لا مفاجأةٌ تصله وهو في الطريق.
                ولا تَعِد بمن لم يأتِ: «قد ينضم» لا «سينضم» — المطابقةُ احتمالٌ
                يقع أو لا يقع، ووعدٌ بشريكٍ لا يجيء يُقرأ خُلفاً */}
            {Number(offer.ride.share_discount_percent) > 0 ? (
              <span className="mb-4 me-4 inline-block rounded-full border border-line bg-surface-2 px-9 py-3 text-10 font-bold text-ink">
                مشتركة — قد ينضم راكب ثانٍ
              </span>
            ) : null}
            {offer.ride.scheduled_for ? (
              <span className="mb-4 me-4 inline-block rounded-full border border-line bg-surface-2 px-9 py-3 text-10 font-bold text-ink">
                محجوزة — {bookedTime(offer.ride.scheduled_for)}
              </span>
            ) : null}
            <div className="text-23 font-bold text-ink">
              {arabicDigits(offer.ride.estimated_fare)}{" "}
              <span className="text-12 font-medium text-muted">
                {currencyLabel}
              </span>
            </div>
            <div className="text-11.5 text-muted">{categoryLabel}</div>
          </div>

          <div className="text-end">
            <div className="text-15 font-bold text-ink">
              {arabicDigits(offer.distanceKm.toFixed(1))} كم
            </div>
            <div className="text-10.5 text-muted">حتى الراكب</div>
          </div>
        </div>

        <div className="mb-15 grid grid-cols-[12px_1fr] gap-x-10 gap-y-4">
          <span className="mx-auto mt-5 block size-8 rounded-full bg-ink" />
          <div className="text-13 text-ink">
            {offer.ride.pickup_address ?? "نقطة الانطلاق"}
          </div>
          <span className="mx-auto block h-12 w-2 bg-line" />
          <span />
          <span className="mx-auto mt-2 block size-8 rounded-2 bg-muted" />
          <div className="text-13 text-muted">
            {offer.ride.dropoff_address ?? "الوجهة"}
          </div>
        </div>

        <div className="flex gap-8">
          <button
            type="button"
            onClick={onAccept}
            disabled={busy}
            style={{ flex: 2.5 }}
            className="pressable rounded-15 bg-brand p-15 text-center text-15 font-bold text-brand-ink disabled:opacity-50"
          >
            قبول
          </button>
          <button
            type="button"
            onClick={onDecline}
            disabled={busy}
            className="pressable flex-1 rounded-15 border border-line p-15 text-center text-13 font-semibold text-muted disabled:opacity-50"
          >
            رفض
          </button>
        </div>
      </div>
    </div>
  );
}
