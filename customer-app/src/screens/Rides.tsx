/** رحلاتي: السجل ثم التفاصيل (SPEC القسم 11.7). */

import { ChevronLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { RideListItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { PAYMENT_METHOD_LABEL, RIDE_STATUS_LABEL } from "@/lib/labels";
import { formatDateTime, formatDistance, formatMoney } from "@/lib/utils";

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
    <Screen title="رحلاتي" nav back={false}>
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-12">
          <ErrorNote message={error} />

          {rides.length === 0 ? (
            <EmptyState title="لا رحلات بعد" hint="أول رحلة تبدأ من الشاشة الرئيسية." />
          ) : (
            <ul className="space-y-8">
              {rides.map(({ ride, has_open_dispute, payment_methods }) => (
                <li key={ride.id}>
                  <Link
                    to={`/rides/${ride.id}`}
                    className="card flex items-center gap-12 p-12 transition hover:bg-surface-2"
                  >
                    <div className="min-w-0 flex-1 space-y-8">
                      <div className="flex items-baseline justify-between gap-8">
                        <span className="text-12 text-muted">
                          {formatDateTime(ride.created_at)}
                        </span>
                        <span className="font-semibold text-ink">
                          {formatMoney(
                            ride.final_fare ?? ride.estimated_fare,
                            ride.currency,
                          )}
                        </span>
                      </div>

                      {/* **مسارُ نقطتين** كما في التصميم: الوجهةُ وحدها لا تقول
                          من أين جاءت الرحلة، وسجلٌّ كلُّه وجهاتٌ يتشابه */}
                      <div className="grid grid-cols-[10px_1fr] items-center gap-x-9 gap-y-3">
                        <span className="mx-auto size-7 rounded-full bg-ink" />
                        <span className="truncate text-12.5 text-ink">
                          {ride.pickup_address ?? "نقطة على الخريطة"}
                        </span>
                        <span className="mx-auto h-9 w-2 bg-line" />
                        <span />
                        <span className="mx-auto size-7 rounded-2 bg-muted" />
                        <span className="truncate text-12.5 text-muted">
                          {ride.dropoff_address ?? "وجهة على الخريطة"}
                        </span>
                      </div>

                      {/* **المسافةُ والقناةُ والحالة** (القرار 37): المسافةُ تصل
                          مع الرحلة، والقنواتُ في `payment_methods` من
                          `GET /rides/me` — كانت تصل في كل نداءٍ ولا يقرؤها أحد */}
                      <div className="flex items-center gap-6 border-t border-line pt-9 text-11 text-muted">
                        <span>{formatDistance(ride.actual_distance_km ?? ride.distance_km)}</span>
                        {payment_methods.length > 0 ? (
                          <>
                            <span>·</span>
                            <span className="truncate">
                              {payment_methods
                                .map((method) => PAYMENT_METHOD_LABEL[method])
                                .join(" + ")}
                            </span>
                          </>
                        ) : null}
                        <span className="ms-auto flex items-center gap-6">
                          {/* شارةُ النزاع — نفسُ نغمة «متنازع فيها» في قائمة
                              الدفعات، لا نغمةَ تطبيق الكبتن */}
                          {has_open_dispute ? <Badge tone="danger">نزاع</Badge> : null}
                          <Badge
                            tone={ride.status === "completed" ? "success" : "neutral"}
                          >
                            {RIDE_STATUS_LABEL[ride.status]}
                          </Badge>
                        </span>
                      </div>
                    </div>
                    <ChevronLeft className="size-16 shrink-0 self-center text-muted" />
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
