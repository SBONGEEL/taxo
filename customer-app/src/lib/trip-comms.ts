/** **أحداثُ محادثة الرحلة ومكالمتها على المقبس القائم** (SPEC §٦٦، `TripCommsEvent` في `ws/events.py`).
 *
 * **لا مقبسَ ثانٍ**: المقبسُ الواحدُ في `lib/ride.tsx` يستقبلها مع أحداث الرحلة ويمرّرها هنا (`dispatchTripComms`)، **وطبقةُ
 * المحادثة والمكالمة** (`lib/comms.tsx`) تُصغي (`onTripComms`). **وجسرٌ لا حالة**: هذا الملفُّ لا يحفظ شيئاً — فلا يفترق ما
 * يعرفه عمّا تعرفه الطبقة.
 *
 * **والحمولاتُ معرّفاتٌ وجوانبُ وقيمٌ خام** — لا رقمَ ولا اسم (§٦٦-د/٢). **ونقرةُ الإشعار ووصولُه والتطبيقُ مفتوح** يمرّان
 * من بابٍ ثانٍ هنا (`routeCommsPush`) لأن الإشعارَ لا يصل من المقبس — **والطبقةُ هي التي تقرّر**: محادثةٌ تُفتح، أو مكالمةٌ
 * ترنّ إن كانت ترنّ بعدُ، أو «مكالمةٌ فائتة».
 *
 * **ونسخةٌ واحدةٌ في التطبيقين حرفاً** (`customer-app` و`driver-app`) — كالعقد الذي تقرؤه.
 */

import type { CommsSide } from "@/api/types";

/** أنواعُ الأحداث الستّة — مرآةُ `TripCommsEvent`. */
const TRIP_COMMS_TYPES: ReadonlySet<string> = new Set([
  "chat_message",
  "chat_read",
  "incoming_call",
  "call_answered",
  "call_ended",
  "call_signal",
]);

/** رسالةٌ كما تصل على المقبس — **بلا `mine`**: الجانبُ يقول من أرسلها. */
export interface WireChatMessage {
  id: string;
  sender_role: CommsSide;
  body: string;
  created_at: string;
  read_at: string | null;
}

/** حالُ المكالمة على المقبس (`ride_calls.call_payload`) — **بلا `caller_role`** وإن حمله: الطرفان اثنان، فالمتصلُ عند المتصَل به
 *  هو الطرفُ الآخر دائماً، وحقلٌ يُقرأ ولا يقرّر شيئاً لا يُنسخ هنا (`check:readers`). */
export interface WireCall {
  ride_id: string;
  call_id: string;
  status: "ringing" | "active" | "ended";
  end_reason: "completed" | "declined" | "no_answer" | "failed" | "ride_ended" | "cancelled" | null;
  recording: boolean;
  ring_timeout_seconds?: number;
}

export type TripCommsEvent =
  | { type: "chat_message"; ride_id: string; message: WireChatMessage }
  | { type: "chat_read"; ride_id: string; read_at: string }
  | ({ type: "incoming_call" | "call_answered" | "call_ended" } & WireCall)
  | {
      type: "call_signal";
      ride_id: string;
      call_id: string;
      from_role: CommsSide;
      kind: "offer" | "answer" | "ice";
      payload: Record<string, unknown>;
    };

/** **أهذا حدثُ محادثةٍ أو مكالمة؟** — يسأله `lib/ride.tsx` قبل أن يمرّره. */
export function isTripCommsEvent(event: { type: string }): event is TripCommsEvent {
  return TRIP_COMMS_TYPES.has(event.type);
}

const listeners = new Set<(event: TripCommsEvent) => void>();

/** يمرّر حدثاً من المقبس إلى طبقة المحادثة والمكالمة. */
export function dispatchTripComms(event: TripCommsEvent): void {
  for (const listener of listeners) listener(event);
}

/** يُصغي إلى الأحداث — ويعيد ما يفكّ الإصغاء. */
export function onTripComms(listener: (event: TripCommsEvent) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// ─────────────────────────────── الإشعار: نقرتُه، ووصولُه والتطبيقُ مفتوح

/** **أنواعُ الإشعار التي تخصّ الطبقة** — **ولا `missed_call`**: إشعارٌ عاديٌّ يبقى في الصندوق ويُرسم بلاغاً كأيِّ إشعار
 *  (`notifications.publish_missed_call`)، ونقرتُه تفتح الرحلةَ كصفّه في الوارد. */
const PUSH_TYPES: ReadonlySet<string> = new Set(["chat_message", "incoming_call"]);

type PushRoute = (data: Record<string, string>, how: "tap" | "received") => boolean;

let pushRoute: PushRoute | null = null;
/** **ما وصل قبل أن تُركَّب الطبقة** — الإقلاعُ البارد يسلّم النقرةَ مبكراً، فتُحفظ ولا تضيع. */
let early: { data: Record<string, string>; how: "tap" | "received" } | null = null;

/** تُسجّلها الطبقةُ حين تُركَّب — **ونقرةٌ سبقتها تُسلَّم لها فوراً**. */
export function setCommsPushRoute(route: PushRoute | null): void {
  pushRoute = route;
  if (route && early) {
    const pending = early;
    early = null;
    route(pending.data, pending.how);
  }
}

/** **أيخصّ هذا الإشعارُ المحادثةَ أو المكالمة؟** — وإن خصّها قرّرت الطبقةُ ما يُفعل، **ويعيد `true` فلا يُعالَج مرّتين**:
 *  لا وجهةَ عامّةٌ تُفتح فوقه، ولا بلاغٌ يُرسم معه. */
export function routeCommsPush(data: Record<string, string> | undefined, how: "tap" | "received"): boolean {
  if (!data?.type || !PUSH_TYPES.has(data.type) || !data.ride_id) return false;
  if (pushRoute) return pushRoute(data, how);
  if (how === "tap") {
    early = { data, how };
    return true;
  }
  return false;
}
