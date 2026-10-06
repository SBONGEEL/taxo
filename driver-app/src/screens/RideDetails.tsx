/** تفاصيل الرحلة — TAXO 2.0 «C17» (`design/t2-new/captain/C17-*.dc.html`) — SPEC القسم 12/6، **في المظهرين والنسائيّ**.
 *
 * ثلاثةُ أسئلةٍ يفتح الكبتن هذه الشاشة ليجيب عنها: **كم قبضتُ**، و**بأي قناة**، و**هل وصلني المال فعلاً**. والثالثُ وحده يفتح باب
 * النزاع — **وهو بابُ الاعتراض الذي يصله السجلُّ** (C16، §٦١-ب/٣): «لم تصلني» بجانب «وصلتني» **في قاع الشاشة كقرار C08**.
 *
 * **والنزاع على كليك وحدها** (`payments.dispute_by_driver`): التحويل يقع خارج التطبيق ولا API يشهد عليه، فبين «حوّلتُ» و«لم
 * يصلني» فراغٌ يملؤه إنسان. الكاش يقع يداً بيد فلا فراغ فيه، والمحفظة يشهد عليها الدفتر. والزرُّ هنا مشروطٌ بدفعة كليك تنتظر التأكيد.
 *
 * **والمسارُ الذي سارها فوق الخريطة** (`C17d`، §٦٢-ج/١١): `ride_route_points` يُسجَّل لإعادة حساب `final_fare` ولدليل النزاع،
 * **وصار له بابٌ لطرفَي الرحلة** (`GET /rides/{id}/route`) — فيُرسم خطَّ الجمر فوق ظلّه بلغة «TaxoMap» (`MapView` بـ`t2`)، **والإطارُ
 * يضمّه كلَّه** (`fitRoute`). **ولا خطَّ من عندنا**: بلا نقاطٍ — أو قبل أن تنتهي — يبقى الدبوسان وحدهما كما كانا.
 *
 * **ولا تفصيلَ تعرفةٍ سطراً سطراً**: `GET /config` لا ينشر أسعار `pricing_settings` — والواجهة لا تضرب مسافةً في سعرٍ لتُخرج رقماً
 * (القسم 14: الحساب في الخلفية حصراً). فما يظهر ما قالته الخلفية: مقدَّرٌ، ومسافة، ومدّة، ونهائيّ، ونسبةُ عمولةٍ مجمَّدة على الرحلة.
 *
 * **والمنطقُ هو هو حرفاً**: الطلباتُ الثلاثة، والتأكيدُ (`POST /payments/{id}/confirm`) ثمّ إعادةُ القراءة، وأسبقيّةُ ما يُعرض
 * (فصلٌ ← نزاعٌ مفتوح ← كاشٌ ينتظر ← كليك ينتظر). **وما تغيّر طبقةُ العرض**: الخريطةُ من الحافّة، والأجرةُ برقم C09، وكتلةُ المسار
 * من C05، والجدولُ من C08، **والقرارُ مثبَّتٌ في القاع** فلا يُطلب تمريرٌ ليُجاب سؤالُ المال.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  confirmPayment,
  getRecordedRoute,
  getRide,
  getRidePayments,
  listRideRatings,
} from "@/api/endpoints";
import type {
  Payment,
  PaymentStatus,
  Rating,
  Ride,
  RidePayments,
} from "@/api/types";
import { MapView } from "@/components/map/MapView";
import { Spinner } from "@/components/ui/Feedback";
import { useMapboxToken } from "@/lib/config";
import {
  CURRENCY_LABEL,
  METHOD_LABEL,
  RIDE_STATUS_LABEL,
  formatWhen,
  trimDistance,
} from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { chipTone } from "@/screens/Rides";
import { Icon } from "@/taxo2";

import { startOfToday, whenParts } from "./t2/when";

import "./t2/ride.css";
import "./t2/rides.css";

/** **حشوُ إطار الشريط** (`.t2-rdt-map`: ١٥٠ وحافّةُ الشاشة العليا) — فوقُه شريطُ الحالة، وجانباه زرّا الرجوع والموقع، وقاعُه شعارُ
 *  Mapbox ونسبتُه (شرطُ الرخصة). **وكان ٨٠ من كلِّ جهة** — حشوُ خريطةٍ تملأ الشاشة — فيبقى للخطّ ٤٠ بكسلاً ويُرسم نقطةً (قِيس). */
const STRIP_PADDING = { top: 62, bottom: 34, left: 72, right: 72 };

/** نصُّ فصل الإدارة — `paid` تصف الواقعة لا الحالة الناتجة. */
const RESOLUTION_LABEL: Record<"paid" | "unpaid", string> = {
  paid: "فصلت الإدارة: المبلغ وصلك",
  unpaid: "فصلت الإدارة: المبلغ لم يصلك",
};

export function RideDetailsScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const goBack = useGoBack();
  const token = useMapboxToken();

  const [ride, setRide] = useState<Ride | null>(null);
  const [payments, setPayments] = useState<RidePayments | null>(null);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    const [one, paid, rated] = await Promise.all([
      getRide(rideId),
      // رحلةٌ ألغيت قبل أي دفعة لا دفعاتِ لها، وليس ذلك عطلاً
      getRidePayments(rideId).catch(() => null),
      listRideRatings(rideId).catch(() => []),
    ]);
    setRide(one);
    setPayments(paid);
    setRatings(rated);
  }, [rideId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الرحلة",
      ),
    );
  }, [load]);

  // **المسارُ الذي سارته** (§٦٢-ج/١١) — للمكتملة وحدَها، **ولا يؤخّر الثلاثةَ ولا يُسقطها**: يُسأل بعد أن تُرسم، وفشلُه أو
  // فراغُه يترك الدبوسين كما كانا. **ونقطتان على الأقلّ** خطٌّ
  const [route, setRoute] = useState<number[][] | null>(null);
  const completed = ride?.status === "completed";
  useEffect(() => {
    if (!completed) return;
    let live = true;
    getRecordedRoute(rideId)
      .then((recorded) => {
        if (live) setRoute(recorded.points.length >= 2 ? recorded.points : null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [rideId, completed]);

  async function confirm(paymentId: string) {
    setConfirming(true);
    setError(null);
    try {
      await confirmPayment(paymentId);
      await load();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تأكيد الدفعة",
      );
    } finally {
      setConfirming(false);
    }
  }

  if (!ride) {
    return (
      <div className="t2 t2-rdt">
        <div className="t2-rdt-wait">
          <div className="t2-head">
            <button
              type="button"
              className="t2-back"
              aria-label="رجوع"
              onClick={() => goBack()}
            >
              <Icon name="arrow_forward" />
            </button>
          </div>
          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : (
            <div className="t2-rdt-wait-body">
              <Spinner />
            </div>
          )}
        </div>
      </div>
    );
  }

  const currency = CURRENCY_LABEL[ride.currency];
  const rows = payments?.payments ?? [];
  // النزاع من دفعةٍ واحدة: كليك تنتظر تأكيده
  const disputable: Payment | undefined = rows.find(
    (payment) => payment.method === "cliq" && payment.status === "pending",
  );
  // **والكاشُ يُؤكَّد من هنا أيضاً** — وجدته المرحلةُ ١٣ على الجهاز: الشاشةُ تكتب «بانتظار تأكيدك» على دفعةٍ نقدية ولا تبني لها
  // زرّاً، والبابُ الوحيد بطاقةُ التحصيل في الرئيسية — وهي تختفي بإعادة فتح التطبيق أو بأيّ تنقّل، لأن الرحلةَ المكتملة ليست «جارية»
  // فلا يستعيدها `getActiveRide`. فمن قبض مالَه ثم أغلق تطبيقَه لا يجد أبداً ما يؤكّد به، والدفعةُ تبقى `pending` فتُقرأ الرحلةُ
  // **غيرَ مدفوعة**. **ولا زرَّ نزاعٍ معه**: `dispute_by_driver` يرفض غيرَ كليك، ومن لم يُسلَّم مالاً لا يضغط «استلمت»
  const collectable: Payment | undefined = rows.find(
    (payment) => payment.method === "cash" && payment.status === "pending",
  );
  const disputed = rows.find((payment) => payment.status === "disputed");
  const resolved = rows.find(
    (payment) => payment.disputed_at !== null && payment.resolution !== null,
  );
  // تقييمُ الكبتن للراكب — لا تقييمُ الراكب له
  const mine = ratings.find((rating) => rating.rater_type === "driver");
  const commission = Number(ride.commission_percent_at_ride);
  const when = whenParts(ride.created_at, startOfToday());
  // **القرارُ في القاع حين يكون مالٌ بانتظار قوله** — وفصلُ الإدارة ونزاعُها المفتوح يسبقانه كما سبقاه
  const deciding = !resolved && !disputed && (collectable ?? disputable);

  return (
    <div className="t2 t2-rdt">
      <div className="t2-rdt-scroll scr">
        <div className="t2-rdt-map">
          <MapView
            token={token}
            // **لا سيارةَ للكبتن على خريطة رحلةٍ مضت** — `center` يرسم علامتَه عنده، فكانت سيارتُه عند نقطة الانطلاق (رآه «p3a»)؛
            // والإطارُ من `fit` على المسار والدبوسين
            center={null}
            pickup={ride.pickup}
            dropoff={ride.dropoff}
            routePoints={route}
            fit
            fitRoute
            fitPadding={STRIP_PADDING}
            t2
          />
          <button
            type="button"
            className="t2-back t2-rdt-back"
            aria-label="رجوع"
            onClick={() => goBack()}
          >
            <Icon name="arrow_forward" />
          </button>
        </div>

        <div className="t2-rdt-body">
          <div className="t2-rdt-top">
            <span className="t2-rdt-when">
              {digits(when.day)} · <span dir="ltr">{digits(when.time)}</span>
            </span>
            <span className={`t2-chip ${chipTone(ride.status)}`}>
              {RIDE_STATUS_LABEL[ride.status]}
            </span>
          </div>
          <div className="t2-rdt-fare">
            <span className="t2-rdt-fare-num" dir="ltr">
              {digits(ride.final_fare ?? ride.estimated_fare)}
            </span>
            <span className="t2-rdt-fare-cur">{currency}</span>
          </div>

          <div className="t2-rdt-route">
            <span className="t2-rdt-dot" aria-hidden="true" />
            <span className="t2-rdt-place">
              {ride.pickup_address ?? "نقطة الانطلاق"}
            </span>
            <span className="t2-rdt-link" aria-hidden="true" />
            <span />
            <span className="t2-rdt-dot to" aria-hidden="true" />
            <span className="t2-rdt-place">
              {ride.dropoff_address ?? "الوجهة"}
            </span>
          </div>

          <h2 className="t2-section">تفصيل السعر</h2>
          <div className="t2-rdt-grid">
            <Row label="السعر المقدّر" value={digits(ride.estimated_fare)} />
            {/* الفعليةُ تُسمّى فعلية: جدولٌ يخلط المقدَّر بالمحقَّق بلا اسمٍ يجعل الكبتن يحسب على رقمٍ لا يعرف مصدره */}
            <Row
              label={
                ride.actual_distance_km ? "المسافة الفعلية" : "المسافة المقدّرة"
              }
              value={`${trimDistance(ride.actual_distance_km ?? ride.distance_km)} كم`}
            />
            <Row
              label="المدّة المقدّرة"
              value={`${trimDistance(ride.duration_min)} دقيقة`}
            />
            {/* **ما وقف لأجله يُسمّى في تفصيله** (§5.10 و§5.10-ب/و): الكبتنُ يقرأ هنا لماذا صار النهائيُّ غيرَ المقدَّر، فلا يظنّ
                نقصاً ولا يسأل الدعم. **قيمٌ تُقرأ لا تُحسب** (§14)، **وصفرٌ لا يُرسم** */}
            {Number(ride.stops_charge) > 0 ? (
              <Row
                label={`رسم المحطات (${digits(String(ride.stops.length))})`}
                value={digits(ride.stops_charge)}
              />
            ) : null}
            {Number(ride.waiting_charge) > 0 ? (
              <Row
                label="رسم الانتظار عند المحطات"
                value={digits(ride.waiting_charge)}
              />
            ) : null}
            {Number(ride.pause_charge) > 0 ? (
              <Row
                label="رسم الوقفات أثناء الرحلة"
                value={digits(ride.pause_charge)}
              />
            ) : null}
            {/* **النسبةُ المجمَّدةُ على هذه الرحلة** (`commission_percent_at_ride`) — سجلٌّ لما حوسب به، لا وعدٌ تسويقيّ */}
            <Row
              label="العمولة"
              value={
                commission === 0
                  ? "0٪ حالياً"
                  : `${digits(String(commission))}٪`
              }
              tone="ok"
            />
            <Row
              label="السعر النهائي"
              value={digits(ride.final_fare ?? ride.estimated_fare)}
              strong
            />
          </div>

          {rows.length > 0 || mine ? (
            <div className="t2-rdt-grid t2-rdt-pay">
              {rows.map((payment) => (
                <Row
                  key={payment.id}
                  label={`${METHOD_LABEL[payment.method]} · ${paymentStatusLabel(payment)}`}
                  value={digits(payment.amount)}
                  tone={payment.status === "confirmed" ? undefined : "warn"}
                />
              ))}
              {mine ? (
                <>
                  <span className="t2-rdt-k">تقييمك للراكب</span>
                  <span className="t2-rdt-v">
                    <span className="t2-rdt-star">
                      <Icon name="star" fill />
                      <span dir="ltr">{digits(String(mine.stars))}</span>
                    </span>
                  </span>
                </>
              ) : null}
            </div>
          ) : null}

          {/* المهلةُ تُقال هنا أيضاً: من أغلق البطاقة لا يراها إلا هنا — **تحت الدفعة التي تخصّها** */}
          {!resolved &&
          !disputed &&
          !collectable &&
          disputable?.cliq_confirmation_expires_at ? (
            <p className="t2-rdt-deadline">
              <Icon name="schedule" />
              <span>
                إن لم تؤكّد أو ترفض حتى{" "}
                {formatWhen(disputable.cliq_confirmation_expires_at)} صارت
                الدفعة نزاعاً تفصل فيه الإدارة.
              </span>
            </p>
          ) : null}

          {resolved ? (
            <p className="t2-rdt-notice">
              <Icon name="balance" />
              <span>
                {resolved.resolution
                  ? RESOLUTION_LABEL[resolved.resolution]
                  : "فُصل النزاع"}
                {resolved.resolution_note
                  ? ` — ${resolved.resolution_note}`
                  : ""}
              </span>
            </p>
          ) : disputed ? (
            <p className="t2-rdt-notice warn">
              <Icon name="balance" />
              <span>نزاعك مفتوح وبانتظار فصل الإدارة. سيصلك إشعار بالنتيجة.</span>
            </p>
          ) : null}

          {/* خطأٌ بلا قرارٍ في القاع (قراءةٌ لاحقة) يُقال هنا */}
          {error && !deciding ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}
        </div>
      </div>

      {deciding ? (
        <div className="t2-rdt-foot">
          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}
          {collectable ? (
            <button
              type="button"
              className="t2-rdt-cash"
              disabled={confirming}
              onClick={() => void confirm(collectable.id)}
            >
              {confirming ? "…" : "استلمت المبلغ كاش"}
            </button>
          ) : disputable ? (
            // **الفعلُ الإيجابي حاضرٌ مع الاعتراض**: من وصلته الحوالة يجد بابَه هنا لا في بطاقةٍ عابرة قد يكون أغلقها. وشاشةٌ
            // تعرض «افتح نزاعاً» وحده تُملي على الكبتن الجوابَ الذي لم يقله — **وترتيبُهما ترتيبُ «رفض · قبول» في C05**
            <div className="t2-rdt-acts">
              <button
                type="button"
                className="t2-rdt-no"
                disabled={confirming}
                onClick={() => navigate(`/rides/${ride.id}/dispute`)}
              >
                لم تصلني
              </button>
              <button
                type="button"
                className="t2-rdt-yes"
                disabled={confirming}
                onClick={() => void confirm(disputable.id)}
              >
                {confirming ? (
                  "…"
                ) : (
                  <>
                    <Icon name="check" />
                    وصلتني
                  </>
                )}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** والاسمُ يختلف بالقناة لا بالحال: `pending` على كليك والكاش انتظارُ قولِ
 * الكبتن، وعلى البطاقة انتظارُ جواب المزود. */
function paymentStatusLabel(payment: Payment): string {
  if (payment.status === "pending") {
    return payment.method === "cash" || payment.method === "cliq"
      ? "بانتظار تأكيدك"
      : "بانتظار الدفع";
  }
  return PAYMENT_STATUS_LABEL[payment.status];
}

const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: "بانتظار الدفع",
  confirmed: "مؤكدة",
  failed: "فاشلة",
  refunded: "مستردّة",
  disputed: "في نزاع",
};

/** صفُّ الجدول (C08): الاسمُ خافتٌ في البداية والقيمةُ في الطرف — **والمبالغُ أرقامٌ بلا عملة** كما رُسمت، فالعملةُ مع الأجرة فوق. */
function Row({
  label,
  value,
  tone,
  strong = false,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn";
  strong?: boolean;
}) {
  return (
    <>
      <span className={strong ? "t2-rdt-k strong" : "t2-rdt-k"}>{label}</span>
      <span
        className={["t2-rdt-v", strong ? "strong" : null, tone ?? null]
          .filter(Boolean)
          .join(" ")}
      >
        {value}
      </span>
    </>
  );
}
