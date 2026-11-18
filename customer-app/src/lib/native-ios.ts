/** **جسرُ iOS الأصليّ: المكالمةُ «مكالمةً حقيقيّة» (CallKit) والرحلةُ على شاشة القفل (Live Activities)** — أمرُ المالك ٢٠٢٦-١١-١٧.
 *
 * **صامتٌ في كلِّ مكانٍ إلا iOS**: أندرويد والويبُ لا يملكان الملحقين، فلا يتغيّر عليهما شيءٌ ولا يُنادى شيء
 * (`isPluginAvailable`). **والمنطقُ الخالصُ في `native-ios-logic.ts`** يُختبر بلا هاتف، وهذا الجسرُ وحدَه.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين بايتاً.**
 */
import { Capacitor, registerPlugin } from "@capacitor/core";
import { useEffect, useRef } from "react";

import { tr } from "@/lib/i18n";
import { type CallLike, nativeCallStep, type ActivityState, type RideLike, rideActivity } from "@/lib/native-ios-logic";

// ── المكالمة ────────────────────────────────────────────────────────────

interface CallKitPlugin {
  startOutgoing(options: { callId: string; name: string }): Promise<void>;
  reportConnected(options: { callId: string }): Promise<void>;
  end(options: { callId: string }): Promise<void>;
  addListener(event: "callEnded" | "callAnswered", fn: (data: { callId: string }) => void): Promise<{ remove: () => void }>;
  addListener(event: "callMuted", fn: (data: { callId: string; muted: boolean }) => void): Promise<{ remove: () => void }>;
}

const callKit = registerPlugin<CallKitPlugin>("CallKit");

function callKitReady(): boolean {
  return Capacitor.getPlatform() === "ios" && Capacitor.isPluginAvailable("CallKit");
}

/** **يُنادى مرّةً في مزوّد الاتصال** — يُعلن المكالمةَ للنظام ويُعيد إلى الويب ما ضغطه صاحبُها في واجهة النظام. */
export function useNativeCall(
  call: CallLike | null,
  peerName: string,
  actions: { hangUp: () => void; answer: () => void; toggleMute: () => void },
): void {
  const before = useRef<CallLike | null>(null);
  const latest = useRef({ call, actions });
  latest.current = { call, actions };

  useEffect(() => {
    if (!callKitReady()) return;
    const step = nativeCallStep(before.current, call);
    const id = call?.callId ?? before.current?.callId ?? null;
    before.current = call;
    if (!step || !id) return;
    const done = () => undefined;
    if (step === "start") void callKit.startOutgoing({ callId: id, name: peerName }).catch(done);
    if (step === "connected") void callKit.reportConnected({ callId: id }).catch(done);
    if (step === "end") void callKit.end({ callId: id }).catch(done);
  }, [call, peerName]);

  useEffect(() => {
    if (!callKitReady()) return;
    const handles: Array<Promise<{ remove: () => void }>> = [
      callKit.addListener("callEnded", ({ callId }) => {
        if (latest.current.call?.callId === callId) latest.current.actions.hangUp();
      }),
      callKit.addListener("callAnswered", ({ callId }) => {
        const now = latest.current.call;
        if (now?.callId === callId && now.stage === "incoming") latest.current.actions.answer();
      }),
      callKit.addListener("callMuted", ({ callId, muted }) => {
        const now = latest.current.call;
        if (now?.callId === callId && now.muted !== muted) latest.current.actions.toggleMute();
      }),
    ];
    return () => handles.forEach((handle) => void handle.then((h) => h.remove()).catch(() => undefined));
  }, []);
}

// ── النشاطُ الحيُّ للرحلة ───────────────────────────────────────────────

interface LiveActivityPlugin {
  show(options: ActivityState & { rideId: string }): Promise<{ shown: boolean }>;
  end(options: { rideId?: string }): Promise<void>;
}

const liveActivity = registerPlugin<LiveActivityPlugin>("LiveActivity");

/** **يُنادى مرّةً حيث تعيش الرحلة** — يبدأ النشاطَ ويحدّثه، وينهيه حين تنتهي أو تُلغى. */
export function useRideActivity(ride: RideLike | null, side: "rider" | "driver"): void {
  const shown = useRef<string | null>(null);
  const state = rideActivity(ride, side, tr);
  const key = state ? JSON.stringify([ride?.id, state]) : null;
  useEffect(() => {
    if (Capacitor.getPlatform() !== "ios" || !Capacitor.isPluginAvailable("LiveActivity")) return;
    if (state && ride) {
      shown.current = ride.id;
      // **الحقولُ بأسمائها لا بالنشر** — ما يُرسم على شاشة القفل يُقرأ هنا حقلاً حقلاً (`check:readers`)
      const { title, detail, plate, step } = state;
      void liveActivity.show({ rideId: ride.id, title, detail, plate, step }).catch(() => undefined);
    } else if (shown.current) {
      const rideId = shown.current;
      shown.current = null;
      void liveActivity.end({ rideId }).catch(() => undefined);
    }
    // **المفتاحُ وحدَه تبعيّة**: الرحلةُ كائنٌ جديدٌ مع كلِّ إطارٍ من المقبس، والنشاطُ لا يتحدّث إلا إن تغيّر نصُّه
  }, [key]);
}
