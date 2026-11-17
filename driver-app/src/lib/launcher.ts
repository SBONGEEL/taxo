/** **المُطلِق في تطبيق الكبتن** (SPEC §١٠٣ المرحلة A/4 البلاطة · 5 الأداة · 6 ما بعد الإقلاع · 10 الاختصارات).
 *
 * الطرفُ الأصليُّ (`LauncherPlugin.java`) **يحمل فعلاً ولا يفعله** — وهنا يُستلم **ويُنفَّذ بمسار الرئيسيّة القائم** (`toggleOnline`):
 * فحصُ الاشتراك، والأذونات، والموقع، كما هي. **ولا حسابَ مال**: نصُّ الأداة هو ما ترسمه الرئيسيّةُ من `/drivers/me/earnings` بحرفه.
 *
 * **كلُّ ميزةٍ بمفتاحها لدولته** (`quick_tile` · `home_widget` · `boot_resume` · `app_shortcuts`)، وتُكتب إلى الطرف الأصليّ
 * في كلِّ تغيّرٍ — مطفأةً تبقى البلاطةُ «غيرَ متاحة» والأداةُ «افتح التطبيق» ولا اختصار. **والغلافُ الأقدمُ لا ملحقَ فيه**: لا شيءَ يُنادى.
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";

export type LauncherAction = "go_online" | "go_offline" | "earnings" | "home";

interface NativeLauncher {
  consume(): Promise<{ action?: string | null }>;
  setShortcuts(options: { items: { id: string; label: string; action: LauncherAction }[] }): Promise<void>;
  setPrefs(options: Record<string, boolean | string | null>): Promise<void>;
  addListener(event: "action", handler: (data: { action: string }) => void): Promise<PluginListenerHandle>;
}

const native = registerPlugin<NativeLauncher>("Launcher");

export function launcherAvailable(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("Launcher");
}

const ACTIONS: ReadonlySet<string> = new Set(["go_online", "go_offline", "earnings", "home"]);

/** **فعلٌ يُنفَّذ أو لا** — ما يطلب الحالَ القائمةَ يُتجاهل (`go_online` وهو متّصل)، والمجهولُ يُتجاهل. خالصٌ ومختبَر. */
export function resolveAction(raw: string | null | undefined, online: boolean): LauncherAction | null {
  if (!raw || !ACTIONS.has(raw)) return null;
  if (raw === "go_online" && online) return null;
  if (raw === "go_offline" && !online) return null;
  return raw as LauncherAction;
}

interface Options {
  country: CountryCode | undefined;
  online: boolean;
  /** نصُّ «أرباح اليوم» كما يُرسم في الرئيسيّة، و`null` حتى يصل */
  earningsText: string | null;
  ridesToday: number | null;
  onAction: (action: LauncherAction) => void;
}

export function useDriverLauncher({ country, online, earningsText, ridesToday, onAction }: Options): void {
  const tile = useFeature(country, "quick_tile");
  const widget = useFeature(country, "home_widget");
  const boot = useFeature(country, "boot_resume");
  const shortcuts = useFeature(country, "app_shortcuts");
  // **فقاعةُ الحال والموقعُ الأصليّ** (§١٠٣ A/1 وA/3) — مفتاحان يقرؤهما الطرفُ الأصليُّ وحدَه
  const bubble = useFeature(country, "status_bubble");
  const nativeLocation = useFeature(country, "native_location");
  const latest = useRef({ online, onAction });
  latest.current = { online, onAction };

  // **الفعلُ القادم** — من إقلاعٍ بارد (`consume`) أو والتطبيقُ حيّ (حدثُ `action`)
  useEffect(() => {
    if (!launcherAvailable()) return;
    const run = (raw: string | null | undefined) => {
      const action = resolveAction(raw, latest.current.online);
      if (action) latest.current.onAction(action);
    };
    void native.consume().then((answer) => run(answer.action)).catch(() => undefined);
    let handle: PluginListenerHandle | null = null;
    void native.addListener("action", (data) => run(data.action)).then((h) => (handle = h))
      .catch(() => undefined);
    return () => void handle?.remove();
  }, []);

  // **ما يقرؤه الطرفُ الأصليّ** — المفاتيحُ والحالُ ونصُّ الأداة
  useEffect(() => {
    if (!launcherAvailable()) return;
    void native
      .setPrefs({
        tile,
        widget,
        boot,
        status_bubble: bubble,
        native_location: nativeLocation,
        online,
        widget_earnings: widget ? earningsText : null,
        widget_rides: widget && ridesToday !== null ? tr("رحلات اليوم: {0}", { 0: ridesToday }) : null,
      })
      .catch(() => undefined);
  }, [tile, widget, boot, bubble, nativeLocation, online, earningsText, ridesToday]);

  useEffect(() => {
    if (!launcherAvailable()) return;
    const items = shortcuts
      ? [
          { id: "go_online", label: tr("اتصل الآن"), action: "go_online" as const },
          { id: "earnings", label: tr("أرباحي"), action: "earnings" as const },
        ]
      : [];
    void native.setShortcuts({ items }).catch(() => undefined);
  }, [shortcuts]);
}
