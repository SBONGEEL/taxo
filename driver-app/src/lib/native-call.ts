/** **مكالمةُ الرحلة عند نظام أندرويد** (SPEC §١٠٣ B/27، خلف `native_call_ui`) — `TaxoConnectionService.java` و`CallBridgePlugin.java`.
 *
 * يقول للنظام «تبدأ · ترنّ · جارية · انتهت» فيوجّه الصوتَ إلى البلوتوث والسيّارة، ويُرجع أزرارَها إلى أفعال المكالمة القائمة
 * (`answer` · `decline` · `hangUp`) — **فالحالُ واحدةٌ في الويب، والنظامُ صدىً لها**. ومطفأً أو بلا إضافةٍ لا شيءَ يتغيّر.
 * **نسخةُ التطبيق الآخر حرفاً.**
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";

import { useFeature } from "@/lib/config";
import { bridgeStep } from "@/lib/native-call-core";
import type { CountryCode } from "@/api/types";

interface CallBridge {
  startOutgoing(options: { name: string }): Promise<{ placed: boolean }>;
  reportIncoming(options: { name: string }): Promise<{ placed: boolean }>;
  setActive(): Promise<void>;
  end(options: { reason: string }): Promise<void>;
  addListener(
    event: "callAction",
    listener: (event: { action: "answer" | "reject" | "hangup" | "failed" }) => void,
  ): Promise<PluginListenerHandle>;
}

const bridge = registerPlugin<CallBridge>("CallBridge");

export function useNativeCallBridge(
  country: CountryCode | undefined,
  call: { stage: string; outgoing: boolean } | null,
  actions: { answer: () => void; decline: () => void; hangUp: () => void },
  name: string,
): void {
  const flag = useFeature(country, "native_call_ui");
  const on = flag && Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("CallBridge");
  const started = useRef(false);
  const prev = useRef<string | null>(null);
  const latest = useRef(actions);
  latest.current = actions;

  useEffect(() => {
    if (!on) return;
    let handle: PluginListenerHandle | null = null;
    let gone = false;
    void bridge
      .addListener("callAction", (event) => {
        if (event.action === "answer") latest.current.answer();
        else if (event.action === "reject") latest.current.decline();
        else if (event.action === "hangup") latest.current.hangUp();
        // «failed»: النظامُ رفض (مكالمةُ شريحةٍ جارية) — الويبُ يمضي وحدَه
        else started.current = false;
      })
      .then((value) => {
        if (gone) void value.remove();
        else handle = value;
      })
      .catch(() => undefined);
    return () => {
      gone = true;
      void handle?.remove();
      if (started.current) void bridge.end({ reason: "local" }).catch(() => undefined);
      started.current = false;
    };
  }, [on]);

  const stage = call?.stage ?? null;
  const outgoing = call?.outgoing ?? false;
  useEffect(() => {
    const before = prev.current;
    prev.current = stage;
    if (!on) return;
    const step = bridgeStep(started.current, before, stage, outgoing);
    if (!step) return;
    if (step.kind === "outgoing" || step.kind === "incoming") {
      started.current = true;
      const place = step.kind === "outgoing" ? bridge.startOutgoing({ name }) : bridge.reportIncoming({ name });
      void place
        .then((answer) => {
          if (!answer.placed) started.current = false;
        })
        .catch(() => {
          started.current = false;
        });
    } else if (step.kind === "active") {
      void bridge.setActive().catch(() => undefined);
    } else {
      started.current = false;
      void bridge.end({ reason: step.reason }).catch(() => undefined);
    }
    // الاسمُ يُقرأ عند البدء وحدَه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, stage, outgoing]);
}
