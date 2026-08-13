/** تفاصيل رحلة سابقة: المسار، والأجرة، والدفعات، والتقييم (القسم 11.7).
 *
 * **المسافة الفعلية تُعرض حين تكون** ولا تُخترع حين تغيب: `null` تعني أن
 * تطبيق الكبتن صمت فبقي المقدَّر هو الحكم — وصفرٌ في مكانها يقول «سار صفر
 * كيلومتر» (SPEC القسم 4/5.7).
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, getRidePayments, listRideRatings } from "@/api/endpoints";
import type { Rating, Ride, RidePayments } from "@/api/types";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { Button } from "@/components/ui/Button";
import { Badge, ErrorNote } from "@/components/ui/Feedback";
import { MapView, type MapHandle } from "@/components/map/MapView";
import { useMapboxToken } from "@/lib/config";
import { Skeleton } from "@/components/ui/Motion";
import { Screen } from "@/components/ui/Screen";
import { RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import {
  formatDateTime,
  formatDistance,
  formatDuration,
  formatMoney,
} from "@/lib/utils";

export function RideDetailsScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();

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

  const token = useMapboxToken();
  // **الإطارُ يضمّ النقطتين**: `center` وحدَه يضع الانطلاقَ في الوسط ويترك
  // الوصولَ خارج الشريط — ودبوسٌ واحدٌ في خريطةِ رحلةٍ لا يقول شيئاً
  const map = useRef<MapHandle>(null);
  useEffect(() => {
    if (ride) map.current?.fitBounds(ride.pickup, ride.dropoff);
  }, [ride]);

  if (loading) {
    // **هيكلٌ لا دوّامة** (§8): ثلاثةُ نداءاتٍ متتابعة تعني ثوانيَ من السواد،
    // والهيكلُ يرسم **شكلَ ما سيصل** فتستقرّ العينُ على مواضعه ولا تقفز حين يصل
    return (
      <Screen title="تفاصيل الرحلة" nav>
        <div className="space-y-20">
          <Skeleton className="-mx-16 -mt-16 h-170 rounded-none" />
          <div className="flex items-start justify-between gap-12">
            <div className="space-y-8">
              <Skeleton className="h-12 w-82" />
              <Skeleton className="h-26 w-150" />
            </div>
            <Skeleton className="h-24 w-82 rounded-full" />
          </div>
          <Skeleton className="h-150" />
          <Skeleton className="h-82" />
        </div>
      </Screen>
    );
  }

  if (!ride) {
    return (
      <Screen title="تفاصيل الرحلة" nav>
        <ErrorNote message={error ?? "الرحلة غير موجودة"} />
      </Screen>
    );
  }

  const owing = payments !== null && Number(payments.outstanding) > 0;
  const rated = ratings.some((entry) => entry.rater_type === "rider");

  return (
    <Screen title="تفاصيل الرحلة" nav>
      <div className="space-y-20">
        {/* **شريطُ الخريطة 170px** (القرار 38): دبوسا الانطلاق والوصول
            **بلا خطِّ مسار** — المسارُ الفعليُّ مسجَّلٌ في `ride_route_points`
            للخلفية ولا منفذَ يقرؤه، وخطٌّ مستقيمٌ من عندنا يوهم بمسارٍ لم يقله
            أحد. ولذلك **لا تُكتب عليه «المسار الفعلي المسجَّل»** كما في
            النموذج: عنوانٌ يَعِد بما لا يُرسم */}
        {token ? (
          <div className="-mx-16 -mt-16 h-170 overflow-hidden">
            <MapView
              ref={map}
              token={token}
              center={ride.pickup}
              pickup={ride.pickup}
              dropoff={ride.dropoff}
              tripLine={false}
              interactive={false}
              className="h-full w-full"
            />
          </div>
        ) : null}

        {/* رأسٌ بأجرةٍ كبيرةٍ وشارةِ حالة (تخطيطُ التصميم): الرقمُ هو ما يُفتح
            له هذا السجلُّ أصلاً، فيُقرأ قبل أن تُقرأ الحقول */}
        <div className="flex items-start justify-between gap-12">
          <div>
            <p className="text-12 text-muted">{formatDateTime(ride.created_at)}</p>
            <p className="text-26 font-bold text-ink">
              {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
            </p>
          </div>
          <Badge tone={ride.status === "completed" ? "success" : "neutral"}>
            {RIDE_STATUS_LABEL[ride.status]}
          </Badge>
        </div>

        <div className="card space-y-12 p-16">
          <Row label="من" value={ride.pickup_address ?? "نقطة على الخريطة"} />
          <Row label="إلى" value={ride.dropoff_address ?? "نقطة على الخريطة"} />
          <Row label="المسافة المقدّرة" value={formatDistance(ride.distance_km)} />
          {ride.actual_distance_km ? (
            <Row
              label="المسافة الفعلية"
              value={formatDistance(ride.actual_distance_km)}
            />
          ) : null}
          <Row label="المدة المقدّرة" value={formatDuration(ride.duration_min)} />
          <Row label="فئة المركبة" value={VEHICLE_LABEL[ride.vehicle_category]} />
          {ride.cancelled_reason ? (
            <Row label="سبب الإلغاء" value={ride.cancelled_reason} />
          ) : null}
        </div>

        <div className="card space-y-8 p-16">
          <Row
            label="السعر المقدّر"
            value={formatMoney(ride.estimated_fare, ride.currency)}
          />
          {ride.final_fare ? (
            <Row
              label="الأجرة النهائية"
              value={formatMoney(ride.final_fare, ride.currency)}
              strong
            />
          ) : null}
          {ride.cancellation_fee ? (
            <Row
              label="رسوم الإلغاء"
              value={formatMoney(ride.cancellation_fee, ride.currency)}
            />
          ) : null}
        </div>

        {/* **بطاقةُ الكبتن كما في التصميم (`pgRideDetail`)** لا صفوفَ
            «حقلٌ: قيمة»: الصفوفُ للأرقام التي تُقارن (أجرةٌ ومسافة)، والكبتنُ
            **شخصٌ يُتعرَّف عليه** — حرفٌ أولُ واسمٌ ومركبةٌ ونجوم. ومن يفتح
            رحلةً مضت يسأل «من أوصلني» لا «ما قيمةُ حقل الكبتن».
            **واللوحةُ لاتينيةٌ بلا تحويل خانات**: تُطابَق حرفاً بحرف. */}
        {ride.driver ? (
          <div className="card flex items-center gap-12 p-14">
            <div className="flex size-44 shrink-0 items-center justify-center rounded-full bg-brand-soft text-16 font-bold text-ink">
              {ride.driver.name.slice(0, 1)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-ink">
                {ride.driver.name}
              </p>
              {ride.driver.vehicle ? (
                <p className="mt-2 truncate text-12.5 text-muted">
                  {ride.driver.vehicle.make} {ride.driver.vehicle.model} ·{" "}
                  {ride.driver.vehicle.color}
                  {" · "}
                  <span dir="ltr">{ride.driver.vehicle.plate_number}</span>
                </p>
              ) : null}
            </div>
            {Number(ride.driver.rating_avg) > 0 ? (
              <span className="shrink-0 text-13 font-semibold text-ink">
                {/* **خاناتٌ لاتينيةٌ لأنها عُرفُ هذا التطبيق**: لا وجودَ
                    لـ`arabicDigits` في `customer-app` أصلاً، وكلُّ سطرِ مالٍ
                    ومسافةٍ فيه لاتينيّ — فتعريبُ رقمٍ واحدٍ يجعله الشاذَّ */}
                {Number(ride.driver.rating_avg).toFixed(1)} ★
              </span>
            ) : null}
          </div>
        ) : null}
        {payments && payments.payments.length > 0 ? (
          <PaymentsList payments={payments.payments} />
        ) : null}

        <ErrorNote message={error} />

        {owing ? (
          <Button size="lg" onClick={() => navigate(`/rides/${ride.id}/pay`)}>
            إكمال الدفع — {formatMoney(payments!.outstanding, payments!.currency)}
          </Button>
        ) : ride.status === "completed" && !rated ? (
          <Button size="lg" onClick={() => navigate(`/rides/${ride.id}/rate`)}>
            قيّم هذه الرحلة
          </Button>
        ) : null}

        {/* «أعد الطلب» — **طلبٌ جديد بنفس النقطتين لا نسخُ رحلةٍ مضت**
            (`FUTURE-FEATURES` بند 3): السعرُ يُعاد حسابه، والمحطاتُ لا
            تُنسخ (قد لا تكون الخدمة مفعّلة اليوم)، والتفضيلُ يُقرأ من الملف
            كأي طلبٍ جديد. ولا يظهر إلا على رحلةٍ انتهت: إعادةُ طلبِ رحلةٍ
            جارية تعني رحلتين */}
        {ride.status === "completed" ? (
          <Button
            size="lg"
            variant="secondary"
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
          </Button>
        ) : null}
      </div>
    </Screen>
  );
}

function Row({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-12 text-14">
      <span className="shrink-0 text-muted">{label}</span>
      <span className={strong ? "text-end font-bold text-ink" : "text-end text-ink"}>
        {value}
      </span>
    </div>
  );
}
