/** مقبس الكبتن — `WS /ws/driver` (SPEC القسم 10/12.2).
 *
 * **فتحُ المقبس هو نفسه مفتاح Online، وإغلاقه ينزله.** الخلفية تستدعي
 * `go_online` عند القبول وتُسقط الكبتن من الفهرس الجغرافي عند الإغلاق
 * (`ws/routes.py::driver_socket`)، فلا مفتاحَ منفصل ولا حالةَ تُخزَّن في
 * التطبيق: المقبسُ مفتوح ⇔ الكبتن متصل. ومسارا REST
 * (`/drivers/me/online|offline`) موجودان لتطبيقٍ فقد مقبسه.
 *
 * وثلاثة أشياء يفعلها هذا الملف ولا يفعلها غيره:
 *
 * - **يفتح المقبس بنفس `device_id`** الذي سجّل رمز الجهاز. بغيره تصل بطاقةُ
 *   الطلب مرتين: على الشاشة ومن نظام التشغيل (القسم 10/12.8).
 * - **يبثّ الموقع بسياسة الخادم** (§٧٥-ج، كانت كلَّ ثلاث ثوانٍ): متاحٌ كلَّ ١٥–٤٥ ثانية، في الطريق كلَّ ١٠، **وفي الرحلة نقطةٌ كلَّ
 *   ثانيتين تُرسل دفعةً كلَّ ١٥** فلا تقصر مسافةُ الأجرة؛ **والساكنُ لا يرسل** حتى يبتعد ثلاثين متراً، ونبضتُه تُبقيه حاضراً.
 *   وأوّلُ بثِّ موقعٍ هو ما يُدخله الفهرس — `is_online` وحده لا يكفي.
 * - **يعيد الاتصال بتباعدٍ متزايد**، ويترك للمستدعي استرجاع الحالة عبر REST
 *   عند كل اتصالٍ ناجح.
 *
 * ولا يقرأ التوكن من التخزين بنفسه: يأخذه عند كل محاولة، فيلتقط المجدَّد بدل
 * أن يعيد المحاولة بتوكنٍ انتهى.
 */

import { WS_URL, tokens } from "@/api/client";
import { reportLocationOverRest, reportPointsOverRest } from "@/api/endpoints";
import { onlineService } from "@/lib/online-service";
import type { Ride } from "@/api/types";
import { deviceId } from "@/lib/device";
import type { TripCommsEvent } from "@/lib/trip-comms"; import { tr } from "@/lib/i18n";

export type DriverSocketEvent =
  | { type: "connected"; active_ride: Ride | null }
  | {
      type: "ride_offer";
      ride: Ride;
      distance_to_pickup_km: number;
      expires_in_seconds: number;
    }
  | { type: "offer_expired"; ride_id: string }
  | {
      type:
        | "driver_assigned"
        | "driver_arrived"
        | "ride_started"
        | "ride_completed"
        | "ride_cancelled";
      ride: Ride;
    }
  | {
      type: "document_approved" | "document_rejected";
      review_note: string | null;
    }
  // أدخل الراكب مرجع حوالته — الحمولة ما تحتاجه بطاقة التأكيد لا الدفعة
  // كاملة، ولا هوية راكبٍ فيها كما لا هوية في بطاقة الطلب
  | {
      type: "cliq_transfer_submitted";
      ride_id: string;
      payment_id: string;
      amount: string;
      currency: string;
      transfer_reference: string;
      expires_at: string | null;
    }
  // **بلاغٌ لما لا يُرسم من حدثٍ له** (§٦١-ل/٣) — الحمولةُ نفسُها التي يحملها إشعارُه
  | { type: "notice"; title: string; body: string; data: Record<string, string> }
  // **محادثةُ الرحلة ومكالمتُها** (§٦٦) — على المقبس نفسِه، وطبقتُها في `lib/comms.tsx`
  | TripCommsEvent
  | { type: "error"; detail: string };
// ولا عضوَ جامع `{ type: string }` في الاتحاد: وجودُه يجعل كل فرعٍ في
// `switch` غيرَ مُضيَّق فيصير كلُّ حقلٍ `unknown`. والأحداثُ غيرُ المعروفة
// تسقط في `default` وقتَ التشغيل — وهو ما نريده بالضبط.

interface Options {
  onEvent: (event: DriverSocketEvent) => void;
  /** بعد كل اتصالٍ ناجح — مكانُ الاسترجاع عبر REST. */
  onOpen?: () => void;
  /** بإغلاقٍ نهائي أو مؤقت — عليه تُرسم حالة «متصل/غير متصل». */
  onClose?: (permanent: boolean) => void;
  /** رفضٌ من الخلفية (غير معتمد، بلا مركبة، بلا اشتراك) برسالته العربية. */
  onRejected?: (reason: string) => void;
}

const RETRY_BASE_MS = 1_000;
const RETRY_MAX_MS = 15_000;

/** **دورةُ القرار** (§٧٥-ج) — كلَّ ثانيةٍ يُسأل: أحان إرسالٌ في هذه الحال؟ والقرارُ لا الإرسال: أكثرُ الدورات لا ترسل شيئاً. */
const TICK_MS = 1_000;
/** **نبضةُ الخدمة الأمامية من الدورة** لا من الإرسال — فالإرسالُ صار متباعداً (حتى ٦٠ ثانيةً للساكن)، وفاصلُ بثِّ الخدمة الأصليّةِ
 *  ٢٠ ثانية (`OnlineService.BROADCAST_MS`) يُعاد تسليحُه بكلِّ نبضة: **فما دامت دورةُ الويب حيّةً لا تبثّ الخدمةُ شيئاً**، وإن خنق
 *  النظامُ مؤقّتاتِ الويب سكتت النبضةُ فبثّت الخدمةُ ثمّ قلبت إشعارَها كما كانت. */
const PULSE_MS = 10_000;
/** كم يُنتظر إقرارُ دفعة الرحلة الأخيرة قبل الإنهاء — ثمّ REST */
const FLUSH_ACK_MS = 3_000;

/** **سياسةُ البثّ** (§٧٥-ج) — تصل مع «connected» وحيّةً بعده (`broadcast_policy`)، **ولا تُكتب قيمُها هنا إلا افتراضاً قبل وصولها**
 *  (قيمُ ترحيلة الخادم نفسُها). */
export interface BroadcastPolicy {
  mode: string;
  available_seconds: number;
  heading_seconds: number;
  trip_send_seconds: number;
  trip_record_seconds: number;
  move_meters: number;
  heartbeat_seconds: number;
}

const DEFAULT_POLICY: BroadcastPolicy = {
  mode: "automatic",
  available_seconds: 15,
  heading_seconds: 10,
  trip_send_seconds: 15,
  trip_record_seconds: 2,
  move_meters: 30,
  heartbeat_seconds: 60,
};

/** **حالُ الكبتن كما يبثّ بها**: متاحٌ ينتظر · في الطريق إلى الراكب (قبل البدء) · في الرحلة. */
export type BroadcastMode = "available" | "heading" | "trip";

interface TripPoint {
  lat: number;
  lng: number;
  heading: number | null;
  t: number;
}

interface Batch {
  seq: number;
  points: TripPoint[];
  /** متى أُرسلت على المقبس آخرَ مرّة — **وتُعاد إن لم يُقَرّ بها في `RESEND_MS`** لا في كلِّ دورة */
  sentAt: number;
}

/** إعادةُ دفعةٍ لم يُقَرّ بها — والإقرارُ يصل في أجزاءٍ من الثانية عادةً */
const RESEND_MS = 5_000;

function meters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

// رموز الإغلاق التي تعني «لا تُعِد المحاولة» — الخلفية ترفض لسببٍ لا يزول
// بإعادة الاتصال (`ws/routes.py`: 4401 جلسة، 4403 صلاحية)
const WS_UNAUTHORIZED = 4401;
const WS_FORBIDDEN = 4403;

export class DriverSocket {
  private socket: WebSocket | null = null;
  private retries = 0;
  private timer: number | null = null;
  private ticker: number | null = null;
  private closed = false;
  private last: GeolocationPosition | null = null;
  private watch: number | null = null;
  /** طلبُ REST قائم — فلا يُتبَع بآخرَ فوقه على شبكةٍ ضعيفة */
  private restInFlight = false;

  // ── البثُّ المتكيّف (§٧٥-ج)
  private policy: BroadcastPolicy = DEFAULT_POLICY;
  private mode: BroadcastMode = "available";
  /** آخرُ موقعٍ أُرسل ومتى — عليه تُقاس قاعدةُ الثلاثين متراً والفاصل */
  private sent: { lat: number; lng: number; at: number } | null = null;
  /** آخرُ إطارٍ أُرسل من أيِّ نوع — عليه تُقاس النبضة */
  private lastFrameAt = 0;
  /** **ساكنٌ ينتظر الحركة**: دورةٌ حان فيها الإرسالُ ولم يتحرّك — فأوّلُ ثلاثين متراً تُرسل فوراً */
  private holding = false;
  private lastPulseAt = 0;
  // ── نقاطُ الرحلة: تُسجَّل كلَّ `trip_record_seconds` وتُرسل دفعةً كلَّ `trip_send_seconds`، **ولا تُمحى إلا بإقرار**
  private buffer: TripPoint[] = [];
  private pending: Batch[] = [];
  private lastRecordAt = 0;
  private lastBatchAt = 0;
  private lastSeq = 0;

  constructor(private readonly options: Options) {}

  /** **ظهورُ التطبيق لصاحبه يُبلَّغ به المقبس** (§٦١-ل/٣): المقبسُ يبقى حيّاً
   *  والتطبيقُ في الخلفية — والخدمةُ الأماميةُ تُبقيه عمداً — **فكانت الخلفيةُ
   *  تحجب الإشعارَ عن هاتفٍ في الجيب**. فيُبلَّغ عند كلِّ تبدّلٍ وعند كلِّ اتصال. */
  private readonly reportVisibility = () =>
    this.send({ type: "visibility", visible: !document.hidden });

  open() {
    this.closed = false;
    document.addEventListener("visibilitychange", this.reportVisibility);
    this.startWatching();
    this.connect();
    // **الدورةُ تعمل والمقبسُ ساقط** — فالقرارُ واحدٌ والناقلُ يُختار عند الإرسال (المقبس أو REST)
    if (this.ticker === null) this.ticker = window.setInterval(() => this.tick(), TICK_MS);
  }

  close() {
    this.closed = true;
    document.removeEventListener("visibilitychange", this.reportVisibility);
    if (this.timer !== null) window.clearTimeout(this.timer);
    if (this.ticker !== null) window.clearInterval(this.ticker);
    if (this.watch !== null) navigator.geolocation?.clearWatch(this.watch);
    this.timer = this.ticker = this.watch = null;
    this.socket?.close();
    this.socket = null;
  }

  /** آخر موقعٍ معروف — ترسمه الخريطة قبل أول بثّ. */
  position(): GeolocationPosition | null {
    return this.last;
  }

  /** **حالُ الكبتن** — من الرحلة النشطة (`lib/ride.tsx`). الخروجُ من الرحلة يرسل ما بقي من نقاطها. */
  setMode(mode: BroadcastMode) {
    if (mode === this.mode) return;
    if (this.mode === "trip") this.cutBatch();
    this.mode = mode;
    this.holding = false;
    this.lastRecordAt = this.lastBatchAt = 0;
    // حالٌ جديدةٌ موقعُها يُرسل الآن — الراكبُ ينتظر أن يرى سيارةً تتحرّك نحوه
    this.sendLocation();
  }

  /** **قبل إنهاء الرحلة**: آخرُ النقاط تُرسل ويُنتظر إقرارُها — **فلا تقصر مسافةُ الأجرة بآخر خمسَ عشرةَ ثانية**. */
  async flushTrip(): Promise<void> {
    if (this.mode !== "trip") return;
    this.record(true);
    this.cutBatch();
    this.flushPending();
    const deadline = Date.now() + FLUSH_ACK_MS;
    while (this.pending.length && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
    }
    // **وما لم يُقَرّ به على المقبس يُرسل بـREST وينتظر** — والفشلُ لا يمنع الإنهاء: الخادمُ يقيس بما وصله
    for (const batch of [...this.pending]) {
      try {
        await reportPointsOverRest(batch);
        this.acknowledge(batch.seq);
      } catch {
        break;
      }
    }
  }

  private startWatching() {
    if (this.watch !== null || !navigator.geolocation) return;
    this.watch = navigator.geolocation.watchPosition(
      (position) => {
        this.last = position;
      },
      // رفضُ إذن الموقع ليس عطلاً يُسقط المقبس: الكبتن يبقى متصلاً ولا
      // يدخل الفهرس الجغرافي، وهو ما ستقوله له الشاشة
      () => undefined,
      { enableHighAccuracy: true, maximumAge: 2_000, timeout: 10_000 },
    );
  }

  private open_(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private send(payload: unknown): boolean {
    if (!this.open_()) return false;
    this.socket!.send(JSON.stringify(payload));
    this.lastFrameAt = Date.now();
    return true;
  }

  private fix(): { lat: number; lng: number; heading: number | null } | null {
    const position = this.last;
    if (!position) return null;
    return {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      // `heading` غائبٌ على أجهزةٍ ثابتة، و`null` أصدقُ من صفرٍ يعني «شمالاً»
      heading: Number.isFinite(position.coords.heading) ? position.coords.heading : null,
    };
  }

  /** **الدورة** (§٧٥-ج): الرحلةُ تسجّل وترسل دفعات، وما سواها يرسل بفاصله وقاعدةِ الثلاثين متراً، **والنبضةُ لكلِّ ساكن**. */
  private tick() {
    if (this.closed) return;
    const now = Date.now();
    if (now - this.lastPulseAt >= PULSE_MS && this.open_()) {
      this.lastPulseAt = now;
      onlineService.start();
    }
    if (this.mode === "trip") {
      this.record(false);
      if (now - this.lastBatchAt >= this.policy.trip_send_seconds * 1000) this.cutBatch();
      this.flushPending();
      // **وبلا نقاطٍ** (لا إشارةَ موقعٍ في نفق) **تبقى النبضة** — فلا يسقط الحضورُ في منتصف رحلة
      if (now - this.lastFrameAt >= this.policy.heartbeat_seconds * 1000) this.heartbeat();
      return;
    }
    const fix = this.fix();
    const interval = (this.mode === "heading" ? this.policy.heading_seconds : this.policy.available_seconds) * 1000;
    if (fix) {
      if (!this.sent) {
        this.sendLocation();
        return;
      }
      const moved = meters(this.sent, fix) >= this.policy.move_meters;
      if (moved && (this.holding || now - this.sent.at >= interval)) {
        this.sendLocation();
        return;
      }
      // حان الإرسالُ ولم يتحرّك — **لا يرسل**، وأوّلُ ثلاثين متراً بعدها تُرسل فوراً
      if (!moved && now - this.sent.at >= interval) this.holding = true;
    }
    if (now - this.lastFrameAt >= this.policy.heartbeat_seconds * 1000) this.heartbeat();
  }

  /** موقعٌ واحدٌ الآن — **بالمقبس، وإلا بـREST** */
  private sendLocation() {
    const fix = this.fix();
    if (!fix) return;
    this.holding = false;
    const sentOverSocket = this.send({ type: "location", ...fix });
    if (!sentOverSocket) {
      if (this.restInFlight) return;
      this.restInFlight = true;
      void reportLocationOverRest(fix)
        .catch(() => undefined)
        .finally(() => {
          this.restInFlight = false;
        });
      this.lastFrameAt = Date.now();
    }
    this.sent = { lat: fix.lat, lng: fix.lng, at: Date.now() };
  }

  /** **نبضةُ «ما زلتُ متّصلاً»** — بلا موقع على المقبس؛ وبلا مقبسٍ يُرسل الموقعُ بـREST (لا بابَ نبضةٍ هناك) */
  private heartbeat() {
    if (!this.send({ type: "heartbeat" })) this.sendLocation();
  }

  /** نقطةُ رحلةٍ كلَّ `trip_record_seconds` — أو الآن (`force`) قبل الإنهاء */
  private record(force: boolean) {
    const fix = this.fix();
    const now = Date.now();
    if (!fix || (!force && now - this.lastRecordAt < this.policy.trip_record_seconds * 1000)) return;
    this.lastRecordAt = now;
    this.buffer.push({ ...fix, t: now });
  }

  /** يقطع ما سُجّل دفعةً تنتظر الإرسالَ والإقرار — **ورقمُها الوقتُ** فلا يتكرّر بعد إعادة تشغيل التطبيق */
  private cutBatch() {
    this.lastBatchAt = Date.now();
    if (!this.buffer.length) return;
    let seq = Math.max(Date.now(), this.lastSeq + 1);
    // سقفُ الخادم ١٢٠ نقطةً للدفعة — وما تراكم في انقطاعٍ أطولَ يُقسَم
    while (this.buffer.length) {
      this.pending.push({ seq, points: this.buffer.splice(0, 120), sentAt: 0 });
      this.lastSeq = seq;
      seq += 1;
    }
  }

  /** كلُّ دفعةٍ لم يُقَرّ بها تُرسل بترتيبها — على المقبس؛ **وبلا مقبسٍ أقدمُها بـREST** */
  private flushPending() {
    if (!this.pending.length) return;
    if (this.open_()) {
      const now = Date.now();
      for (const batch of this.pending) {
        if (batch.sentAt && now - batch.sentAt < RESEND_MS) continue;
        if (this.send({ type: "locations", seq: batch.seq, points: batch.points })) batch.sentAt = now;
      }
      return;
    }
    if (this.restInFlight) return;
    const batch = this.pending[0];
    this.restInFlight = true;
    void reportPointsOverRest(batch)
      .then(() => this.acknowledge(batch.seq))
      .catch(() => undefined)
      .finally(() => {
        this.restInFlight = false;
      });
  }

  private acknowledge(seq: number | null) {
    this.pending = this.pending.filter((batch) => batch.seq !== seq);
  }

  private connect() {
    const token = tokens.access();
    if (!token || this.closed) return;

    const url = new URL(`${WS_URL}/driver`);
    url.searchParams.set("token", token);
    url.searchParams.set("device_id", deviceId());

    const socket = new WebSocket(url.toString());
    this.socket = socket;

    socket.onopen = () => {
      this.retries = 0;
      // **والمقبسُ الجديدُ يبدأ «أمامَ صاحبه»** عند الخلفية — فيُقال له الحالُ فوراً
      this.reportVisibility();
      // **وموقعُه الآن**: مقبسٌ جديدٌ لا حضورَ له حتى أوّلِ موقع — **وكلُّ دفعةٍ لم يُقَرّ بها تُعاد عليه**
      this.sent = null;
      this.sendLocation();
      for (const batch of this.pending) batch.sentAt = 0;
      onlineService.start();
      this.lastPulseAt = Date.now();
      this.options.onOpen?.();
    };

    socket.onmessage = (message) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(message.data) as Record<string, unknown>;
      } catch {
        // رسالةٌ تالفة لا تُسقط اتصالاً — الكبتن على الطريق
        return;
      }
      // **إطاراتُ البثّ تُستهلك هنا** ولا تصل الشاشة (§٧٥-ج)
      if (event.type === "connected" && event.broadcast) this.applyPolicy(event.broadcast as BroadcastPolicy);
      if (event.type === "broadcast_policy") {
        this.applyPolicy(event as unknown as BroadcastPolicy);
        return;
      }
      if (event.type === "location_request") {
        this.sendLocation();
        return;
      }
      if (event.type === "points_ack") {
        this.acknowledge((event.seq as number | null) ?? null);
        return;
      }
      this.options.onEvent(event as unknown as DriverSocketEvent);
    };

    socket.onclose = (event) => {
      this.socket = null;

      // رفضٌ لسببٍ لا يزول بالمحاولة: يُبلَّغ ولا يُعاد
      if (event.code === WS_UNAUTHORIZED || event.code === WS_FORBIDDEN) {
        this.closed = true;
        if (this.ticker !== null) window.clearInterval(this.ticker);
        this.ticker = null;
        this.options.onRejected?.(event.reason || tr("تعذّر بدء الاستقبال"));
        this.options.onClose?.(true);
        return;
      }

      this.options.onClose?.(this.closed);
      if (this.closed) return;

      // **سقط المقبس ⇒ REST فوراً** (SPEC §10) — والدورةُ نفسُها تختاره ناقلاً حين لا مقبس (`sendLocation` · `flushPending`):
      // كبتنٌ غيرُ مرئيٍّ لا تصله رحلة، **ونقاطُ رحلةٍ لا تنتظر عودةَ المقبس**
      this.sendLocation();

      const delay = Math.min(RETRY_BASE_MS * 2 ** this.retries, RETRY_MAX_MS);
      this.retries += 1;
      this.timer = window.setTimeout(() => this.connect(), delay);
    };

    socket.onerror = () => socket.close();
  }

  private applyPolicy(policy: BroadcastPolicy) {
    this.policy = { ...DEFAULT_POLICY, ...policy };
  }
}
