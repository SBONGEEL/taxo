/** **مكالمةُ WebRTC صوتاً وحدَه** (SPEC §٦٦-ج/١٥، §٦٦-د/٢) — اتصالُ الندّين، والإشارةُ عبر الخادم، والتسجيلُ حين يُعلَن.
 *
 * **بلا React وبلا حالِ شاشة**: يعرف الاتصالَ وحدَه ويُبلغ بما يقع (`SessionEvents`) — **والطبقةُ** (`lib/comms.tsx`) تقرّر ما
 * يُرسم. **والإشارةُ تُرسل بـREST** (`POST /calls/{id}/signal`) **وتصل من المقبس القائم** (`call_signal`) — فلا مقبسَ ثانٍ.
 *
 * **والمُرحِّلُ ما يعطيه الخادمُ لهذه المكالمة** (`ice_servers`): بياناتُ دخولٍ مؤقّتةٌ لطرفَي الرحلة وحدهما، **وقائمةٌ فارغةٌ في
 * التطوير** فلا يبقى إلا المرشّحون المحليّون — يكفون جهازين على شبكةٍ واحدة، ولا يكفون شبكتين.
 *
 * **وتعذُّرُ الاتصال يُقال ولا يُنتظر** (§٦٦-د/٥): مفاوضةٌ لم تكتمل في عشرين ثانية، أو ICE فشل، أو انقطع ولم يعد — `broken`.
 * **والانقطاعُ القصيرُ ضعفٌ لا فشل** (`weak`): يُقال «الشبكةُ ضعيفة…» سطراً، ويُمهَل قبل أن يُعدّ فشلاً.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين حرفاً.**
 */

import { signalRideCall } from "@/api/endpoints";
import type { IceServer } from "@/api/types";

/** **مهلةُ المفاوضة** — «إن لم تكتمل خلال عشرين ثانية» (§٦٦-د/٥) بحرفه. */
export const NEGOTIATION_MS = 20_000;

/** **كم يُمهَل انقطاعٌ قبل أن يُعدّ فشلاً** — ICE يعود وحدَه من انقطاعٍ قصير (نفقٌ، مصعد)، وفشلٌ يُعلَن عند أوّل رمشةٍ
 *  يقطع مكالمةً كانت ستعود. وثمانٍ أقلُّ من نصف مهلة المفاوضة، فلا يبقى صاحبُها أمام صمتٍ طويل. */
const WEAK_GRACE_MS = 8_000;

export interface SessionEvents {
  /** الصوتُ وصل أوّلَ مرّة — `iceConnectionState` صار `connected` أو `completed`. */
  connected: () => void;
  /** ضعُفت الشبكة (`true`) أو عادت (`false`) — سطرٌ لا فشل. */
  weak: (weak: boolean) => void;
  /** تعذّر الاتصال — المهلةُ أو الفشلُ أو انقطاعٌ لم يعد. */
  broken: () => void;
}

/** صيغُ التسجيل بالترتيب — **وما يقبله الخادمُ** (`storage.sniff_audio`: webm أو ogg). */
const RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/ogg"];

export class CallSession {
  private readonly pc: RTCPeerConnection;
  private readonly audio: HTMLAudioElement;
  private remote: MediaStream | null = null;
  /** مرشّحون وصلوا قبل الوصف البعيد — **يُضافون بعده** وإلا رُفضوا */
  private pendingIce: RTCIceCandidateInit[] = [];
  private remoteDescribed = false;
  /** **أُخذ عرضٌ ليُجاب** — يُرفع متزامناً، فعرضان يصلان معاً لا يُجابان كلاهما */
  private offerTaken = false;
  private connectedOnce = false;
  private closed = false;
  private negotiationTimer: number | null = null;
  private weakTimer: number | null = null;
  private recorder: MediaRecorder | null = null;
  private recordingContext: AudioContext | null = null;
  private chunks: Blob[] = [];

  constructor(
    private readonly callId: string,
    iceServers: IceServer[],
    readonly local: MediaStream,
    private readonly events: SessionEvents,
  ) {
    this.pc = new RTCPeerConnection({ iceServers });
    for (const track of local.getAudioTracks()) this.pc.addTrack(track, local);
    // **الصوتُ البعيدُ في عنصرٍ لا يُرسم** — `autoplay` و`play()` معاً: الضغطةُ التي بدأت المكالمةَ إيماءةٌ تفتح الصوت
    this.audio = new Audio();
    this.audio.autoplay = true;
    this.pc.ontrack = (event) => {
      this.remote = event.streams[0] ?? new MediaStream([event.track]);
      this.audio.srcObject = this.remote;
      void this.audio.play().catch(() => undefined);
    };
    this.pc.onicecandidate = (event) => {
      // **`null` نهايةُ المرشّحين** — لا شيءَ يُرسل
      if (event.candidate && !this.closed) void this.send("ice", event.candidate.toJSON() as Record<string, unknown>);
    };
    this.pc.oniceconnectionstatechange = () => this.onIceState();
  }

  /** **المتصل**: العرضُ يُرسل — ويصل المتصَلَ به وهو يرنّ، فيحفظه حتى «ردّ». */
  async sendOffer(): Promise<void> {
    const offer = await this.pc.createOffer();
    await this.pc.setLocalDescription(offer);
    await this.send("offer", { type: offer.type, sdp: offer.sdp ?? "" });
  }

  /** **المتصل بعد «ردّ»**: العرضُ نفسُه ثانيةً — **بمرشّحيه في وصفه** (`localDescription` يحمل ما جُمع). الخادمُ يمرّر ولا يحفظ،
   *  فمتصَلٌ به كان مقبسُه مغلقاً حين خرج العرضُ الأوّل لا يصله غيرُ هذا. **ولا يُعاد بعد أن وصل الجواب** (`stable`). */
  async resendOffer(): Promise<void> {
    const local = this.pc.localDescription;
    if (this.closed || !local || local.type !== "offer" || this.pc.signalingState !== "have-local-offer") return;
    await this.send("offer", { type: local.type, sdp: local.sdp });
  }

  /** **المتصَلُ به بعد «ردّ»**: العرضُ المحفوظ ⇒ الجواب. **وعرضٌ واحدٌ يُجاب**: الثاني (`resendOffer`) يصل من وصله الأوّلُ أيضاً،
   *  وقد يصل والأوّلُ بعدُ في منتصف الطريق — فالعلَمُ يُرفع قبل أوّل `await` لا بعده. */
  async acceptOffer(offer: Record<string, unknown>): Promise<void> {
    if (this.offerTaken || this.pc.remoteDescription) return;
    this.offerTaken = true;
    try {
      await this.pc.setRemoteDescription(offer as unknown as RTCSessionDescriptionInit);
    } catch (caught) {
      // **عرضٌ لم يُقبل لا يحجب الذي بعده**
      this.offerTaken = false;
      throw caught;
    }
    await this.flushIce();
    const answer = await this.pc.createAnswer();
    await this.pc.setLocalDescription(answer);
    await this.send("answer", { type: answer.type, sdp: answer.sdp ?? "" });
  }

  /** **المتصل**: الجوابُ وصل. */
  async acceptAnswer(answer: Record<string, unknown>): Promise<void> {
    if (this.remoteDescribed || this.pc.signalingState !== "have-local-offer") return;
    await this.pc.setRemoteDescription(answer as unknown as RTCSessionDescriptionInit);
    await this.flushIce();
  }

  /** مرشّحٌ من الطرف الآخر — **يُحفظ إن سبق الوصف**. */
  async addIce(candidate: Record<string, unknown>): Promise<void> {
    const init = candidate as RTCIceCandidateInit;
    if (!this.pc.remoteDescription) {
      this.pendingIce.push(init);
      return;
    }
    await this.pc.addIceCandidate(init).catch(() => undefined);
  }

  /** **تبدأ مهلةُ العشرين** — من لحظة الردّ لا من الرنين: الرنينُ مهلتُه هو (`ring_timeout_seconds`). */
  armNegotiation(): void {
    this.clearNegotiation();
    this.negotiationTimer = window.setTimeout(() => {
      if (!this.connectedOnce) this.fail();
    }, NEGOTIATION_MS);
  }

  setMuted(muted: boolean): void {
    for (const track of this.local.getAudioTracks()) track.enabled = !muted;
  }

  /** **مكبّرُ الصوت حيث تسمح المنصّة** — مخرجٌ صوتيٌّ يُختار بـ`setSinkId`؛ ويعيد `false` حيث لا يُختار. */
  async routeTo(deviceId: string): Promise<boolean> {
    const sink = this.audio as HTMLAudioElement & { setSinkId?: (id: string) => Promise<void> };
    if (typeof sink.setSinkId !== "function") return false;
    try {
      await sink.setSinkId(deviceId);
      return true;
    } catch {
      return false;
    }
  }

  /** **تسجيلُ الصوتين معاً** في جهاز المتصل (§٦٦-د/٣) — **حين يُعلن الخادمُ المكالمةَ مسجَّلةً وحدَها**، ولا يبدأ قبل وصول الصوت
   *  البعيد. وصمتُ `MediaRecorder` (منصّةٌ بلا صيغةٍ مقبولة) لا يُسقط المكالمة. */
  startRecording(): void {
    if (this.recorder || !this.remote || typeof MediaRecorder === "undefined") return;
    try {
      const ctx = new AudioContext();
      const mix = ctx.createMediaStreamDestination();
      ctx.createMediaStreamSource(this.local).connect(mix);
      ctx.createMediaStreamSource(this.remote).connect(mix);
      const type = RECORDING_TYPES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = new MediaRecorder(mix.stream, type ? { mimeType: type } : undefined);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) this.chunks.push(event.data);
      };
      recorder.start(1_000);
      this.recorder = recorder;
      this.recordingContext = ctx;
    } catch {
      this.recorder = null;
    }
  }

  /** يوقف التسجيلَ ويعيد ملفَّه — أو `null` بلا تسجيل. */
  async stopRecording(): Promise<Blob | null> {
    const recorder = this.recorder;
    if (!recorder) return null;
    this.recorder = null;
    if (recorder.state !== "inactive") {
      await new Promise<void>((resolve) => {
        recorder.onstop = () => resolve();
        recorder.stop();
      });
    }
    void this.recordingContext?.close().catch(() => undefined);
    this.recordingContext = null;
    if (this.chunks.length === 0) return null;
    const blob = new Blob(this.chunks, { type: (recorder.mimeType || "audio/webm").split(";")[0] });
    this.chunks = [];
    return blob;
  }

  /** يُغلق كلَّ شيء — **والميكروفونُ أوّلاً**: مؤشّرُه في شريط النظام لا يبقى مضاءً بعد مكالمةٍ انتهت. */
  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.clearNegotiation();
    if (this.weakTimer !== null) window.clearTimeout(this.weakTimer);
    this.weakTimer = null;
    for (const track of this.local.getTracks()) track.stop();
    this.pc.ontrack = null;
    this.pc.onicecandidate = null;
    this.pc.oniceconnectionstatechange = null;
    this.pc.close();
    this.audio.srcObject = null;
  }

  private onIceState(): void {
    if (this.closed) return;
    const state = this.pc.iceConnectionState;
    if (state === "connected" || state === "completed") {
      if (this.weakTimer !== null) window.clearTimeout(this.weakTimer);
      this.weakTimer = null;
      this.events.weak(false);
      if (!this.connectedOnce) {
        this.connectedOnce = true;
        this.clearNegotiation();
        this.events.connected();
      }
      return;
    }
    if (state === "failed") {
      this.fail();
      return;
    }
    // **انقطاعٌ بعد اتصال**: ضعفٌ يُقال، ومهلةٌ قبل الحكم بالفشل
    if (state === "disconnected" && this.connectedOnce) {
      this.events.weak(true);
      if (this.weakTimer === null) {
        this.weakTimer = window.setTimeout(() => {
          this.weakTimer = null;
          if (this.pc.iceConnectionState !== "connected" && this.pc.iceConnectionState !== "completed") this.fail();
        }, WEAK_GRACE_MS);
      }
    }
  }

  private fail(): void {
    if (this.closed) return;
    this.events.broken();
  }

  private clearNegotiation(): void {
    if (this.negotiationTimer !== null) window.clearTimeout(this.negotiationTimer);
    this.negotiationTimer = null;
  }

  private async flushIce(): Promise<void> {
    this.remoteDescribed = true;
    const pending = this.pendingIce;
    this.pendingIce = [];
    for (const candidate of pending) await this.pc.addIceCandidate(candidate).catch(() => undefined);
  }

  /** **إشارةٌ تسقط لا تُسقط المكالمة** — مهلةُ المفاوضة هي الحَكَم: ما لم يصل يُقال «تعذّر» بعدها. */
  private async send(kind: "offer" | "answer" | "ice", payload: Record<string, unknown>): Promise<void> {
    try {
      await signalRideCall(this.callId, kind, payload);
    } catch {
      // انظر أعلاه
    }
  }
}

/** **أيُّ مخرجٍ يصير «مكبّرَ الصوت»** — حيث يعدّد المتصفّحُ المخارجَ ويختار بينها (`setSinkId`)؛ و`null` حيث لا: **غلافُ أندرويد
 *  ومتصفّحُه لا يعرضان اختيارَ المخرج** (`setSinkId` غائبةٌ أو بمخرجٍ واحد)، فيختفي الزرُّ ولا يَعِد بما لا يقع — **والمكبّرُ
 *  هناك يحتاج ملحقاً أصليّاً** (`AudioManager.setSpeakerphoneOn`) يُبنى مع حزمة المكالمة. */
export async function speakerOutput(): Promise<string | null> {
  const probe = (typeof document !== "undefined" ? document.createElement("audio") : null) as
    | (HTMLAudioElement & { setSinkId?: unknown })
    | null;
  if (!probe || typeof probe.setSinkId !== "function") return null;
  try {
    const outputs = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "audiooutput");
    if (outputs.length < 2) return null;
    const other = outputs.find((device) => device.deviceId !== "default" && device.deviceId !== "communications");
    return other?.deviceId ?? null;
  } catch {
    return null;
  }
}
