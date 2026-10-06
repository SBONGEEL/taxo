/** تفاصيل رحلة سابقة: المسار، والأجرة، والدفعات، والتقييم (القسم 11.7).
 *
 * **المسافة الفعلية تُعرض حين تكون** ولا تُخترع حين تغيب: `null` تعني أن
 * تطبيق الكبتن صمت فبقي المقدَّر هو الحكم — وصفرٌ في مكانها يقول «سار صفر
 * كيلومتر» (SPEC القسم 4/5.7).
 *
 * **بلغة TAXO 2.0** (لوحتا `design/t2-new/rider/R18` · `R18b`): شريطُ الخريطة من الحافة والصفحةُ ورقةٌ فوقه (R06)، والأجرةُ
 * بطاقةُ R10، والمسارُ بطاقةُ «من · إلى»، والأرقامُ شبكةُ R09، والكبتنُ بطاقةُ R08، والدفعاتُ قائمةُ R11. **والنداءاتُ الثلاثةُ
 * والقواعدُ والوجهاتُ حرفاً** — وكلُّ سطرٍ كان يُعرض باقٍ.
 *
 * **والمسارُ الذي سارته على الشريط** (`R18c`، §٦٢-ج/١١): خطُّ الجمر فوق ظلّه كما ترسمه «TaxoMap» — **من نقاطٍ سجّلها بثُّ الكبتن**
 * (`GET /rides/{id}/route`) لا خطٍّ من عندنا، **ورابعُ نداءٍ لا يؤخّر الثلاثة**: يُسأل بعد أن تُرسم، للمكتملة وحدَها (لا نقاطَ
 * لغيرها)، **وفشلُه أو فراغُه يترك الدبوسين وحدهما** كما كانا.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRecordedRoute, getRide, getRidePayments, listRideRatings } from "@/api/endpoints";
import type { Coordinates, Rating, Ride, RidePayments, RideStatus } from "@/api/types";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { DriverAvatar } from "@/components/ride/DriverAvatar";
import { MapView, type MapHandle } from "@/components/map/MapView";
import { useGoBack } from "@/lib/back";
import { useMapboxToken } from "@/lib/config";
import { RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import {
  currencyLabel,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatMoney,
} from "@/lib/utils";
import { fareLineRows } from "@/lib/fareLines";
import { Icon } from "@/taxo2";
import { BannerT2, HeadT2 } from "@/screens/t2/MoneyT2";

/** **ما يغطّي الشريطَ من حوافّه** — الرجوعُ وشريطُ الحالة فوق، والورقةُ تعلو قاعَه بثلاثين: فيُضبط الإطارُ على ما يُرى منه. */
const STRIP_PADDING = { top: 76, bottom: 54, left: 48, right: 48 };

/** الحالاتُ التي ترسمها «رحلاتي» (R12) بنبرة الخطأ — **والنصُّ نصُّ السجلّ** (من ألغى). */
const UNSERVED: RideStatus[] = ["cancelled_by_rider", "cancelled_by_driver", "no_driver_found"];

/** **إطارُ الشريط يضمّ الخطَّ كلَّه** لا طرفيه وحدهما: طريقٌ انعطف بعيداً عن المستقيم بين الانطلاق والوصول يخرج من إطارٍ يضمّهما
 *  فقط. ركنان (جنوبيٌّ غربيّ · شماليٌّ شرقيّ) لـ`fitBounds` — **حسابُ هندسةٍ للعرض** لا يُسعَّر منه شيء. */
function frameOf(ride: Ride, route: number[][] | null): [Coordinates, Coordinates] {
  const lats = [ride.pickup.lat, ride.dropoff.lat, ...(route ?? []).map((point) => point[1])];
  const lngs = [ride.pickup.lng, ride.dropoff.lng, ...(route ?? []).map((point) => point[0])];
  return [
    { lat: Math.min(...lats), lng: Math.min(...lngs) },
    { lat: Math.max(...lats), lng: Math.max(...lngs) },
  ];
}

export function RideDetailsScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  // **من حيث جئت، والرئيسيةُ لمن دخل مباشرةً** (`lib/back.ts`) — كما كان رأسُ الشاشة
  const goBack = useGoBack("/");

  const [ride, setRide] = useState<Ride | null>(null);
  const [payments, setPayments] = useState<RidePayments | null>(null);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getRide(rideId),
      getRidePayments(rideId).catch(() => null),
      listRideRatings(rideId).catch(() => []),
    ])
      .then(([row, state, entries]) => {
        setRide(row);
        setPayments(state);
        setRatings(entries);
      })
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الرحلة"),
      )
      .finally(() => setLoading(false));
  }, [rideId]);

  // **المسارُ الذي سارته** (§٦٢-ج/١١) — للمكتملة وحدَها، و`null` حتى يصل أو حين لا يُرسم: **نقطتان على الأقلّ** خطٌّ، وما دونهما
  // لا خطّ. **ولا خطأَ يُعرض لفشله**: الشاشةُ كاملةٌ بلا خطّ كما كانت قبله
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

  const token = useMapboxToken();
  // **الإطارُ يضمّ النقطتين — والخطَّ حين يصل**: `center` وحدَه يضع الانطلاقَ في الوسط ويترك
  // الوصولَ خارج الشريط — ودبوسٌ واحدٌ في خريطةِ رحلةٍ لا يقول شيئاً
  const map = useRef<MapHandle>(null);
  useEffect(() => {
    if (!ride) return;
    const [southWest, northEast] = frameOf(ride, route);
    map.current?.fitBounds(southWest, northEast, STRIP_PADDING);
  }, [ride, route]);

  /** الرجوعُ فوق الخريطة — **ثابتٌ حين تُمرَّر الصفحة** (موضعُه في R06). */
  const floatingBack = (
    <div className="t2-m-ride-top">
      <button type="button" className="t2-mapbtn" aria-label="رجوع" onClick={goBack}>
        <Icon name="arrow_forward" />
      </button>
    </div>
  );

  if (loading) {
    // **هيكلٌ لا دوّامة** (§8): ثلاثةُ نداءاتٍ متتابعة تعني ثوانيَ من الفراغ، والهيكلُ يرسم **شكلَ ما سيصل** فتستقرّ العينُ على
    // مواضعه ولا تقفز حين يصل — والعنوانُ والرجوعُ قائمان كما كانا
    return (
      <div className="t2 t2-m-ride" aria-busy="true">
        {token ? floatingBack : null}
        {token ? <span className="t2-m-skel map" aria-hidden="true" /> : null}
        <div className={token ? "t2-m-ride-sheet" : "t2-m-ride-sheet flat"}>
          <div className="t2-m-ride-head">
            {token ? null : (
              <button type="button" className="t2-back" aria-label="رجوع" onClick={goBack}>
                <Icon name="arrow_forward" />
              </button>
            )}
            <h1 className="t2-m-ride-title">تفاصيل الرحلة</h1>
          </div>
          <span className="t2-m-skel line" aria-hidden="true" />
          <span className="t2-m-skel card" aria-hidden="true" />
          <span className="t2-m-skel block" aria-hidden="true" />
          <span className="t2-m-skel block" aria-hidden="true" />
        </div>
      </div>
    );
  }

  if (!ride) {
    return (
      <div className="t2 t2-m-page">
        <HeadT2 title="تفاصيل الرحلة" onBack={goBack} />
        <BannerT2 tone="danger" message={error ?? "الرحلة غير موجودة"} />
      </div>
    );
  }

  const owing = payments !== null && Number(payments.outstanding) > 0;
  const rated = ratings.some((entry) => entry.rater_type === "rider");
  const chip =
    ride.status === "completed" ? "t2-chip ok" : UNSERVED.includes(ride.status) ? "t2-chip danger" : "t2-chip";

  /** **سطورُ الأجرة — تُقرأ ولا تُحسب** (§5.10 و§5.10-ب/و): المجموعُ والضربُ في الخلفية (§14). **وصفرٌ لا يُرسم** — سطرٌ فارغٌ
   *  يعلّم قارئَه ألّا يقرأ. **والمقدَّرُ سطرٌ حين تكون النهائيةُ هي الرقمَ الكبير**، وإلا فهو الرقمُ الكبيرُ نفسُه. */
  // **وتفصيلُ الأجرة المجمَّد أوّلاً حين يوجد** (R10، §٦٢-د/٦): أسطرٌ مجموعُها الرقمُ الكبيرُ نفسُه، **وتحتها منفصلاً** ما ليس منه
  // (المقدَّرُ حين تكون النهائيةُ هي الرقم، ورسومُ الإلغاء). **ورحلةٌ أقدمُ من التجميد** تبقى بسطورها السابقة حرفاً
  const lines = fareLineRows(ride);
  const rows: { label: string; value: string }[] = lines ?? [];
  const extras: { label: string; value: string }[] = [];
  const after = lines ? extras : rows;
  if (ride.final_fare) after.push({ label: "السعر المقدّر", value: formatMoney(ride.estimated_fare, ride.currency) });
  if (!lines && Number(ride.stops_charge) > 0)
    rows.push({ label: `رسم المحطات (${ride.stops.length})`, value: formatMoney(ride.stops_charge, ride.currency) });
  if (!lines && Number(ride.waiting_charge) > 0)
    rows.push({ label: "رسم الانتظار عند المحطات", value: formatMoney(ride.waiting_charge, ride.currency) });
  if (!lines && Number(ride.pause_charge) > 0)
    rows.push({ label: "رسم الوقفات أثناء الرحلة", value: formatMoney(ride.pause_charge, ride.currency) });
  if (ride.cancellation_fee) after.push({ label: "رسوم الإلغاء", value: formatMoney(ride.cancellation_fee, ride.currency) });

  const stats = [
    { label: "المسافة المقدّرة", value: formatDistance(ride.distance_km) },
    ...(ride.actual_distance_km ? [{ label: "المسافة الفعلية", value: formatDistance(ride.actual_distance_km) }] : []),
    { label: "المدة المقدّرة", value: formatDuration(ride.duration_min) },
    { label: "فئة المركبة", value: VEHICLE_LABEL[ride.vehicle_category] },
  ];

  const vehicle = ride.driver?.vehicle ?? null;

  return (
    <div className="t2 t2-m-ride">
      {/* **شريطُ الخريطة من الحافة** (القرار 38): دبوسا الانطلاق والوصول، **والخطُّ المسارُ الذي سجّله بثُّ الكبتن** حين يكون
          (`routePoints` — متّصلاً بالجمر فوق ظلّه، R18c) — **ولا خطَّ مستقيماً من عندنا** (`tripLine={false}`): خطٌّ بين نقطتين يوهم
          بمسارٍ لم يقله أحد. **وشعارُ Mapbox فوق الورقة** لا تحتها (`controlsInset`) — شرطُ الرخصة مرئيّ */}
      {token ? (
        <>
          {floatingBack}
          <div className="t2-m-ride-map">
            <MapView
              ref={map}
              token={token}
              center={ride.pickup}
              pickup={ride.pickup}
              dropoff={ride.dropoff}
              tripLine={false}
              routePoints={route}
              interactive={false}
              controlsInset={30}
              className="h-full w-full"
            />
          </div>
        </>
      ) : null}

      <div className={token ? "t2-m-ride-sheet" : "t2-m-ride-sheet flat"}>
        <div className="t2-m-ride-head">
          {token ? null : (
            <button type="button" className="t2-back" aria-label="رجوع" onClick={goBack}>
              <Icon name="arrow_forward" />
            </button>
          )}
          <h1 className="t2-m-ride-title">تفاصيل الرحلة</h1>
          <span className={chip}>{RIDE_STATUS_LABEL[ride.status]}</span>
        </div>
        <div className="t2-m-ride-when">{formatDateTime(ride.created_at)}</div>

        {/* **الأجرةُ أوّلاً وكبيرة** (بطاقةُ R10): الرقمُ هو ما يُفتح له هذا السجلُّ أصلاً، فيُقرأ قبل أن تُقرأ الحقول */}
        <div className="t2-m-card t2-m-fare">
          <div className="t2-m-label">{ride.final_fare ? "الأجرة النهائية" : "السعر المقدّر"}</div>
          <div className="t2-m-amount">
            <span dir="ltr" className="t2-m-num lg">
              {formatMoney(ride.final_fare ?? ride.estimated_fare)}
            </span>
            <span className="t2-m-cur">{currencyLabel(ride.currency)}</span>
          </div>
          {[rows, extras].map((group, index) =>
            group.length > 0 ? (
              <div key={index}>
                <div className="t2-m-dash tight" aria-hidden="true" />
                <div className="t2-m-rows">
                  {group.map((row) => (
                    <div key={row.label} className="t2-m-row">
                      <span className="t2-m-row-label">{row.label}</span>
                      <span className="t2-m-row-value">{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null,
          )}
        </div>

        {/* «من · إلى» — بطاقةُ المسار في R06، **والعنوانُ كاملاً يلتفّ ولا يُقطع** */}
        <div className="t2-m-route t2-m-gap">
          <span className="t2-route-from" aria-hidden="true" />
          <div>
            <div className="t2-route-label">من</div>
            <div className="t2-m-route-value">{ride.pickup_address ?? "نقطة على الخريطة"}</div>
          </div>
          <span className="t2-route-join" aria-hidden="true" />
          <span />
          <span className="t2-route-to" aria-hidden="true" />
          <div>
            <div className="t2-route-label">إلى</div>
            <div className="t2-m-route-value">{ride.dropoff_address ?? "نقطة على الخريطة"}</div>
          </div>
        </div>

        <div className={stats.length === 4 ? "t2-m-stats four t2-m-gap" : "t2-m-stats t2-m-gap"}>
          {stats.map((stat) => (
            <div key={stat.label} className="t2-m-stat">
              <div className="t2-m-stat-value">{stat.value}</div>
              <div className="t2-m-stat-label">{stat.label}</div>
            </div>
          ))}
        </div>

        {ride.cancelled_reason ? (
          <div className="t2-m-card t2-m-gap">
            <div className="t2-m-label">سبب الإلغاء</div>
            <div className="t2-m-reason">{ride.cancelled_reason}</div>
          </div>
        ) : null}

        {/* **بطاقةُ الكبتن** (R08) لا صفوفَ «حقلٌ: قيمة»: الكبتنُ **شخصٌ يُتعرَّف عليه** — حرفٌ أولُ واسمٌ ونجومٌ ومركبة.
            **واللوحةُ لاتينيةٌ بلا تحويل خانات**: تُطابَق حرفاً بحرف */}
        {ride.driver ? (
          <div className="t2-m-driver t2-m-gap">
            <DriverAvatar rideId={ride.id} name={ride.driver.name} />
            <div className="t2-m-driver-main">
              <div className="t2-m-driver-name">{ride.driver.name}</div>
              {Number(ride.driver.rating_avg) > 0 ? (
                <div className="t2-m-driver-rating">
                  <Icon name="star" fill />
                  {/* **خاناتٌ لاتينيةٌ لأنها عُرفُ هذا التطبيق** — وكسرٌ واحدٌ كما كان */}
                  <b>{Number(ride.driver.rating_avg).toFixed(1)}</b>
                </div>
              ) : null}
              {vehicle ? (
                <div className="t2-m-driver-car">
                  {vehicle.make} {vehicle.model} · {vehicle.color}
                </div>
              ) : null}
            </div>
            {vehicle ? (
              <div dir="ltr" className="t2-trk-plate">
                <span className="t2-trk-plate-cc">{ride.country_code}</span>
                <span className="t2-trk-plate-no">{vehicle.plate_number}</span>
              </div>
            ) : null}
          </div>
        ) : null}

        {payments && payments.payments.length > 0 ? <PaymentsList payments={payments.payments} /> : null}

        <BannerT2 tone="danger" message={error} />

        <div className="t2-m-actions">
          {owing ? (
            // **زرُّ الجمر وسعرُه آخرُ السطر** — «اطلب» في R06: ما يُدفع الآن يُقرأ قبل الضغط
            <button
              type="button"
              className="t2-button action t2-m-cta t2-m-cta-split"
              onClick={() => navigate(`/rides/${ride.id}/pay`)}
            >
              <span>إكمال الدفع</span>
              <span className="t2-m-cta-price">{formatMoney(payments!.outstanding, payments!.currency)}</span>
            </button>
          ) : ride.status === "completed" && !rated ? (
            <button type="button" className="t2-button primary t2-m-cta" onClick={() => navigate(`/rides/${ride.id}/rate`)}>
              قيّم هذه الرحلة
            </button>
          ) : null}

          {/* «أعد الطلب» — **طلبٌ جديد بنفس النقطتين لا نسخُ رحلةٍ مضت** (`FUTURE-FEATURES` بند 3): السعرُ يُعاد حسابه،
              والمحطاتُ لا تُنسخ، والتفضيلُ يُقرأ من الملف كأي طلبٍ جديد. ولا يظهر إلا على رحلةٍ انتهت */}
          {ride.status === "completed" ? (
            <button
              type="button"
              className="t2-button secondary t2-m-wide"
              onClick={() =>
                navigate("/", {
                  state: {
                    again: {
                      pickup: ride.pickup,
                      pickupAddress: ride.pickup_address,
                      dropoff: ride.dropoff,
                      dropoffAddress: ride.dropoff_address,
                    },
                  },
                })
              }
            >
              أعد الطلب
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
