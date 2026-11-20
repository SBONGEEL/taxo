/** **«تعديل الوجهة»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ) — متى يُرسم الزرّ.
 *
 *  **ثلاثةُ شروطٍ معاً**: نوعُ الرحلة يسمح (`destination_editable` من الخلفيّة — لا يُعاد حسابُه هنا فيفترق)، **ومفتاحُ طورها مشتعلٌ
 *  في دولتها**، وحالُها في أحد الطورين. **مطفأً لا زرّ** — والبابُ يرفض على كلِّ حال، فالزرُّ وعدٌ لا يُرسم بلا بابٍ يفي به. */

import type { Ride } from "@/api/types";

export const DESTINATION_CHANGE_SEARCHING_FLAG = "destination_change_searching";
export const DESTINATION_CHANGE_IN_RIDE_FLAG = "destination_change_in_ride";

const SEARCHING = new Set(["requested", "searching"]);
const IN_RIDE = new Set(["accepted", "arrived", "in_progress"]);

export type DestinationPhase = "searching" | "in_ride";

export function destinationPhase(status: string): DestinationPhase | null {
  if (SEARCHING.has(status)) return "searching";
  if (IN_RIDE.has(status)) return "in_ride";
  return null;
}

export function canChangeDestination(
  ride: Pick<Ride, "status" | "destination_editable">,
  flags: { searching: boolean; inRide: boolean },
): boolean {
  if (!ride.destination_editable) return false;
  const phase = destinationPhase(ride.status);
  if (phase === "searching") return flags.searching;
  if (phase === "in_ride") return flags.inRide;
  return false;
}
