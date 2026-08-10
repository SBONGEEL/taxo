/** رحلاتي: السجل ثم التفاصيل (SPEC القسم 11.7). */

import { ChevronLeft, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { RIDE_STATUS_LABEL } from "@/lib/labels";
import { formatDateTime, formatMoney } from "@/lib/utils";

const PAGE = 20;

export function RidesScreen() {
  const [rides, setRides] = useState<Ride[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);

  async function load(offset: number) {
    try {
      const page = await listMyRides(PAGE, offset);
      setRides((current) => (offset === 0 ? page : [...current, ...page]));
      setMore(page.length === PAGE);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة رحلاتك");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(0);
  }, []);

  return (
    <Screen title="رحلاتي" back="/menu">
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-3">
          <ErrorNote message={error} />

          {rides.length === 0 ? (
            <EmptyState title="لا رحلات بعد" hint="أول رحلة تبدأ من الشاشة الرئيسية." />
          ) : (
            <ul className="space-y-2">
              {rides.map((ride) => (
                <li key={ride.id}>
                  <Link
                    to={`/rides/${ride.id}`}
                    className="card flex items-center gap-3 p-3 transition hover:bg-line/20"
                  >
                    <MapPin className="size-5 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">
                        {ride.dropoff_address ?? "وجهة على الخريطة"}
                      </p>
                      <p className="text-xs text-muted">
                        {formatDateTime(ride.created_at)}
                      </p>
                    </div>
                    <div className="shrink-0 text-end">
                      <p className="font-semibold text-ink">
                        {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
                      </p>
                      <Badge tone={ride.status === "completed" ? "success" : "neutral"}>
                        {RIDE_STATUS_LABEL[ride.status]}
                      </Badge>
                    </div>
                    <ChevronLeft className="size-4 shrink-0 text-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {more ? (
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => load(rides.length)}
            >
              عرض المزيد
            </Button>
          ) : null}
        </div>
      )}
    </Screen>
  );
}
