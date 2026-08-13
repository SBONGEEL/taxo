/** رحلاتي المجدولة (SPEC القسم 5.11، المرحلة 12-ط).
 *
 * **وجملةُ الحال تُبنى هنا من حقيقتين**: حالِ الحجز وحالِ رحلته. فلا عمودَ
 * `fulfilled` في الخلفية يقول ذلك — ما جرى بعد التسليم تقوله الرحلةُ نفسُها،
 * وعمودٌ يكرّره يفترق عنه أولَ مرةٍ تُلغى فيها رحلةٌ وُجد لها كبتن.
 *
 * **والإلغاءُ من هنا لحجزٍ منتظرٍ وحده**: بعد التسليم صارت له رحلةٌ تُلغى من
 * شاشتها وبرسمها — وزرٌّ هنا يُلغي رحلةً يجعل رسمَ الإلغاء يُخصم من مكانٍ لا
 * يذكره صاحبُه.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { cancelBooking, listBookings } from "@/api/endpoints";
import type { Booking } from "@/api/types";
import { Screen } from "@/components/ui/Screen";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { formatMoney } from "@/lib/utils";

/** أوّلُ حقيقةٍ تحكم: الحجزُ ثم رحلتُه — لا سردٌ للاثنين. */
function stateOf(booking: Booking): { text: string; tone: string } {
  if (booking.status === "cancelled") {
    return { text: "أُلغي", tone: "text-muted" };
  }
  if (booking.status === "missed") {
    return { text: "لم يُنفَّذ — كنتَ في رحلةٍ حينها", tone: "text-warn" };
  }
  if (booking.status === "pending") {
    return { text: "بانتظار موعده", tone: "text-ink" };
  }
  // سُلّم للتوزيع: الرحلةُ تقول الباقي
  switch (booking.ride_status) {
    case "no_driver_found":
      return { text: "لم نجد كبتناً", tone: "text-danger" };
    case "completed":
      return { text: "اكتملت", tone: "text-ok" };
    case "cancelled_by_rider":
    case "cancelled_by_driver":
      return { text: "أُلغيت الرحلة", tone: "text-muted" };
    case null:
    case undefined:
      return { text: "طُلبت الرحلة", tone: "text-ok" };
    default:
      return { text: "رحلتك جارية", tone: "text-ok" };
  }
}

function when(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("ar", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function BookingsScreen() {
  const [rows, setRows] = useState<Booking[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await listBookings());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الحجوزات"),
    );
  }, [load]);

  async function drop(bookingId: string) {
    setBusy(bookingId);
    setError(null);
    try {
      await cancelBooking(bookingId);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الإلغاء");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Screen title="رحلاتي المجدولة" back>
      <ErrorNote message={error} />
      {rows === null && !error ? <Spinner /> : null}
      {rows?.length === 0 ? (
        <EmptyState
          title="لا حجوزَ بعد"
          hint="حدّد موعداً من شاشة تأكيد الرحلة."
        />
      ) : null}

      <ul className="space-y-10">
        {(rows ?? []).map((booking) => {
          const state = stateOf(booking);
          return (
            <li
              key={booking.id}
              className="rounded-16 border border-line bg-surface p-14"
            >
              <div className="flex items-start justify-between gap-10">
                <div className="min-w-0">
                  <p className="text-14 font-semibold text-ink">
                    {when(booking.scheduled_at)}
                  </p>
                  <p className="mt-2 truncate text-12 text-muted">
                    {booking.dropoff_address ?? "نقطة على الخريطة"}
                  </p>
                </div>
                <span className={`shrink-0 text-12 font-medium ${state.tone}`}>
                  {state.text}
                </span>
              </div>

              <div className="mt-10 flex items-center justify-between gap-10">
                <span className="text-12 text-muted">
                  {/* **تقديرٌ لا أجرة** — والسعرُ يُحسب عند التنفيذ */}
                  {booking.estimated_fare_at_booking
                    ? `تقديراً ${formatMoney(booking.estimated_fare_at_booking, booking.currency)}`
                    : "بلا تقدير"}
                </span>
                {booking.status === "pending" ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="w-auto px-14"
                    loading={busy === booking.id}
                    onClick={() => void drop(booking.id)}
                  >
                    ألغِ الحجز
                  </Button>
                ) : booking.ride_id ? (
                  <Link
                    to={`/rides/${booking.ride_id}`}
                    className="text-12 font-semibold text-ink underline"
                  >
                    تفاصيل الرحلة
                  </Link>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </Screen>
  );
}
