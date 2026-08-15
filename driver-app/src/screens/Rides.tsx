/** سجل الرحلات — SPEC القسم 12/6، وشكلُه من `DESIGN.md` §5.3.
 *
 * «للكبتن ما أُسند إليه» — الخلفية تفصل ذلك، والشاشة لا تفلتر بيدها.
 *
 * **وشارةُ النزاع في القائمة الآن** (`FUTURE-FEATURES` بند 19). كانت غائبةً
 * لأن حالَ الدفع تعيش على `payments` و`GET /rides/me` لا يحملها، وسؤالُ
 * الخلفية عن دفعات كل صفٍّ عشرون نداءً لصفحةٍ واحدة. فصار المسارُ يضمّ
 * الملخّصَ **في استعلامٍ ثانٍ لصفحةٍ كاملة** — لا نداءٌ لكل صف ولا حقلٌ
 * يُثقل `Ride` في كل إطار مقبس.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { RideListItem } from "@/api/types";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
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
  const [rides, setRides] = useState<RideListItem[] | null>(null);
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

        <Stagger className="flex flex-col gap-10">
          {(rides ?? []).map(
            ({ ride, has_open_dispute, settlement }) => (
            <StaggerItem key={ride.id}>
              <button
                type="button"
                onClick={() => navigate(`/rides/${ride.id}`)}
                className="pressable w-full card px-14 py-13 text-start"
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
                  {/* **مالٌ لم يُقفل بعد** — كشفته تجربةُ المرحلة ١٣: بعد
                      إعادة فتح التطبيق يختفي كلُّ ما يدلّ على رحلةٍ تنتظر
                      تأكيدَه، فيبقى المالُ في يده والدفعةُ `pending` بلا أن
                      يعرف. **والحكمُ يصل الآن محسوباً** (`settlement`) من
                      `services/settlement.py` بعد أن كانت المقارنةُ هنا
                      إحدى أربعٍ تجيب سؤالاً واحداً بأربع طرق */}
                  {settlement === "due" || settlement === "awaiting" ? (
                    <span className="rounded-full border border-warn px-8 py-2 text-10 font-bold text-warn">
                      {/* **«بانتظار تأكيدك» غيرُ «لم تُدفع»**: الأولى صفُّ
                          دفعةٍ ينتظر ضغطتَه هو، والثانيةُ راكبٌ لم يختر بعد —
                          وعليه في الأولى عملٌ وليس عليه في الثانية شيء.
                          وخلطُهما يجعله يفتش عن زرٍّ لا وجودَ له */}
                      {settlement === "awaiting" ? "بانتظار تأكيدك" : "لم تُدفع"}
                    </span>
                  ) : null}
                  {/* شارةُ النزاع — برتقاليةٌ في ذيل الصف كما في التصميم */}
                  {has_open_dispute ? (
                    <span className="rounded-full border border-warn px-8 py-2 text-10 font-bold text-warn">
                      نزاع
                    </span>
                  ) : null}
                  <span
                    className={cn("ms-auto font-bold", statusTone(ride.status))}
                  >
                    {RIDE_STATUS_LABEL[ride.status]}
                  </span>
                </div>
              </button>
            </StaggerItem>
            ),
          )}
        </Stagger>

        {more ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void load(rides?.length ?? 0)}
            className="pressable mt-12 w-full rounded-14 border border-line py-13 text-center text-12.5 font-semibold text-muted disabled:opacity-60"
          >
            {busy ? "…" : "عرض المزيد"}
          </button>
        ) : null}
      </div>

    </div>
  );
}
