/** رحلاتي: السجل ثم التفاصيل (SPEC القسم 11.7). */

import { ChevronLeft, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { RideListItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { RIDE_STATUS_LABEL } from "@/lib/labels";
import { formatDateTime, formatMoney } from "@/lib/utils";

const PAGE = 20;

export function RidesScreen() {
  const [rides, setRides] = useState<RideListItem[]>([]);
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
        <div className="space-y-12">
          <ErrorNote message={error} />

          {rides.length === 0 ? (
            <EmptyState title="لا رحلات بعد" hint="أول رحلة تبدأ من الشاشة الرئيسية." />
          ) : (
            <ul className="space-y-8">
              {rides.map(({ ride, has_open_dispute }) => (
                <li key={ride.id}>
                  <Link
                    to={`/rides/${ride.id}`}
                    className="card flex items-center gap-12 p-12 transition hover:bg-surface-2"
                  >
                    <MapPin className="size-20 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">
                        {ride.dropoff_address ?? "وجهة على الخريطة"}
                      </p>
                      <p className="text-12 text-muted">
                        {formatDateTime(ride.created_at)}
                      </p>
                    </div>
                    <div className="shrink-0 text-end">
                      <p className="font-semibold text-ink">
                        {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
                      </p>
                      <div className="flex items-center justify-end gap-6">
                        {/* شارةُ النزاع — نفسُ نغمة «متنازع فيها» في قائمة الدفعات،
                            لا نغمةَ تطبيق الكبتن: الراكب يرى الحالتين في شاشةٍ واحدة. */}
                        {has_open_dispute ? <Badge tone="danger">نزاع</Badge> : null}
                        <Badge tone={ride.status === "completed" ? "success" : "neutral"}>
                          {RIDE_STATUS_LABEL[ride.status]}
                        </Badge>
                      </div>
                    </div>
                    <ChevronLeft className="size-16 shrink-0 text-muted" />
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
