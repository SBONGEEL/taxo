/** **دوالُّ الفقاعة الخالصة** (SPEC §١١٠) — بلا Capacitor ولا أسماءٍ مستعارة، فيختبرها `node --test` (`tests/bubble-core.test.ts`). */
/** ما تحتاجه الفقاعةُ من الرحلة — بنيويٌّ فيطابق `Ride` في `api/types.ts` بلا استيراده. */
interface Ride {
  id: string;
  status: string;
  arrived_at: string | null;
  pickup: { lat: number; lng: number };
  dropoff: { lat: number; lng: number };
}

/** **الهدفُ رقمٌ موجبٌ بثلاث منازل على الأكثر** — وما عداه «بلا هدف». خالصٌ ومختبَر. */
export function cleanGoal(raw: string): string {
  // الخانُ العربيّةُ-الهنديّةُ تُقرأ لاتينيّة — بترميزها لا بحرفها (`check:digits`)
  const text = raw.trim().replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
  if (!/^\d{1,5}(\.\d{1,3})?$/.test(text)) return "";
  return Number(text) > 0 ? text : "";
}

/** **ما تعرفه الفقاعةُ عن الرحلة** — المعرّفُ والحالُ ووقتُ الوصول ووجهةُ الملاحة؛ **ولا رقمَ هاتفٍ ولا اسمَ لم يصل التطبيقَ أصلاً**.
 *  خالصٌ ومختبَر. */
export function bubbleRide(ride: Pick<Ride, "id" | "status" | "arrived_at" | "pickup" | "dropoff"> | null): string | null {
  if (!ride) return null;
  const status = ride.status;
  if (status !== "accepted" && status !== "arrived" && status !== "in_progress") return null;
  const to = status === "in_progress" ? ride.dropoff : ride.pickup;
  return JSON.stringify({
    id: ride.id,
    status,
    rider: "الراكب",
    arrived_at: ride.arrived_at,
    nav_lat: to.lat,
    nav_lng: to.lng,
  });
}
