import { useEffect } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import type { CountryCode, Ride } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { digits } from "@/lib/utils";

/**
 * **إشعارُ التتبّع الحيّ للراكب** (SPEC §١٠٣ B/19) — إشعارٌ واحدٌ مستمرٌّ صامتٌ يتبدّل سطرُه بحال الرحلة، خلف `ride_live_tracking`.
 * **الويبُ وحدَه يكتبه ويمحوه** (`RideLivePlugin.java`) — فلا يبقى بعد رحلةٍ انتهت، ولا يُرسم وهو مطفأ.
 */
const native = registerPlugin<{
  show(options: { title: string; text: string }): Promise<void>;
  clear(): Promise<void>;
}>("RideLive");

export interface LiveLine {
  title: string;
  text: string;
}

/** خالصةٌ ومختبَرة: الحالُ ودقائقُ الاقتراب ⇐ السطر، أو `null` لما ليس رحلةً جارية. */
export function rideLiveLine(ride: Ride | null, approachMinutes: number | null): LiveLine | null {
  if (!ride) return null;
  const plate = ride.driver?.vehicle?.plate_number ?? "";
  const car = ride.driver?.vehicle ? `${ride.driver.vehicle.make} ${ride.driver.vehicle.model}`.trim() : "";
  const who = [car, plate].filter(Boolean).join(" · ");
  switch (ride.status) {
    case "accepted":
      return {
        title:
          approachMinutes != null && approachMinutes > 0
            ? tr("الكبتن في الطريق — يصل خلال {0} د", { 0: digits(approachMinutes) })
            : tr("الكبتن في الطريق إليك"),
        text: who,
      };
    case "arrived":
      return { title: tr("الكبتن وصل إلى نقطة الانطلاق"), text: who };
    case "in_progress":
      return { title: tr("في الرحلة — إلى وجهتك"), text: who };
    case "at_stop":
      return { title: tr("في محطة توقّف"), text: who };
    default:
      return null;
  }
}

export function useRideLive(country: CountryCode | undefined, ride: Ride | null, approachMinutes: number | null): void {
  const on = useFeature(country, "ride_live_tracking");
  const line = on ? rideLiveLine(ride, approachMinutes) : null;
  const title = line?.title ?? null;
  const text = line?.text ?? "";
  useEffect(() => {
    if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("RideLive")) return;
    if (title) void native.show({ title, text }).catch(() => undefined);
    else void native.clear().catch(() => undefined);
  }, [title, text]);
  // يُمحى حين تُغادَر الشاشة أو يُطفأ المفتاح — ولا يبقى يتيماً
  useEffect(
    () => () => {
      if (Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("RideLive")) void native.clear().catch(() => undefined);
    },
    [],
  );
}
