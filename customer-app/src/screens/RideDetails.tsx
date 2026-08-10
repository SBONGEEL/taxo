/** تفاصيل رحلة سابقة: المسار، والأجرة، والدفعات، والتقييم (القسم 11.7).
 *
 * **المسافة الفعلية تُعرض حين تكون** ولا تُخترع حين تغيب: `null` تعني أن
 * تطبيق الكبتن صمت فبقي المقدَّر هو الحكم — وصفرٌ في مكانها يقول «سار صفر
 * كيلومتر» (SPEC القسم 4/5.7).
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, getRidePayments, listRideRatings } from "@/api/endpoints";
import type { Rating, Ride, RidePayments } from "@/api/types";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { Button } from "@/components/ui/Button";
import { Badge, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { formatDateTime, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

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

  if (loading) {
    return (
      <Screen title="تفاصيل الرحلة">
        <Spinner />
      </Screen>
    );
  }

  if (!ride) {
    return (
      <Screen title="تفاصيل الرحلة">
        <ErrorNote message={error ?? "الرحلة غير موجودة"} />
      </Screen>
    );
  }

  const owing = payments !== null && Number(payments.outstanding) > 0;
  const rated = ratings.some((entry) => entry.rater_type === "rider");

  return (
    <Screen title="تفاصيل الرحلة">
      <div className="space-y-5">
        <div className="card space-y-3 p-4">
          <div className="flex items-center justify-between">
            <Badge tone={ride.status === "completed" ? "success" : "neutral"}>
              {RIDE_STATUS_LABEL[ride.status]}
            </Badge>
            <span className="text-xs text-muted">{formatDateTime(ride.created_at)}</span>
          </div>

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

        <div className="card space-y-2 p-4">
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

        {ride.driver ? (
          <div className="card space-y-2 p-4">
            <Row label="الكبتن" value={ride.driver.name} />
            {ride.driver.vehicle ? (
              <>
                <Row
                  label="المركبة"
                  value={`${ride.driver.vehicle.make} ${ride.driver.vehicle.model} — ${ride.driver.vehicle.color}`}
                />
                <Row label="اللوحة" value={ride.driver.vehicle.plate_number} />
              </>
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
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="shrink-0 text-muted">{label}</span>
      <span className={strong ? "text-end font-bold text-ink" : "text-end text-ink"}>
        {value}
      </span>
    </div>
  );
}
