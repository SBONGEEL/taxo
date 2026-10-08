/** **طبقةُ المحادثة والمكالمة داخل الرحلة** (SPEC §٦٦) — فوق الشاشات لا داخل واحدة: المكالمةُ ترنّ والراكبُ أو الكبتنُ في أيِّ
 * شاشة، والمحادثةُ تُفتح من ورقة الرحلة ومن نقرة إشعار.
 *
 * **ما تملكه هنا** — والرسمُ كلُّه في `screens/t2/CommsT2.tsx`:
 *
 * - **متى يُرسم الزرّان** (`canMessage` · `canCall`): من قبول الكبتن حتى تنتهي الرحلةُ أو تُلغى (§٦٦-أ/١). **و`open`/`can_call`
 *   من الخادم حكمٌ** متى عُرفا؛ **وقبلهما المفتاحُ من `GET /config` وحالُ الرحلة — القاعدةُ نفسُها التي يحكم بها الخادم**: فتحُ
 *   المحادثة (`GET /rides/{id}/chat`) **يعلّم رسائلَ الطرف الآخر مقروءةً ويُخبره**، فطلبُه لرسم زرٍّ يُري الطرفَ الآخر «قُرئت» عن
 *   رسالةٍ لم يرها أحد. فلا يُطلب إلا والورقةُ تُفتح.
 * - **شارةُ ما لم يُقرأ** — تُعدّ من المقبس والورقةُ مغلقة، وتُصفَّر حين تُفتح.
 * - **المكالمةُ بحالاتها**: صادرةٌ (جارٍ الاتصال · تنبيهُ التسجيل · يرنّ) · واردةٌ · تتّصل · جارية · تعذّرت · لم يُجب · انتهت
 *   الرحلة · انتهت. **والاتصالُ نفسُه في `lib/call-session.ts`**.
 * - **والأصواتُ من `lib/sound.ts`** تحت مفاتيحها القائمة: رنينُ الوارد حلقةٌ (`callRing`)، و«يرنّ» نغمةٌ قصيرة (`callDial`)،
 *   والانتهاءُ (`callEnd`)، والتعذّرُ (`error`)، **ورسالةٌ والمحادثةُ مغلقة** (`notify` — يعزفه بلاغُ التطبيق الذي يقولها، `toast`).
 *
 * **والأحداثُ من المقبس القائم** (`lib/trip-comms.ts`) **ومن الإشعار** (`routeCommsPush`) — ولا مقبسَ ثانٍ.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين حرفاً**: ما يفترق (الجانب، ومن هو الطرفُ الآخر، وأين يُقال البلاغ، وهل المقبسُ حيّ) يصل خصائص.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import {
  ackRecordingNotice,
  answerRideCall,
  declineRideCall,
  endRideCall,
  getRideCall,
  getTripChat,
  reportTripChat,
  sendTripChat,
  startRideCall,
  uploadCallRecording,
} from "@/api/endpoints";
import type { CallStart, ChatMessage, ChatReportReason, ChatThread, CommsSide, IceServer, Ride } from "@/api/types";
import { CallSession, speakerOutput } from "@/lib/call-session";
import { useFeature } from "@/lib/config";
import { useCallsSupported } from "@/lib/mic-gate";
import { loop, play } from "@/lib/sound";
import { onTripComms, setCommsPushRoute, type TripCommsEvent } from "@/lib/trip-comms";

/** **نافذةُ المحادثة والمكالمة** — مرآةُ `trip_chat.CHAT_WINDOW` (`ACTIVE_DRIVER_STATUSES`): من القبول حتى الانتهاء. */
const WINDOW: ReadonlySet<string> = new Set(["accepted", "arrived", "in_progress", "at_stop"]);

export function inCommsWindow(ride: Pick<Ride, "status"> | null): boolean {
  return ride !== null && WINDOW.has(ride.status);
}

/** **من الطرفُ الآخر** كما يُرسم في رأس المحادثة والمكالمة — عند الراكب اسمُ الكبتن ومركبتُه ولوحتُها، **وعند الكبتن «الراكب»
 *  وحدَه** (§٦١-ز: لا يرى الكبتنُ اسمَ الراكب). */
export interface CommsPeer {
  name: string;
  meta: string | null;
  plate: string | null;
  avatar: ReactNode;
}

/** أطوارُ المكالمة كما تُرسم. */
type CallStage =
  | "preparing"
  | "consent"
  | "dialing"
  | "incoming"
  | "joining"
  | "talking"
  | "broken"
  | "unanswered"
  | "tripover"
  | "hungup";

const OVER: ReadonlySet<CallStage> = new Set<CallStage>(["broken", "unanswered", "tripover", "hungup"]);

export interface CallView {
  stage: CallStage;
  rideId: string;
  callId: string | null;
  /** **أنا المتصل؟** — يقرّر أيَّ رأسٍ يُقال وأيَّ زرٍّ يُرسم */
  outgoing: boolean;
  /** **أعلنها الخادمُ مسجَّلة** — فالتنبيهُ قبل الرنين والشارةُ أثناءها */
  recording: boolean;
  /** لحظةُ وصول الصوت — منها تعدّ المدّة */
  since: number | null;
  muted: boolean;
  speaker: boolean;
  /** **أيختار المتصفّحُ المخرجَ هنا؟** — وإلا لا زرَّ مكبّر */
  speakerReady: boolean;
  minimized: boolean;
  /** الشبكةُ ضعُفت أثناءها — سطرٌ لا فشل */
  weak: boolean;
  /** «انتهت المكالمة · 02:13» — كم دامت */
  lasted: number | null;
  /** نصُّ الخادم أو الجهاز حين يتعذّر البدء (لا إذنَ للميكروفون، مكالمةٌ جارية…) */
  reason: string | null;
}

export interface ChatView {
  rideId: string;
  thread: ChatThread | null;
  error: string | null;
  /** **في نافذة الرحلة؟** — يفرّق «انتهت الرحلة» عن «غيرُ متاحة» حين لا يُكتب فيها */
  live: boolean;
}

interface CommsState {
  side: CommsSide;
  peer: CommsPeer | null;
  /** «الكبتن» أو «الراكب» — الطرفُ الآخر بكلمة */
  peerRole: string;
  canMessage: boolean;
  canCall: boolean;
  unread: number;
  chat: ChatView | null;
  call: CallView | null;
  openChat: (rideId?: string) => void;
  closeChat: () => void;
  send: (text: string) => Promise<string | null>;
  report: (messageId: string, reason: ChatReportReason, note: string) => Promise<string | null>;
  startCall: () => void;
  consent: (go: boolean) => void;
  answer: () => void;
  decline: () => void;
  hangUp: () => void;
  toggleMute: () => void;
  toggleSpeaker: () => void;
  minimize: (minimized: boolean) => void;
  dismissCall: () => void;
  retry: () => void;
  messageInstead: () => void;
}

const CommsContext = createContext<CommsState | null>(null);

export function useComms(): CommsState | null {
  return useContext(CommsContext);
}

/** نصُّ الخطأ — **عربيةُ الخادم كما هي** (عقدُ الأخطاء)، أو جملةُ الطبقة حين لم يصل ردّ. */
function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/** **صوتٌ لا يتجاوز المسموح** — طلبُ الميكروفون، **ورفضُه يُقال بسببه** لا «تعذّر الاتصال». */
async function microphone(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({ audio: true, video: false });
}

const MIC_REFUSED = "لا إذنَ للميكروفون — اسمح به من إعدادات الهاتف ثمّ أعد المحاولة.";

/** **كم يُنتظر المقبسُ لرنينٍ وصل من إشعار** — الإقلاعُ البارد يفتحه في ثوانٍ؛ وبعدها لا يُرنّ هنا: «ردّ» بلا مقبسٍ لا تصله إشارة. */
const LIVE_WAIT_MS = 10_000;

/** **رفعُ التسجيل** — بعد أن يُكتب انتهاؤها عند الخادم (`_require_recordable` يشترط `ended`)، **ومرّةً ثانيةً إن رُفض**: إنهاءٌ
 *  ضاع في الشبكة يُعاد (لا يكتب شيئاً على منتهية) ثمّ يُرفع. **وكان يُفقد** (قِيس ٢٠٢٦-١٠-٠٨): «إنهاء» يرسل الإنهاءَ ولا ينتظره،
 *  والرفعُ يخرج حين يقف المسجِّل — فيصل قبل أن يلتزم الإنهاء، فيُردّ `call_recording_refused` ويُرمى الملفّ. */
async function uploadRecording(callId: string, blob: Blob): Promise<void> {
  try {
    await uploadCallRecording(callId, blob);
    return;
  } catch (caught) {
    if (!(caught instanceof ApiError && caught.code === "call_recording_refused")) {
      console.warn("[call] تعذّر رفع التسجيل", caught);
      return;
    }
  }
  await endRideCall(callId).catch(() => undefined);
  await uploadCallRecording(callId, blob).catch((caught: unknown) => console.warn("[call] تعذّر رفع التسجيل", caught));
}

export function CommsProvider({
  side,
  ride,
  peer,
  live,
  toast,
  children,
}: {
  side: CommsSide;
  /** الرحلةُ الجاريةُ أو المعروضة — من `useRide` */
  ride: Ride | null;
  peer: CommsPeer | null;
  /** **المقبسُ حيّ** — الإشارةُ تصل منه وحدَه: بلاه لا مكالمة، **والمحادثةُ المفتوحةُ تُسأل كلَّ خمس ثوانٍ** بدله */
  live: boolean;
  /** بلاغٌ صغيرٌ بصوته — بلاغُ التطبيق القائم */
  toast: (title: string, body?: string) => void;
  children: ReactNode;
}) {
  const peerRole = side === "rider" ? "الكبتن" : "الراكب";
  /** **«مكالمةٌ فائتة» بنصِّ إشعار الخادم حرفاً** (`MISSED_CALL_TITLE` · `MISSED_CALL_BODY`) — فبلاغُه على المقبس، إن وصل بعدها،
   *  يُطوى معها (`firstSighting`) ولا يُرسم مرّتين. */
  const missed = useCallback(
    () => toast(`مكالمةٌ فائتة من ${peerRole}`, "افتح الرحلة لتعاود الاتصال أو تراسل"),
    [peerRole, toast],
  );
  const chatFlag = useFeature(ride?.country_code, "trip_chat_enabled");
  const callFlag = useFeature(ride?.country_code, "ride_calls_enabled");
  const micReady = useCallsSupported();

  const [chat, setChatState] = useState<ChatView | null>(null);
  const chatRef = useRef<ChatView | null>(null);
  const setChat = useCallback((next: ChatView | null) => {
    chatRef.current = next;
    setChatState(next);
  }, []);

  const [call, setCallState] = useState<CallView | null>(null);
  const callRef = useRef<CallView | null>(null);
  const setCall = useCallback((next: CallView | null) => {
    callRef.current = next;
    setCallState(next);
  }, []);
  const patchCall = useCallback(
    (patch: Partial<CallView>) => {
      if (callRef.current) setCall({ ...callRef.current, ...patch });
    },
    [setCall],
  );

  const [unread, setUnread] = useState(0);
  /** **حكمُ الخادم متى عُرف** لهذه الرحلة — `open` و`can_call` من آخر فتح */
  const [known, setKnown] = useState<{ rideId: string; open: boolean; can_call: boolean } | null>(null);

  const rideRef = useRef<Ride | null>(ride);
  rideRef.current = ride;
  const sessionRef = useRef<CallSession | null>(null);
  /** ما يعيش مع المكالمة ولا يُرسم: مؤقّتاتُها ونغماتُها وما ينتظرها */
  const extras = useRef<{
    stopRing: (() => void) | null;
    ringTimer: number | null;
    closeTimer: number | null;
    pending: { started: CallStart; local: MediaStream } | null;
    answered: boolean;
    talked: boolean;
    /** **إنهاؤها عند الخادم وهو في الطريق** — رفعُ التسجيل ينتظره */
    ending: Promise<void> | null;
  }>({ stopRing: null, ringTimer: null, closeTimer: null, pending: null, answered: false, talked: false, ending: null });
  /** **رقمُ محاولة الاتصال** — «إنهاء» أثناء سؤال الميكروفون أو أثناء البدء يُبطلها، فلا تُكمل وحدَها بعده */
  const attempts = useRef(0);
  /** **رنينٌ وصل من إشعارٍ والمقبسُ مغلق** — يُحفظ حتى يُفتح، أو تنقضي مهلتُه */
  const heldRing = useRef<{ callId: string; rideId: string; how: "tap" | "received"; timer: number } | null>(null);
  /** **إشاراتٌ سبقت أصحابَها** — العرضُ يصل المتصَلَ به وهو يرنّ، ومرشّحون قبل الوصف */
  const signals = useRef(new Map<string, { offer: Record<string, unknown> | null; ice: Record<string, unknown>[] }>());

  const currentId = ride?.id ?? null;
  const windowOpen = inCommsWindow(ride);
  const verdict = known && known.rideId === currentId ? known : null;
  const canMessage = windowOpen && (verdict ? verdict.open : chatFlag);
  // **والمكالمةُ تحتاج المقبسَ حيّاً** — الإشارةُ تصل منه وحدَه، فزرٌّ بلاه يَعِد بمكالمةٍ لا تكتمل
  const canCall = windowOpen && live && micReady && (verdict ? verdict.can_call : callFlag);
  // **ومن يبدأ مكالمةً أو يرنّ من إشعارٍ يسأل الحالَ الآن** لا حالَ آخرِ رسم — «أعد المحاولة» تُضغط بعد أن سقط المقبس
  const canCallRef = useRef(canCall);
  canCallRef.current = canCall;
  const liveRef = useRef(live);
  liveRef.current = live;

  // ── رحلةٌ جديدة: لا شارةَ قديمة
  useEffect(() => {
    setUnread(0);
  }, [currentId]);

  /** **رسالةٌ وصلت والمحادثةُ مغلقة** (§٤/١ «تنبيهٌ صغير») — **ببلاغ التطبيق نفسِه لا بطبقةٍ ثانية**: قِيس في تجربة المتصفّحين أنّ
   *  تنبيهاً مستقلّاً أعلى الشاشة **يقع فوق بلاغ «مكالمةٌ فائتة» نفسِه** فيُقرآن معاً. وبلاغُ التطبيق يرصّها عموداً، ويعزف «الإشعار»
   *  تحت مفتاحه، ولا يكرّر ما رُسم في ثوانيه العشر. **والشارةُ على «رسالة» هي ما يبقى** حتى تُفتح. */
  const alertMessage = useCallback(
    (body: string | null) => {
      setUnread((count) => count + 1);
      toast(`رسالةٌ جديدة من ${peerRole}`, body ?? "افتح المحادثة لقراءتها");
    },
    [peerRole, toast],
  );

  // ─────────────────────────────── المحادثة

  const load = useCallback(
    async (rideId: string) => {
      try {
        const thread = await getTripChat(rideId);
        setKnown({ rideId, open: thread.open, can_call: thread.can_call });
        const open = chatRef.current;
        if (open && open.rideId === rideId) setChat({ ...open, thread, error: null });
      } catch (caught) {
        const open = chatRef.current;
        if (open && open.rideId === rideId && !open.thread) {
          setChat({ ...open, error: messageOf(caught, "تعذّر فتح المحادثة — تحقّق من الاتصال.") });
        }
      }
    },
    [setChat],
  );

  const openChat = useCallback(
    (rideId?: string) => {
      const id = rideId ?? rideRef.current?.id;
      if (!id) return;
      const current = rideRef.current;
      setChat({ rideId: id, thread: null, error: null, live: current?.id === id && inCommsWindow(current) });
      if (current?.id === id) setUnread(0);
      // **والمكالمةُ الجاريةُ تصغر شريطاً ولا تنقطع** (§٦٦ «رسالة» أثناء المكالمة)
      if (callRef.current && !OVER.has(callRef.current.stage)) patchCall({ minimized: true });
      void load(id);
    },
    [load, patchCall, setChat],
  );

  const closeChat = useCallback(() => setChat(null), [setChat]);

  // **والرحلةُ تنتهي والورقةُ مفتوحة**: تبقى مقروءةً ويحلّ سطرُ الإغلاق محلَّ حقل الكتابة
  useEffect(() => {
    const open = chatRef.current;
    if (!open || open.rideId !== currentId) return;
    if (open.live !== windowOpen) {
      setChat({
        ...open,
        live: windowOpen,
        thread: open.thread && !windowOpen ? { ...open.thread, open: false, can_call: false } : open.thread,
      });
    }
  }, [currentId, windowOpen, setChat]);

  // **بلا مقبسٍ حيٍّ تُسأل المحادثةُ المفتوحةُ كلَّ خمس ثوانٍ** — والفتحُ يعلّمها مقروءةً، **فلا يُسأل والتطبيقُ في الخلفية**:
  // الورقةُ مفتوحةٌ ولا أحدَ أمامها، وكلُّ سؤالٍ كان يُري الطرفَ الآخر «قُرئت» (قِيس ٢٠٢٦-١٠-٠٨)
  const chatId = chat?.rideId ?? null;
  useEffect(() => {
    if (!chatId || live) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void load(chatId);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [chatId, live, load]);

  // **والعودةُ إلى التطبيق تعلّم ما وصل في غيابه** — الآن وهي أمام صاحبها
  useEffect(() => {
    if (!chatId) return;
    const onVisibility = () => {
      if (!document.hidden) void load(chatId);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [chatId, load]);

  /** **رسالةٌ من الطرف الآخر والورقةُ مفتوحة** — تُعلَّم مقروءةً بفتحٍ ثانٍ (الخادمُ يُخبره «قُرئت»)، **مؤجَّلاً لحظةً** فلا تصير
   *  رسائلُ متتابعةٌ فتحاتٍ متتابعة. **والتطبيقُ في الخلفية لا يقرأ**: تُعلَّم حين يعود (`visibilitychange` أعلاه). */
  const readSoon = useRef<number | null>(null);
  const markReadSoon = useCallback(
    (rideId: string) => {
      if (readSoon.current !== null) window.clearTimeout(readSoon.current);
      readSoon.current = window.setTimeout(() => {
        readSoon.current = null;
        if (document.hidden) return;
        void load(rideId);
      }, 600);
    },
    [load],
  );

  const send = useCallback(
    async (text: string): Promise<string | null> => {
      const open = chatRef.current;
      const body = text.trim();
      if (!open || !body) return null;
      try {
        const message = await sendTripChat(open.rideId, body);
        const now = chatRef.current;
        if (now && now.rideId === open.rideId && now.thread && !now.thread.messages.some((m) => m.id === message.id)) {
          setChat({ ...now, thread: { ...now.thread, messages: [...now.thread.messages, message] } });
        }
        return null;
      } catch (caught) {
        // **«انتهت الرحلة، وأُغلقت المحادثة.»** — لا خطأٌ تحت الحقل بل سطرٌ مكانه، والرسائلُ مقروءة
        if (caught instanceof ApiError && caught.code === "chat_closed") {
          const now = chatRef.current;
          if (now?.thread) setChat({ ...now, live: false, thread: { ...now.thread, open: false, can_call: false } });
          setKnown({ rideId: open.rideId, open: false, can_call: false });
          return null;
        }
        return messageOf(caught, "تعذّر الإرسال — تحقّق من الاتصال وأعد المحاولة.");
      }
    },
    [setChat],
  );

  const report = useCallback(
    async (messageId: string, reason: ChatReportReason, note: string): Promise<string | null> => {
      const open = chatRef.current;
      if (!open) return null;
      try {
        await reportTripChat(open.rideId, messageId, reason, note.trim() ? note.trim() : null);
        return null;
      } catch (caught) {
        return messageOf(caught, "تعذّر إرسال البلاغ — أعد المحاولة.");
      }
    },
    [],
  );

  // ─────────────────────────────── المكالمة

  const clearTimers = useCallback(() => {
    const bag = extras.current;
    bag.stopRing?.();
    bag.stopRing = null;
    if (bag.ringTimer !== null) window.clearTimeout(bag.ringTimer);
    bag.ringTimer = null;
    if (bag.closeTimer !== null) window.clearTimeout(bag.closeTimer);
    bag.closeTimer = null;
  }, []);

  /** **إنهاؤها عند الخادم — ووعدُه محفوظ**: رفعُ التسجيل في `teardown` ينتظره، فلا يسبق إنهاءً لم يلتزم بعد. */
  const endOnServer = useCallback((callId: string) => {
    extras.current.ending = endRideCall(callId).then(
      () => undefined,
      () => undefined,
    );
  }, []);

  /** **يُغلق الاتصالَ ويرفع التسجيلَ إن وُجد** — المتصلُ وحدَه يرفع، وبعد المكالمة لا أثناءها (§٦٦-د/٣)، **وبعد أن يُكتب انتهاؤها
   *  عند الخادم** (`endOnServer` → `uploadRecording`). والميكروفونُ يُغلق فوراً — لا ينتظر شبكة. */
  const teardown = useCallback(() => {
    const session = sessionRef.current;
    sessionRef.current = null;
    const pending = extras.current.pending;
    extras.current.pending = null;
    const ending = extras.current.ending ?? Promise.resolve();
    extras.current.ending = null;
    pending?.local.getTracks().forEach((track) => track.stop());
    if (!session) return;
    const view = callRef.current;
    const upload = view?.outgoing && view.recording && view.callId ? view.callId : null;
    void session.stopRecording().then(async (blob) => {
      session.close();
      if (!blob || !upload) return;
      await ending;
      await uploadRecording(upload, blob);
    });
  }, []);

  /** **تنتهي المكالمةُ إلى طورٍ يُقال** — والطورُ المنتهي يبقى على الشاشة حتى يُغلق، **إلا «انتهت المكالمة» فلحظةٌ ثمّ تعود**. */
  const finish = useCallback(
    (stage: CallStage, reason: string | null = null) => {
      const view = callRef.current;
      if (!view || OVER.has(view.stage)) return;
      clearTimers();
      teardown();
      const lasted = view.since !== null ? Math.max(0, Math.round((Date.now() - view.since) / 1000)) : null;
      setCall({ ...view, stage, reason, lasted, minimized: false, weak: false });
      play(stage === "hungup" || stage === "tripover" ? "callEnd" : "error");
      if (stage === "hungup") {
        extras.current.closeTimer = window.setTimeout(() => setCall(null), 1_800);
      }
    },
    [clearTimers, setCall, teardown],
  );

  const sessionEvents = useCallback(
    () => ({
      connected: () => {
        const view = callRef.current;
        if (!view || OVER.has(view.stage)) return;
        extras.current.talked = true;
        patchCall({ stage: "talking", since: Date.now() });
        if (view.outgoing && view.recording) sessionRef.current?.startRecording();
        void speakerOutput().then((device) => patchCall({ speakerReady: device !== null }));
      },
      weak: (weak: boolean) => patchCall({ weak }),
      broken: () => {
        const id = callRef.current?.callId;
        if (id) endOnServer(id);
        finish("broken");
      },
    }),
    [endOnServer, finish, patchCall],
  );

  /** يُسلّم الجلسةَ ما سبقها من إشارات. */
  const drainSignals = useCallback(async (callId: string, session: CallSession) => {
    const held = signals.current.get(callId);
    signals.current.delete(callId);
    if (!held) return;
    if (held.offer) await session.acceptOffer(held.offer).catch(() => undefined);
    for (const candidate of held.ice) await session.addIce(candidate);
  }, []);

  /** **يرنّ عند الطرف الآخر** — العرضُ يخرج، و«يرنّ…» حتى يُردّ أو تنقضي مهلةُ الرنين فـ«لم يُجب». */
  const dial = useCallback(
    async (started: CallStart, local: MediaStream) => {
      const view = callRef.current;
      if (!view || view.callId !== started.call_id || OVER.has(view.stage)) {
        local.getTracks().forEach((track) => track.stop());
        return;
      }
      const session = new CallSession(started.call_id, started.ice_servers, local, sessionEvents());
      sessionRef.current = session;
      const answered = extras.current.answered;
      patchCall({ stage: answered ? "joining" : "dialing" });
      if (answered) session.armNegotiation();
      else play("callDial");
      extras.current.ringTimer = window.setTimeout(() => {
        const now = callRef.current;
        if (now?.callId === started.call_id && now.stage === "dialing") {
          // **الخادمُ يكتبها «لم يُجب»** حين يُنهيها المتصلُ بعد مهلة الرنين (`hang_up` → `no_answer`)
          endOnServer(started.call_id);
          finish("unanswered");
        }
      }, started.ring_timeout_seconds * 1_000);
      await session.sendOffer().catch(() => undefined);
      await drainSignals(started.call_id, session);
    },
    [drainSignals, endOnServer, finish, patchCall, sessionEvents],
  );

  const blankCall = useCallback(
    (rideId: string, outgoing: boolean): CallView => ({
      stage: "preparing",
      rideId,
      callId: null,
      outgoing,
      recording: false,
      since: null,
      muted: false,
      speaker: false,
      speakerReady: false,
      minimized: false,
      weak: false,
      lasted: null,
      reason: null,
    }),
    [],
  );

  const startCall = useCallback(async () => {
    const current = rideRef.current;
    if (!current || !inCommsWindow(current)) return;
    // **ولا مكالمةَ حيث لا يُرسم «اتصال»** (المقبس · الميكروفون · المفتاح) — «أعد المحاولة» تمرّ من هنا، **وكانت تبدأ مكالمةً
    // والمقبسُ ساقط** فلا يصل جوابٌ ولا مرشّح، فيرى المتصلُ «لم يُجب» والطرفُ الآخر قد ردّ (قِيس ٢٠٢٦-١٠-٠٨)
    if (!canCallRef.current) return;
    if (callRef.current && !OVER.has(callRef.current.stage)) return;
    clearTimers();
    extras.current.answered = false;
    extras.current.talked = false;
    const attempt = ++attempts.current;
    setCall(blankCall(current.id, true));
    /** **أهذه المحاولةُ ما زالت على الشاشة؟** — «إنهاء» يُغلقها، أو بدأت بعدها غيرُها */
    const still = () => attempts.current === attempt && callRef.current?.stage === "preparing";
    let local: MediaStream;
    try {
      local = await microphone();
    } catch {
      if (still()) finish("broken", MIC_REFUSED);
      return;
    }
    // **«إنهاء» والميكروفونُ يُسأل** — لا تُبدأ عند الخادم: كانت ترنّ عند الطرف الآخر ثمّ تُلغى، فتتركه بـ«مكالمةٌ فائتة» عن
    // مكالمةٍ أُنهيت قبل أن تبدأ، **وتأكل واحدةً من ستِّ مكالماتٍ في عشر دقائق** (قِيس ٢٠٢٦-١٠-٠٨)
    if (!still()) {
      local.getTracks().forEach((track) => track.stop());
      return;
    }
    let started: CallStart;
    try {
      started = await startRideCall(current.id);
    } catch (caught) {
      local.getTracks().forEach((track) => track.stop());
      if (!still()) return;
      if (caught instanceof ApiError && caught.code === "call_window_closed") finish("tripover");
      else finish("broken", messageOf(caught, "تعذّر بدءُ المكالمة — تحقّق من الاتصال."));
      return;
    }
    const view = callRef.current;
    if (!view || !still()) {
      // **أُغلقت الشاشةُ أثناء البدء** — تُنهى عند الخادم فلا ترنّ عند الطرف الآخر بلا من ينتظرها
      local.getTracks().forEach((track) => track.stop());
      void endRideCall(started.call_id).catch(() => undefined);
      return;
    }
    setCall({ ...view, callId: started.call_id, recording: started.recording });
    if (started.recording) {
      // **التنبيهُ قبل أن يخرج العرض** — و«متابعة» وحدَها تُرسل الإقرارَ وتُكمل (§٦٦-ج/١٦)
      extras.current.pending = { started, local };
      patchCall({ stage: "consent" });
      return;
    }
    await dial(started, local);
  }, [blankCall, clearTimers, dial, finish, patchCall, setCall]);

  const consent = useCallback(
    async (go: boolean) => {
      const view = callRef.current;
      const pending = extras.current.pending;
      if (!view || view.stage !== "consent" || !pending) return;
      extras.current.pending = null;
      if (!go) {
        pending.local.getTracks().forEach((track) => track.stop());
        void endRideCall(pending.started.call_id).catch(() => undefined);
        setCall(null);
        return;
      }
      try {
        await ackRecordingNotice(pending.started.call_id);
      } catch (caught) {
        pending.local.getTracks().forEach((track) => track.stop());
        finish("broken", messageOf(caught, "تعذّر بدءُ المكالمة — تحقّق من الاتصال."));
        return;
      }
      await dial(pending.started, pending.local);
    },
    [dial, finish, setCall],
  );

  /** **رنينٌ وارد** — من المقبس أو من إشعار؛ **ومكالمةٌ ثانيةٌ على مكالمةٍ جارية لا تقطعها**. */
  const ring = useCallback(
    (event: { ride_id: string; call_id: string; recording: boolean }, seconds: number) => {
      const view = callRef.current;
      if (view && (view.callId === event.call_id || !OVER.has(view.stage))) return;
      clearTimers();
      extras.current.answered = false;
      extras.current.talked = false;
      setCall({ ...blankCall(event.ride_id, false), stage: "incoming", callId: event.call_id, recording: event.recording });
      extras.current.stopRing = loop("callRing");
      extras.current.ringTimer = window.setTimeout(() => {
        const now = callRef.current;
        if (now?.callId === event.call_id && now.stage === "incoming") {
          clearTimers();
          setCall(null);
          missed();
        }
      }, Math.max(1, seconds) * 1_000);
    },
    [blankCall, clearTimers, missed, setCall],
  );

  const answer = useCallback(async () => {
    const view = callRef.current;
    if (!view || view.stage !== "incoming" || !view.callId) return;
    const callId = view.callId;
    clearTimers();
    patchCall({ stage: "joining" });
    let local: MediaStream;
    try {
      local = await microphone();
    } catch {
      void declineRideCall(callId).catch(() => undefined);
      finish("broken", MIC_REFUSED);
      return;
    }
    let ice: IceServer[];
    try {
      // **وفي المسجَّلة: الإقرارُ هو ما رآه فوق «ردّ»** — والخادمُ يرفض الردَّ بلاه
      ice = (await answerRideCall(callId, view.recording)).ice_servers;
    } catch (caught) {
      local.getTracks().forEach((track) => track.stop());
      if (caught instanceof ApiError && (caught.code === "call_not_ringing" || caught.code === "call_not_active")) {
        setCall(null);
        missed();
      } else if (caught instanceof ApiError && caught.code === "call_window_closed") {
        finish("tripover");
      } else {
        finish("broken", messageOf(caught, "تعذّر الردّ — تحقّق من الاتصال."));
      }
      return;
    }
    if (callRef.current?.callId !== callId || OVER.has(callRef.current.stage)) {
      local.getTracks().forEach((track) => track.stop());
      return;
    }
    const session = new CallSession(callId, ice, local, sessionEvents());
    sessionRef.current = session;
    session.armNegotiation();
    await drainSignals(callId, session);
  }, [clearTimers, drainSignals, finish, missed, patchCall, sessionEvents, setCall]);

  const decline = useCallback(() => {
    const view = callRef.current;
    if (!view?.callId || view.stage !== "incoming") return;
    clearTimers();
    void declineRideCall(view.callId).catch(() => undefined);
    setCall(null);
  }, [clearTimers, setCall]);

  const hangUp = useCallback(() => {
    const view = callRef.current;
    if (!view || OVER.has(view.stage)) return;
    if (view.callId) endOnServer(view.callId);
    if (view.stage === "talking" || view.stage === "joining") {
      finish("hungup");
      return;
    }
    // **قبل أن يُردّ**: إلغاءٌ لا «انتهت» — تُغلق الشاشةُ بلا نغمة
    clearTimers();
    teardown();
    setCall(null);
  }, [clearTimers, endOnServer, finish, setCall, teardown]);

  const toggleMute = useCallback(() => {
    const view = callRef.current;
    if (!view) return;
    sessionRef.current?.setMuted(!view.muted);
    patchCall({ muted: !view.muted });
  }, [patchCall]);

  const toggleSpeaker = useCallback(async () => {
    const view = callRef.current;
    const session = sessionRef.current;
    if (!view || !session) return;
    const target = view.speaker ? "default" : await speakerOutput();
    if (target && (await session.routeTo(target))) patchCall({ speaker: !view.speaker });
  }, [patchCall]);

  const minimize = useCallback((minimized: boolean) => patchCall({ minimized }), [patchCall]);

  const dismissCall = useCallback(() => {
    const view = callRef.current;
    if (view && !OVER.has(view.stage)) return;
    clearTimers();
    setCall(null);
  }, [clearTimers, setCall]);

  /** **«أعد المحاولة» بشروط «اتصال» نفسِها** — والزرُّ لا يُرسم بدونها (`CommsT2`)، وهذا لمن ضغطه في اللحظة التي سقطت فيها. */
  const retry = useCallback(() => {
    if (!canCallRef.current) return;
    dismissCall();
    void startCall();
  }, [dismissCall, startCall]);

  const messageInstead = useCallback(() => {
    const rideId = callRef.current?.rideId;
    dismissCall();
    openChat(rideId);
  }, [dismissCall, openChat]);

  // **الرحلةُ انتهت والمكالمةُ حيّة** — الخادمُ يُغلقها (`ride_ended`) ويبثّ ذلك، **وهذا لمن فاته البثّ**
  useEffect(() => {
    const view = callRef.current;
    if (!view || OVER.has(view.stage) || view.rideId !== currentId || windowOpen) return;
    if (view.stage === "incoming") {
      clearTimers();
      setCall(null);
      return;
    }
    finish("tripover");
  }, [clearTimers, currentId, finish, setCall, windowOpen]);

  // ─────────────────────────────── الأحداث

  const onEvent = useCallback(
    (event: TripCommsEvent) => {
      switch (event.type) {
        case "chat_message": {
          const open = chatRef.current;
          const mine = event.message.sender_role === side;
          if (open && open.rideId === event.ride_id) {
            if (open.thread && !open.thread.messages.some((m) => m.id === event.message.id)) {
              const message: ChatMessage = { ...event.message, ride_id: event.ride_id, mine };
              setChat({ ...open, thread: { ...open.thread, messages: [...open.thread.messages, message] } });
            }
            if (!mine) markReadSoon(event.ride_id);
            return;
          }
          if (mine || event.ride_id !== rideRef.current?.id) return;
          alertMessage(event.message.body);
          return;
        }
        case "chat_read": {
          const open = chatRef.current;
          if (!open?.thread || open.rideId !== event.ride_id) return;
          const until = Date.parse(event.read_at);
          setChat({
            ...open,
            thread: {
              ...open.thread,
              messages: open.thread.messages.map((m) =>
                m.mine && !m.read_at && Date.parse(m.created_at) <= until ? { ...m, read_at: event.read_at } : m,
              ),
            },
          });
          return;
        }
        case "incoming_call":
          ring(event, event.ring_timeout_seconds ?? 30);
          return;
        case "call_answered": {
          const view = callRef.current;
          if (!view || view.callId !== event.call_id) return;
          if (view.outgoing) {
            extras.current.answered = true;
            if (view.stage === "dialing") {
              if (extras.current.ringTimer !== null) window.clearTimeout(extras.current.ringTimer);
              extras.current.ringTimer = null;
              patchCall({ stage: "joining" });
              sessionRef.current?.armNegotiation();
              // **العرضُ ثانيةً بعد «ردّ»** — الخادمُ يمرّر الإشارةَ ولا يحفظها، **فمتصَلٌ به كان مقبسُه مغلقاً حين خرج العرضُ الأوّل**
              // (ردّ من إشعار، أو عاد من الخلفية) لا يصله غيرُ هذا؛ وكان يرى «ردّ» ثمّ «تعذّر الاتصال» بعد عشرين ثانية (قِيس
              // ٢٠٢٦-١٠-٠٨). ومن وصله الأوّلُ يُهمل الثاني (`acceptOffer`)
              void sessionRef.current?.resendOffer().catch(() => undefined);
            }
          } else if (view.stage === "incoming") {
            // **رُدّ عليها من جهازٍ آخرَ له** — تسكت هنا
            clearTimers();
            setCall(null);
          }
          return;
        }
        case "call_ended": {
          signals.current.delete(event.call_id);
          const view = callRef.current;
          if (!view || view.callId !== event.call_id || OVER.has(view.stage)) return;
          const reason = event.end_reason;
          if (reason === "ride_ended") {
            if (view.stage === "incoming") {
              clearTimers();
              setCall(null);
            } else finish("tripover");
            return;
          }
          if (view.stage === "incoming") {
            clearTimers();
            setCall(null);
            if (reason === "cancelled" || reason === "no_answer") missed();
            return;
          }
          if (view.stage === "talking" || (view.stage === "joining" && extras.current.talked)) {
            finish(reason === "failed" ? "broken" : "hungup");
            return;
          }
          if (view.outgoing && (reason === "declined" || reason === "no_answer")) {
            finish("unanswered");
            return;
          }
          finish(reason === "completed" ? "hungup" : "broken");
          return;
        }
        case "call_signal": {
          const session = sessionRef.current;
          const view = callRef.current;
          if (session && view?.callId === event.call_id) {
            if (event.kind === "offer") void session.acceptOffer(event.payload).catch(() => undefined);
            else if (event.kind === "answer") void session.acceptAnswer(event.payload).catch(() => undefined);
            else void session.addIce(event.payload);
            return;
          }
          // **سبقت الإشارةُ جلستَها** — تُحفظ حتى «ردّ» أو حتى يُبنى الاتصال
          const held = signals.current.get(event.call_id) ?? { offer: null, ice: [] };
          if (event.kind === "offer") held.offer = event.payload;
          else if (event.kind === "ice") held.ice.push(event.payload);
          signals.current.set(event.call_id, held);
          return;
        }
      }
    },
    [alertMessage, clearTimers, finish, markReadSoon, missed, patchCall, ring, setCall, setChat, side],
  );

  useEffect(() => onTripComms(onEvent), [onEvent]);

  // ─────────────────────────────── الإشعار: نقرتُه ووصولُه والتطبيقُ مفتوح

  /** **أترنّ بعدُ؟** — والسؤالُ نفسُه يكتب الفائتةَ فائتةً عند الخادم. **ولا يُسأل إلا والمقبسُ حيّ** (`pushRoute`). */
  const ringFromPush = useCallback(
    (callId: string, rideId: string, how: "tap" | "received") => {
      if (callRef.current?.callId === callId) return;
      void getRideCall(callId)
        .then((state) => {
          if (state.status === "ringing" && !state.mine) {
            const elapsed = (Date.now() - Date.parse(state.started_at)) / 1000;
            ring({ ride_id: rideId, call_id: callId, recording: state.recording }, Math.min(30, Math.max(5, 30 - elapsed)));
          } else if (how === "tap" && !state.mine && state.status === "ended" && state.answered_at === null) {
            missed();
          }
        })
        .catch(() => {
          if (how === "tap") missed();
        });
    },
    [missed, ring],
  );

  const dropHeldRing = useCallback(() => {
    const held = heldRing.current;
    heldRing.current = null;
    if (held) window.clearTimeout(held.timer);
    return held;
  }, []);

  const pushRoute = useCallback(
    (data: Record<string, string>, how: "tap" | "received"): boolean => {
      const rideId = data.ride_id;
      if (data.type === "chat_message") {
        if (how === "tap") {
          openChat(rideId);
          return true;
        }
        // **وصل والتطبيقُ مفتوحٌ بلا مقبس** — الإشعارُ لا يحمل النصّ (شاشةُ القفل)، فالشارةُ والتنبيهُ بلا نصّ؛ **والورقةُ المفتوحةُ
        // تُعاد قراءتُها وهي أمام صاحبها وحدَه** (القراءةُ تعلّمها مقروءة)
        const open = chatRef.current;
        if (open && open.rideId === rideId) {
          if (!document.hidden) void load(rideId);
          return true;
        }
        if (rideId === rideRef.current?.id) alertMessage(null);
        return true;
      }
      if (data.type === "incoming_call" && data.call_id) {
        const callId = data.call_id;
        if (callRef.current?.callId === callId) return true;
        // **ولا رنينَ والمقبسُ مغلق** — العرضُ والجوابُ والمرشّحون يصلون منه وحدَه، فـ«ردّ» بلاه شاشةُ اتصالٍ لا يكتمل (قِيس
        // ٢٠٢٦-١٠-٠٨). **فيُحفظ حتى يُفتح** — الإقلاعُ من نقرة إشعارٍ يفتحه في ثوانٍ — **ويُقال «فائتة» لنقرةٍ لم يُفتح بعدها**
        if (!liveRef.current) {
          dropHeldRing();
          heldRing.current = {
            callId,
            rideId,
            how,
            timer: window.setTimeout(() => {
              if (dropHeldRing()?.how === "tap") missed();
            }, LIVE_WAIT_MS),
          };
          return true;
        }
        ringFromPush(callId, rideId, how);
        return true;
      }
      return false;
    },
    [alertMessage, dropHeldRing, load, missed, openChat, ringFromPush],
  );

  // **فُتح المقبس ورنينٌ من إشعارٍ ينتظره** — يُسأل الآن أترنّ بعدُ
  useEffect(() => {
    if (!live) return;
    const held = dropHeldRing();
    if (held) ringFromPush(held.callId, held.rideId, held.how);
  }, [live, dropHeldRing, ringFromPush]);

  useEffect(() => {
    setCommsPushRoute(pushRoute);
    return () => setCommsPushRoute(null);
  }, [pushRoute]);

  // **الخروجُ من الحساب يُغلق كلَّ شيء** — لا ميكروفونَ مفتوحٌ ولا رنينٌ لمن خرج
  useEffect(
    () => () => {
      clearTimers();
      teardown();
      dropHeldRing();
    },
    [clearTimers, dropHeldRing, teardown],
  );

  const value = useMemo<CommsState>(
    () => ({
      side,
      peer,
      peerRole,
      canMessage,
      canCall,
      unread,
      chat,
      call,
      openChat,
      closeChat,
      send,
      report,
      startCall: () => void startCall(),
      consent: (go: boolean) => void consent(go),
      answer: () => void answer(),
      decline,
      hangUp,
      toggleMute,
      toggleSpeaker: () => void toggleSpeaker(),
      minimize,
      dismissCall,
      retry,
      messageInstead,
    }),
    [
      side,
      peer,
      peerRole,
      canMessage,
      canCall,
      unread,
      chat,
      call,
      openChat,
      closeChat,
      send,
      report,
      startCall,
      consent,
      answer,
      decline,
      hangUp,
      toggleMute,
      toggleSpeaker,
      minimize,
      dismissCall,
      retry,
      messageInstead,
    ],
  );

  return <CommsContext.Provider value={value}>{children}</CommsContext.Provider>;
}

/** «02:13» — **دقائقُ وثوانٍ بخاناتٍ لاتينية** (§20)، بلا منسِّق: عدّادٌ لا تاريخ. */
export function callClock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  return `${String(minutes).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}
