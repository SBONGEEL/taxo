/** نهايةُ الرحلة — TAXO 2.0 «R10» (Claude Design «Rider»)، **في المظهرين** — رُسم نهاريّاً، **والليليُّ برموز إسفلت الهوية نفسِها** (§٦٢/٣) — وجهُ شاشة التقييم.
 *
 * **وجهٌ ثانٍ لشاشة التقييم لا شاشةٌ ثانية**: النجومُ والملاحظةُ والإرسالُ والبقشيشُ كلُّها من `useRating` — **فلا يفترق
 * الوجهان في تقييمٍ ولا في بقشيش**. **وبطاقةُ الأجرة قراءةٌ لا حساب**: الأجرةُ النهائيةُ وطريقةُ الدفع والسطورُ كما تعرضها شاشةُ
 * الدفع من الخلفية (`getRide` · `getRidePayments`) — **ولا رقمَ يُشتقّ هنا** (§14).
 *
 * **والدفعُ يبقى خطوتَه قبلها** (`/rides/:id/pay`): اللوحةُ ترسم «R10» بعد دفعٍ تمّ، **وضمُّ الدفع إليها مسارُ مالٍ جديد** لا يُبنى
 * بلا قرار المالك (`TAXO2-DESIGN-CORRECTIONS.md` §٢٩).
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته**: سطورُ «الأجرة الأساسية · المسافة · الوقت» بمبالغها — **بُني تفصيلُها في الخلفية ويُعرض على
 * المالك قبل أن يُودَع** (§٦٢-د/١: ميزةُ مالٍ تُعرض قبل البناء)؛ واشتقاقُها هنا حسابُ مالٍ في الواجهة · **وإرسالُ البقشيش مع التقييم بزرٍّ
 * واحد**: قرارُ المالك ٢٠٢٦-٠٨-١٩ «الاختيارُ يُرى، والإرسالُ فعلٌ مستقل» — فبقي زرُّ «أرسل» للبقشيش وحدَه.
 *
 * **ووسومُ التقييم بُنيت** (§٦٢-ج/٢٥ — ليست مالاً): خمسةُ وسومٍ كما رُسمت، **تظهر من أربع نجومٍ فصاعداً** (كلُّها مديح، ومديحٌ تحت
 * نجمتين تناقض) وتُرسل مع التقييم نفسِه؛ مفاتيحُها من الخلفية (`RatingTag`) وتسمياتُها هنا.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getRide, getRidePayments } from "@/api/endpoints";
import type { RatingTag, Ride, RidePayments } from "@/api/types";
import { TIP_MIN_STARS, useRating } from "@/components/ride/useRating";
import { ErrorNote } from "@/components/ui/Feedback";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { currencyLabel, formatDistance, formatMoney, formatTime } from "@/lib/utils";
import { fareLineRows } from "@/lib/fareLines";

import "@/taxo2";
import "./t2.css";

/** وسومُ R10 بترتيب اللوحة — **التسميةُ هنا والمفتاحُ من الخلفية** (`RatingTag`). */
const RATING_TAGS: { tag: RatingTag; label: string }[] = [
  { tag: "safe_driving", label: "قيادة آمنة" },
  { tag: "clean_car", label: "سيارة نظيفة" },
  { tag: "friendly", label: "ودود" },
  { tag: "fast_arrival", label: "وصل بسرعة" },
  { tag: "knows_way", label: "يعرف الطريق" },
];

/** الوسومُ مديحٌ كلُّها — **تظهر من أربع نجوم** فلا يُعرض مديحٌ على تقييمٍ منخفض. */
const TAGS_MIN_STARS = 4;

/** **«وصلتِ» للراكبة و«وصلتَ» للراكب** — وبلا جنسٍ معلَنٍ بلا حركة، فلا يُخمَّن. */
function arrivedTitle(gender: string | null | undefined) {
  if (gender === "female") return "وصلتِ بالسلامة";
  if (gender === "male") return "وصلتَ بالسلامة";
  return "وصلت بالسلامة";
}

export function RatingT2Screen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const r = useRating(rideId);

  // **بطاقةُ الأجرة من الخلفية كما هي** — قراءتان لا تفشل الشاشةُ بفشلهما: البطاقةُ تغيب ويبقى التقييم
  const [ride, setRide] = useState<Ride | null>(null);
  const [payments, setPayments] = useState<RidePayments | null>(null);
  useEffect(() => {
    let cancelled = false;
    getRide(rideId)
      .then((row) => !cancelled && setRide(row))
      .catch(() => undefined);
    getRidePayments(rideId)
      .then((row) => !cancelled && setPayments(row))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [rideId]);

  const home = () => navigate("/", { replace: true });

  // **طريقةُ الدفع كما سُجّلت** — القنواتُ بأسمائها (و«كاش للكبتن» كما رُسمت)، **ولا يُعدّ الخصمُ قناةً يدفعها الراكب**
  const methods = [
    ...new Set(
      (payments?.payments ?? [])
        .filter((row) => row.method !== "promo" && row.method !== "share" && row.status !== "failed")
        .map((row) => row.method),
    ),
  ];
  const payLabel = methods
    .map((method) => (method === "cash" ? "كاش للكبتن" : PAYMENT_METHOD_LABEL[method]))
    .join(" + ");

  /** سطورُ البطاقة — **تفصيلُ الأجرة كما جمّدته الخلفية** (§٦٢-د/٦): أسطرٌ مجموعُها الأجرةُ نفسُها، **وتحتها منفصلةً** ما ليس
   *  منها: خصمُ الكوبون والمشاركة ورسمُ إلغاءٍ سابق. **ورحلةٌ أقدمُ من التجميد** تبقى بسطورها السابقة حرفاً — ما تعرضه شاشةُ
   *  الدفع نفسُها: المسافةُ الفعليةُ ورسومُ المحطات والانتظار والوقفات ورسمُ إلغاءٍ سابق. */
  const lines = ride ? fareLineRows(ride) : null;
  const rows: { label: string; value: string }[] = lines ?? [];
  const extras: { label: string; value: string }[] = [];
  if (lines) {
    for (const row of payments?.payments ?? []) {
      if ((row.method === "promo" || row.method === "share") && row.status === "confirmed")
        extras.push({
          label: row.method === "promo" ? "خصم الكوبون" : "خصم المشاركة",
          value: formatMoney(row.amount, payments?.currency),
        });
    }
  } else if (ride) {
    if (ride.actual_distance_km) rows.push({ label: "المسافة الفعلية", value: formatDistance(ride.actual_distance_km) });
    if (Number(ride.stops_charge) > 0)
      rows.push({ label: `رسم المحطات (${ride.stops.length})`, value: formatMoney(ride.stops_charge, ride.currency) });
    if (Number(ride.waiting_charge) > 0)
      rows.push({ label: "رسم الانتظار عند المحطات", value: formatMoney(ride.waiting_charge, ride.currency) });
    if (Number(ride.pause_charge) > 0)
      rows.push({ label: "رسم الوقفات أثناء الرحلة", value: formatMoney(ride.pause_charge, ride.currency) });
  }
  if (payments && Number(payments.cancellation_debt) > 0)
    (lines ? extras : rows).push({
      label: "رسمُ إلغاءٍ سابق",
      value: formatMoney(payments.cancellation_debt, payments.currency),
    });

  const first = ride?.driver?.name.split(" ")[0] ?? null;
  const tipShown = r.tip?.offered && !r.tip.given && r.stars >= TIP_MIN_STARS;

  return (
    <div className="t2 t2-r10">
      <div className="t2-r10-head">
        <span className="t2-r10-check" aria-hidden="true">
          <span className="t2-icon">check</span>
        </span>
        <div className="t2-r10-head-main">
          <h1 className="t2-r10-title">{arrivedTitle(user?.gender)}</h1>
          {ride ? (
            <div className="t2-r10-sub">
              {ride.dropoff_address ?? "وجهتك"}
              {ride.completed_at ? (
                <>
                  {" · "}
                  <span dir="ltr">{formatTime(ride.completed_at)}</span>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
        {r.done ? null : (
          <button type="button" className="t2-r10-skip" onClick={home}>
            تخطّي
          </button>
        )}
      </div>

      {payments?.final_fare ? (
        <div className="t2-r10-fare">
          <div className="t2-r10-fare-top">
            <div>
              <div className="t2-r10-fare-label">الأجرة النهائية</div>
              <div className="t2-r10-fare-amount">
                <span dir="ltr" className="t2-num">{formatMoney(payments.final_fare)}</span>
                <span className="t2-r10-fare-cur">{currencyLabel(payments.currency)}</span>
              </div>
            </div>
            {payLabel ? (
              <span className="t2-r10-pay">
                <span className="t2-icon" aria-hidden="true">payments</span>
                {payLabel}
              </span>
            ) : null}
          </div>
          {[rows, lines ? extras : []].map((group, index) =>
            group.length > 0 ? (
              <div key={index}>
                <div className="t2-r10-dash" aria-hidden="true" />
                <div className="t2-r10-rows">
                  {group.map((row) => (
                    <div key={row.label} className="t2-r10-row">
                      <span className="t2-r10-row-label">{row.label}</span>
                      <span className="t2-r10-row-value">{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null,
          )}
        </div>
      ) : null}

      <div className="t2-r10-ask">{first ? `كيف كانت رحلتك مع ${first}؟` : "كيف كانت رحلتك مع الكبتن؟"}</div>
      <div className="t2-r10-stars" role="radiogroup" aria-label="عدد النجوم">
        {[1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={r.stars === value}
            aria-label={`${value} من 5`}
            disabled={r.done}
            className={value <= r.stars ? "t2-r10-star on" : "t2-r10-star"}
            onClick={() => r.setStars(value)}
          >
            <span className="t2-icon" aria-hidden="true">star</span>
          </button>
        ))}
      </div>

      {r.stars >= TAGS_MIN_STARS ? (
        <div className="t2-r10-tags" role="group" aria-label="ما أعجبك في الرحلة">
          {RATING_TAGS.map(({ tag, label }) => {
            const on = r.tags.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                aria-pressed={on}
                disabled={r.done}
                className={on ? "t2-r10-tag on" : "t2-r10-tag"}
                onClick={() => r.toggleTag(tag)}
              >
                {label}
              </button>
            );
          })}
        </div>
      ) : null}

      {/* **والملاحظةُ باقيةٌ تحت الوسوم** — كانت في موضعها حين لم تكن وسوم، وتعمل اليوم */}
      <textarea
        className="t2-input t2-r10-comment"
        maxLength={500}
        value={r.comment}
        disabled={r.done}
        onChange={(event) => r.setComment(event.target.value)}
        placeholder="ملاحظة (اختيارية) — ما الذي أعجبك أو يمكن تحسينه؟"
        aria-label="ملاحظة (اختيارية)"
      />

      {r.tip?.given ? (
        <p className="t2-r10-thanks">
          شكرتَ الكبتن ببقشيش {formatMoney(r.tip.given.amount, r.tip.given.currency)}.
        </p>
      ) : tipShown && r.tip ? (
        <div className="t2-r10-tip">
          <div className="t2-r10-tip-head">
            <span className="t2-r10-tip-title">بقشيش للكبتن</span>
            <span className="t2-r10-tip-note">يصله كاملاً</span>
          </div>
          <div className="t2-r10-tip-row">
            <button
              type="button"
              className="t2-r10-tip-opt"
              disabled={r.tipping !== null}
              onClick={() => r.setTip({ ...r.tip!, offered: false })}
            >
              بدون
            </button>
            {r.tip.presets.map((amount) => (
              <button
                key={amount}
                type="button"
                dir="ltr"
                aria-pressed={r.chosenTip === amount}
                className={r.chosenTip === amount ? "t2-r10-tip-opt on" : "t2-r10-tip-opt"}
                disabled={r.tipping !== null}
                onClick={() => r.setChosenTip(r.chosenTip === amount ? null : amount)}
              >
                {formatMoney(amount)}
              </button>
            ))}
          </div>
          {/* **ومن أين يُخصم يُقال** — كما في الشاشة القائمة: المحفظةُ قناتُه الوحيدة */}
          <p className="t2-r10-tip-from">يُخصم من محفظتك ويصل الكبتن كاملاً — بلا أي خصم.</p>
          {r.chosenTip ? (
            <button
              type="button"
              className="t2-button action t2-r10-tip-send"
              disabled={r.tipping !== null}
              aria-busy={r.tipping !== null}
              onClick={() => void r.sendTip(r.chosenTip!)}
            >
              أرسل {formatMoney(r.chosenTip, r.tip.currency)}
            </button>
          ) : null}
        </div>
      ) : null}

      <ErrorNote message={r.error} className="t2-error" />
      {r.done ? <p className="t2-note t2-r10-done">شكراً — وصلنا تقييمك.</p> : null}

      <div className="t2-r10-spacer" />
      {r.done ? (
        <button type="button" className="t2-r10-cta" onClick={home}>
          العودة للرئيسية
        </button>
      ) : (
        <button
          type="button"
          className="t2-r10-cta"
          disabled={r.stars === 0 || r.busy}
          aria-busy={r.busy}
          onClick={() => void r.submit()}
        >
          إرسال التقييم
        </button>
      )}
    </div>
  );
}
