/** **زرُّ الصوت ثلاثاً للطوارئ** (SPEC §١٠٣ B/22) — يشعله الراكبُ بنفسه ويختار جهتَه، خلف `volume_emergency` لدولته.
 *
 * **ما يحدث عند الضغطة الثالثة في رحلةٍ جارية**: (١) تنبيهُ فريق TAXO من الباب القائم (`POST /emergency`، والموقعُ الحيُّ مع الطرفين في
 * اللوحة)؛ (٢) **رسالةٌ إلى الجهة المختارة جاهزةٌ برابط التتبّع الحيّ** في تطبيق الرسائل — **والإرسالُ ضغطةٌ من الراكب**: إرسالُ SMS صامتاً
 * يحتاج إذنَ `SEND_SMS` الذي تحصره Google Play في تطبيقات الرسائل الافتراضيّة، فلا يُطلب. **والجهةُ على الجهاز وحدَه**، لا تصل الخادم.
 */
import { useEffect } from "react";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";

import { createTrackLink, pressEmergency } from "@/api/endpoints";
import type { CountryCode, Ride } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { trackUrl } from "@/lib/for-other";

const native = registerPlugin<{
  arm(options: { on: boolean }): Promise<void>;
  addListener(event: "trigger", handler: () => void): Promise<PluginListenerHandle>;
}>("VolumeTrigger");

const ENABLED = "taxo.sos.volume";
const CONTACT = "taxo.sos.contact";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // تخزينٌ محجوب — الإعدادُ لا يُحفظ، والميزةُ تبقى مطفأة
  }
}

/** خالصة: رقمٌ دوليٌّ صالحٌ للجهة (+ اختياريّة، ٨–١٥ خانة) أو `null`. */
export function normalizeContact(raw: string): string | null {
  const cleaned = raw.replace(/[\s-]/g, "").replace(/^00/, "+");
  return /^\+?[0-9]{8,15}$/.test(cleaned) ? cleaned : null;
}

export function volumeEmergencyChosen(): boolean {
  return read(ENABLED) === "1";
}

export function volumeEmergencyContact(): string | null {
  return read(CONTACT);
}

export function setVolumeEmergency(on: boolean, contact: string | null): void {
  write(ENABLED, on ? "1" : "0");
  write(CONTACT, contact);
}

/** خالصة: نصُّ الرسالة — **بلا رصيدٍ ولا شيءٍ من الحساب**، الرابطُ واللوحةُ وحدَهما. */
export function emergencyText(live: string | null, plate: string | null): string {
  return [
    tr("أحتاج مساعدة — أنا في رحلة TAXO الآن."),
    live ? tr("موقعي مباشرةً: {0}", { 0: live }) : null,
    plate ? tr("لوحة السيارة: {0}", { 0: plate }) : null,
  ]
    .filter(Boolean)
    .join("\n");
}

const LIVE = new Set(["accepted", "arrived", "in_progress", "at_stop"]);

export function useVolumeEmergency(country: CountryCode | undefined, ride: Ride | null): void {
  const on = useFeature(country, "volume_emergency");
  const contact = volumeEmergencyContact();
  const armed = on && volumeEmergencyChosen() && !!contact && !!ride && LIVE.has(ride.status);
  const rideId = armed ? ride!.id : null;
  const plate = ride?.driver?.vehicle?.plate_number ?? null;

  useEffect(() => {
    if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("VolumeTrigger")) return;
    void native.arm({ on: rideId !== null }).catch(() => undefined);
    if (rideId === null || !contact) return;
    let handle: PluginListenerHandle | null = null;
    let busy = false;
    void native
      .addListener("trigger", () => {
        if (busy) return;
        busy = true;
        void (async () => {
          // **الفريقُ أوّلاً** — ولو تعذّر الرابطُ أو الرسالة
          await pressEmergency({ app: "rider", ride_id: rideId }).catch(() => undefined);
          let live: string | null = null;
          try {
            live = trackUrl((await createTrackLink(rideId)).token);
          } catch {
            live = null;
          }
          window.location.href = `sms:${contact}?body=${encodeURIComponent(emergencyText(live, plate))}`;
        })().finally(() => {
          window.setTimeout(() => (busy = false), 10_000);
        });
      })
      .then((h) => (handle = h))
      .catch(() => undefined);
    return () => {
      void handle?.remove();
      void native.arm({ on: false }).catch(() => undefined);
    };
  }, [rideId, contact, plate]);
}
