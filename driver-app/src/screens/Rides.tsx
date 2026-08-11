/** سجل الرحلات — SPEC القسم 12/6، وشكلُه من `DESIGN.md` §5.3.
 *
 * «للكبتن ما أُسند إليه» — الخلفية تفصل ذلك، والشاشة لا تفلتر بيدها.
 *
 * **وشارةُ النزاع ليست في هذه القائمة**: حالُ الدفع تعيش على `payments` لا
 * على `rides`، و`GET /rides/me` لا يحملها. وسؤالُ الخلفية عن دفعات كل صفٍّ
 * على حدة عشرون نداءً لصفحةٍ واحدة. فالشارة مكانُها التفاصيل حيث يُسأل عن
 * رحلةٍ واحدة — والتصميم يعرضها في القائمة، وهذا انحرافٌ مقصود مذكورٌ في
 * تقرير الجلسة.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { BottomNav } from "@/components/BottomNav";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import {
  CURRENCY_LABEL,
  RIDE_STATUS_LABEL,
  formatWhen,
  statusTone,
  trimDistance,
} from "@/lib/rideFormat";
import { arabicDigits, cn } from "@/lib/utils";

/** حدُّ الخلفية 100، وصفحةٌ من عشرين تكفي شاشةً وتترك «المزيد» صادقاً. */
const PAGE_SIZE = 20;

export function RidesScreen() {
  const navigate = useNavigate();
  const [rides, setRides] = useState<Ride[] | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (offset: number) => {
    setBusy(true);
    try {
      const page = await listMyRides(PAGE_SIZE, offset);
      setRides((current) =>
        offset === 0 ? page : [...(current ?? []), ...page],
      );
      // صفحةٌ ممتلئةٌ تماماً تعني «قد يكون بعدها المزيد» — والسؤالُ التالي
      // وحده يحسم، فالخلفية لا تردّ عدداً كلياً
      setMore(page.length === PAGE_SIZE);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة السجل",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <h1 className="mb-16 mt-6 text-20 font-bold text-ink">سجل الرحلات</h1>

        <ErrorNote message={error} />

        {rides === null && !error ? <Spinner className="mx-auto" /> : null}

        {rides?.length === 0 ? (
          <EmptyNote
            title="لا رحلات بعد"
            hint="ستظهر هنا كل رحلةٍ أنهيتَها، بأجرتها وتفصيلها."
          />
        ) : null}

        <ul className="flex flex-col gap-10">
          {(rides ?? []).map((ride) => (
            <li key={ride.id}>
              <button
                type="button"
                onClick={() => navigate(`/rides/${ride.id}`)}
                className="w-full rounded-16 border border-line bg-surface px-14 py-13 text-start"
              >
                <div className="mb-8 flex items-baseline justify-between">
                  <span className="text-12 text-muted">
                    {formatWhen(ride.created_at)}
                  </span>
                  <span className="text-15 font-bold text-ink">
                    {ride.final_fare
                      ? `${arabicDigits(ride.final_fare)} ${CURRENCY_LABEL[ride.currency]}`
                      : "—"}
                  </span>
                </div>

                <div className="grid grid-cols-[10px_minmax(0,1fr)] gap-x-9 gap-y-3">
                  <span className="mx-auto mt-5 block size-7 rounded-full bg-ink" />
                  <div className="truncate text-12.5 text-ink">
                    {ride.pickup_address ?? "نقطة الانطلاق"}
                  </div>
                  <span className="mx-auto block h-9 w-2 bg-line" />
                  <span />
                  <span className="mx-auto mt-3 block size-7 rounded-2 bg-muted" />
                  <div className="truncate text-12.5 text-muted">
                    {ride.dropoff_address ?? "الوجهة"}
                  </div>
                </div>

                <div className="mt-9 flex items-center gap-9 border-t border-line pt-9 text-11 text-muted">
                  <span>
                    {trimDistance(ride.actual_distance_km ?? ride.distance_km)}{" "}
                    كم
                  </span>
                  <span
                    className={cn("ms-auto font-bold", statusTone(ride.status))}
                  >
                    {RIDE_STATUS_LABEL[ride.status]}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>

        {more ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void load(rides?.length ?? 0)}
            className="mt-12 w-full rounded-14 border border-line py-13 text-center text-12.5 font-semibold text-muted disabled:opacity-60"
          >
            {busy ? "…" : "عرض المزيد"}
          </button>
        ) : null}
      </div>

      <BottomNav />
    </div>
  );
}
