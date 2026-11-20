/** **دوالُّ فقاعة الراكب الخالصة** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — بلا Capacitor ولا أسماءٍ مستعارة (`tests/rider-bubble.test.ts`). */

/** ما تحتاجه الفقاعةُ من الرحلة — بنيويٌّ فيطابق `Ride` في `api/types.ts`. */
export interface BubbleRideInput {
  id: string;
  status: string;
  arrived_at: string | null;
  driver: { name: string; vehicle: { make: string; model: string; color: string; plate_number: string } | null } | null;
}

export type RiderPhase = "searching" | "assigned" | "arrived" | "in_progress";

export function riderPhase(status: string): RiderPhase | null {
  if (status === "requested" || status === "searching") return "searching";
  if (status === "accepted") return "assigned";
  if (status === "arrived") return "arrived";
  if (status === "in_progress") return "in_progress";
  return null;
}

/** **الاسمُ الأوّلُ وحدَه** — كما يُرسل في رابط المشاركة. */
export function firstName(name: string | null | undefined): string {
  return (name ?? "").trim().split(/\s+/)[0] ?? "";
}

/**
 * **ما تعرفه فقاعةُ الراكب** — الطورُ والكابتنُ باسمه الأوّل ومركبتُه ولوحتُه ووقتُ الوصول. **ولا رقمَ هاتفٍ ولا مبلغ**: الإلغاءُ «مجانيٌّ»
 * أثناء البحث وحدَه (قبل القبول — القسم 5)، وما بعده يُقال في ورقة الإلغاء برسمه.
 */
export function riderBubbleRide(ride: BubbleRideInput | null, etaMin: number | null, etaFirst: number | null): string | null {
  if (!ride) return null;
  const phase = riderPhase(ride.status);
  if (!phase) return null;
  const vehicle = ride.driver?.vehicle ?? null;
  const arrivedMs = ride.arrived_at ? Date.parse(ride.arrived_at) : NaN;
  return JSON.stringify({
    id: ride.id,
    phase,
    free_cancel: phase === "searching",
    driver: firstName(ride.driver?.name),
    car: vehicle ? `${vehicle.make} ${vehicle.model}`.trim() : "",
    color: vehicle?.color ?? "",
    plate: vehicle?.plate_number ?? "",
    eta_min: phase === "assigned" && etaMin !== null ? Math.max(0, Math.round(etaMin)) : -1,
    eta_first: phase === "assigned" && etaFirst !== null ? Math.max(1, Math.round(etaFirst)) : -1,
    arrived_ms: phase === "arrived" && Number.isFinite(arrivedMs) ? arrivedMs : 0,
  });
}
