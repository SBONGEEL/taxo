/** **اقتراحُ الوجهة الذكيّ** (SPEC §١٠٣ C/35، خلف `smart_destination`) — الحسابُ في `smart-destination-core.ts`.
 *
 * **في الهاتف وحدَه**: السجلُّ في تخزين الجهاز بمفتاحٍ لكلِّ مستخدم، ولا نداءَ ولا حقلَ جديدٌ في الخادم. **ومطفأً لا يُكتب شيءٌ
 * ولا يُرسم شيء** — والرئيسيّةُ كما كانت حرفاً.
 */
import { useEffect, useState } from "react";

import { useFeature } from "@/lib/config";
import { appendVisit, suggestDestination, type DestinationSuggestion, type DestinationVisit } from "@/lib/smart-destination-core";
import type { CountryCode } from "@/api/types";

const keyFor = (userId: string) => `taxo.dest.history.${userId}`;

function readHistory(userId: string): DestinationVisit[] {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter(
          (row): row is DestinationVisit =>
            typeof row === "object" && row !== null && typeof (row as DestinationVisit).lat === "number" &&
            typeof (row as DestinationVisit).lng === "number" && typeof (row as DestinationVisit).at === "number" &&
            typeof (row as DestinationVisit).address === "string",
        )
      : [];
  } catch {
    return [];
  }
}

/** يُنادى حين تُنشأ رحلة — **مرّةً لكلِّ رحلة** (المُعرِّفُ يمنع التكرار). */
export function useRecordDestination(
  country: CountryCode | undefined,
  userId: string | undefined,
  ride: { id: string; dropoff: { lat: number; lng: number }; dropoff_address: string | null } | null,
): void {
  const on = useFeature(country, "smart_destination");
  useEffect(() => {
    if (!on || !userId || !ride || !ride.dropoff_address) return;
    try {
      const seenKey = `taxo.dest.seen.${userId}`;
      if (localStorage.getItem(seenKey) === ride.id) return;
      const next = appendVisit(readHistory(userId), {
        lat: ride.dropoff.lat,
        lng: ride.dropoff.lng,
        address: ride.dropoff_address,
        at: Date.now(),
      });
      localStorage.setItem(keyFor(userId), JSON.stringify(next));
      localStorage.setItem(seenKey, ride.id);
    } catch {
      // تخزينٌ محجوب — لا اقتراحَ، ولا شيءَ ينكسر
    }
    // المُعرِّفُ وحدَه يكفي: الرحلةُ نفسُها تُبثّ في كلِّ إطار
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, userId, ride?.id]);
}

export function useSmartDestination(
  country: CountryCode | undefined,
  userId: string | undefined,
  here: { lat: number; lng: number } | null,
): DestinationSuggestion | null {
  const on = useFeature(country, "smart_destination");
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const timer = window.setInterval(() => setNow(Date.now()), 5 * 60_000);
    return () => window.clearInterval(timer);
  }, [on]);
  if (!on || !userId) return null;
  return suggestDestination(readHistory(userId), now, here);
}
