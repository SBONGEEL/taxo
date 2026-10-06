/** **زمنُ الوصول عند الراكب** (§٦٢-ج/١٠) — «اقتصادي يصل خلال 3 د» قبل الطلب (R05 · R06)، و«· 5 د» في التتبّع (R08).
 *
 * **والكلفةُ على المالك** (`eta_enabled` لكلِّ سوق): قبل الطلب سؤالٌ كلَّ دقيقةٍ ما دامت الرئيسيةُ أو ورقةُ الطلب مفتوحة — والخادمُ
 * يخزّن الجوابَ دقيقةً للحيّ، **فتحريكُ الدبوس في الحيّ نفسِه لا يدفع نداء**؛ وفي الطريق إليها **مسارُ الاقتراب مرّةً** ثمّ يُحسب
 * الباقي هنا من موضع الكبتن المبثوث (نسبةُ ما بقي على الخطّ من مدّته) — **لا سؤالَ كلَّ دقيقة**. ومطفأً لا رقمَ ولا موضعٌ يُحجز.
 */

import { useEffect, useMemo, useState } from "react";

import { getApproach, getNearestEta, type ApproachRoute } from "@/api/endpoints";
import type { Coordinates, Ride, VehicleCategory } from "@/api/types";
import { distanceKm, type LatLng } from "@/lib/route-line";

export type CategoryMinutes = Partial<Record<VehicleCategory, number>>;

const EVERY_MS = 60_000;

/** خليّةُ السؤال — **نصفُ منزلةٍ ثالثة** كخليّة الخادم (≈٥٥٠ م): حركةٌ داخلها لا تعيد السؤال. */
function cell(value: number): number {
  return Math.floor(value * 200) / 200;
}

/** دقائقُ أقرب كبتنٍ متاحٍ لكلِّ فئة — و`null` حيث المفتاحُ مطفأ أو لا جواب (فلا يُرسم شيء). */
export function useNearestEta(point: Coordinates | null, active: boolean): CategoryMinutes | null {
  const [minutes, setMinutes] = useState<CategoryMinutes | null>(null);
  const lat = point ? cell(point.lat) : null;
  const lng = point ? cell(point.lng) : null;
  useEffect(() => {
    if (!active || lat === null || lng === null || !point) {
      setMinutes(null);
      return;
    }
    const at = { lat: point.lat, lng: point.lng };
    let cancelled = false;
    const ask = () =>
      getNearestEta(at)
        .then((answer) => {
          if (cancelled) return;
          if (!answer.enabled) {
            setMinutes(null);
            return;
          }
          const next: CategoryMinutes = {};
          for (const row of answer.categories) next[row.vehicle_category] = row.minutes;
          setMinutes(next);
        })
        .catch(() => undefined);
    void ask();
    const timer = window.setInterval(ask, EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // الخليّةُ لا الإحداثيّةُ الدقيقة — وإلا أعادت كلُّ حركةٍ صغيرةٍ للدبوس السؤال
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, lat, lng]);
  return minutes;
}

/** **أقلُّ الدقائق** — شارةُ «3 د» على بلاطة «رحلة» (R05)؛ و`null` إن لم يُعرف شيء. */
export function fastestMinutes(minutes: CategoryMinutes | null): number | null {
  if (!minutes) return null;
  const values = Object.values(minutes).filter((value): value is number => typeof value === "number");
  return values.length > 0 ? Math.min(...values) : null;
}

/** ما بقي من الاقتراب بالدقائق — **أقربُ رأسٍ على الخطّ إلى الكبتن ثمّ ما بعده إلى نهايته**، نسبةً من مدّته؛ ودقيقةٌ حدٌّ أدنى. */
function minutesLeft(route: ApproachRoute, at: LatLng): number | null {
  if (route.distance_km <= 0 || route.points.length < 2) return null;
  const vertex = (index: number): LatLng => ({ lng: route.points[index][0], lat: route.points[index][1] });
  let nearest = 0;
  let nearestKm = Infinity;
  for (let index = 0; index < route.points.length; index += 1) {
    const km = distanceKm(at, vertex(index));
    if (km < nearestKm) {
      nearestKm = km;
      nearest = index;
    }
  }
  let leftKm = nearestKm;
  for (let index = nearest; index < route.points.length - 1; index += 1) {
    leftKm += distanceKm(vertex(index), vertex(index + 1));
  }
  const share = Math.min(1, leftKm / route.distance_km);
  return Math.max(1, Math.round(share * route.duration_min));
}

/** دقائقُ الكبتن إليها في طريقه (R08) — **مسارُ الاقتراب مرّةً لرحلةٍ مقبولة**، والباقي من موضعه المبثوث. */
export function useApproachMinutes(ride: Ride | null, ping: LatLng | null): number | null {
  const id = ride && ride.status === "accepted" ? ride.id : null;
  const [route, setRoute] = useState<ApproachRoute | null>(null);
  useEffect(() => {
    setRoute(null);
    if (!id) return;
    let cancelled = false;
    getApproach(id)
      .then((answer) => {
        if (!cancelled && answer.points.length >= 2) setRoute(answer);
      })
      // **و٤٠٤ حالٌ صحيحة** (المفتاحُ مطفأ) — الحبّةُ تقول المسافةَ وحدَها كما كانت
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [id]);
  return useMemo(() => (id && route && ping ? minutesLeft(route, ping) : null), [id, route, ping]);
}
