/** **المُطلِق في تطبيق الراكب** (SPEC §١٠٣ المرحلة A/10) — اختصارا الأيقونة «اطلب رحلة إلى البيت» و«محفظتي»، خلف `app_shortcuts`.
 *
 * الطرفُ الأصليُّ (`LauncherPlugin.java`، منسوخٌ بايتاً من الكبتن) **يحمل الفعلَ ولا يفعله** — وهنا يُنفَّذ بمسار الرئيسيّة القائم:
 * «البيت» يمرّ بـ`pickPlace` نفسِه الذي يمرّ به لمسُ المكان المحفوظ (فالسعرُ والطلبُ من الخلفيّة كما هما)، **ولا بيتَ محفوظاً ⇐
 * «أماكني» ليضيفه** — لا رحلةَ تُخترع وجهتُها. والغلافُ الأقدمُ لا ملحقَ فيه: لا شيءَ يُنادى.
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { routeCommsPush } from "@/lib/trip-comms";

export type RiderAction = "ride_home" | "wallet";

interface NativeLauncher {
  consume(): Promise<{ action?: string | null }>;
  setShortcuts(options: { items: { id: string; label: string; action: RiderAction }[] }): Promise<void>;
  addListener(event: "action", handler: (data: { action: string }) => void): Promise<PluginListenerHandle>;
}

const native = registerPlugin<NativeLauncher>("Launcher");

export function launcherAvailable(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("Launcher");
}

/** خالصٌ ومختبَر — المجهولُ يُتجاهل */
/** **زرّا إشعار الكبتن الغنيّ** (§١٠٣/12، `RideNotice.java`): `ride_call:<رحلة>` و`ride_chat:<رحلة>` — يمرّان بباب الإشعارات
 *  القائم (`routeCommsPush`) كنقرةٍ على إشعار محادثة، **فالطبقةُ وحدَها تقرّر** وتحفظهما في الإقلاع البارد. */
export function rideCommsAction(raw: string | null | undefined): { type: string; ride_id: string } | null {
  const match = /^ride_(call|chat):([0-9a-fA-F-]{8,64})$/.exec(raw ?? "");
  if (!match) return null;
  return { type: match[1] === "call" ? "start_call" : "chat_message", ride_id: match[2] };
}

export function riderAction(raw: string | null | undefined): RiderAction | null {
  return raw === "ride_home" || raw === "wallet" ? raw : null;
}

export function useRiderLauncher(country: CountryCode | undefined, onAction: (action: RiderAction) => void): void {
  const shortcuts = useFeature(country, "app_shortcuts");
  const latest = useRef(onAction);
  latest.current = onAction;

  useEffect(() => {
    if (!launcherAvailable()) return;
    const run = (raw: string | null | undefined) => {
      const comms = rideCommsAction(raw);
      if (comms) {
        routeCommsPush(comms, "tap");
        return;
      }
      const action = riderAction(raw);
      if (action) latest.current(action);
    };
    void native.consume().then((answer) => run(answer.action)).catch(() => undefined);
    let handle: PluginListenerHandle | null = null;
    void native.addListener("action", (data) => run(data.action)).then((h) => (handle = h))
      .catch(() => undefined);
    return () => void handle?.remove();
  }, []);

  useEffect(() => {
    if (!launcherAvailable()) return;
    const items = shortcuts
      ? [
          { id: "ride_home", label: tr("اطلب رحلة إلى البيت"), action: "ride_home" as const },
          { id: "wallet", label: tr("محفظتي"), action: "wallet" as const },
        ]
      : [];
    void native.setShortcuts({ items }).catch(() => undefined);
  }, [shortcuts]);
}
