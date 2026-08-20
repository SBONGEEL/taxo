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
 * - **يبثّ الموقع كل ثلاث ثوانٍ** — وهو ما يجعل الكبتن مرئياً للتوزيع أصلاً:
 *   `is_online` وحده لا يكفي، أول بثِّ موقعٍ هو ما يُدخله الفهرس.
 * - **يعيد الاتصال بتباعدٍ متزايد**، ويترك للمستدعي استرجاع الحالة عبر REST
 *   عند كل اتصالٍ ناجح.
 *
 * ولا يقرأ التوكن من التخزين بنفسه: يأخذه عند كل محاولة، فيلتقط المجدَّد بدل
 * أن يعيد المحاولة بتوكنٍ انتهى.
 */

import { WS_URL, tokens } from "@/api/client";
import { reportLocationOverRest } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { deviceId } from "@/lib/device";

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
// السقف نفسه الذي يفترضه القسم 10: الحضور في Redis عمره 60 ثانية
export const LOCATION_INTERVAL_MS = 3_000;

/** فترةُ بديل REST — **أوسعُ من فترة المقبس ولا تُقارَب مهلةَ الحضور**.
 *
 * إطارُ مقبسٍ كلَّ ثلاث ثوانٍ رخيص؛ وطلبُ HTTP كاملٌ بمثلها يستهلك بطاريةً
 * وحزمةً على طريقٍ ضعيف. ومفتاحُ `geo:presence:{driver_id}` عمرُه **٦٠ ثانية**،
 * فالعشرُ تُبقيه حيّاً بستّة أضعافِ هامش — ولو قاربناها لَاختفى الكبتنُ من
 * الخريطة بين طلبين على شبكةٍ متعثّرة.
 */
export const REST_FALLBACK_INTERVAL_MS = 10_000;

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
  /** مؤقّتُ بديل REST — يعمل **فقط** حين لا مقبس، ويتوقف حين يعود. */
  private fallbackTicker: number | null = null;
  private fallbackInFlight = false;

  constructor(private readonly options: Options) {}

  open() {
    this.closed = false;
    this.startWatching();
    this.connect();
  }

  close() {
    this.closed = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    if (this.ticker !== null) window.clearInterval(this.ticker);
    if (this.watch !== null) navigator.geolocation?.clearWatch(this.watch);
    this.stopFallback();
    this.timer = this.ticker = this.watch = null;
    this.socket?.close();
    this.socket = null;
  }

  /** آخر موقعٍ معروف — ترسمه الخريطة قبل أول بثّ. */
  position(): GeolocationPosition | null {
    return this.last;
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
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 10_000 },
    );
  }

  private send(payload: unknown) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private broadcast() {
    const position = this.last;
    if (!position) return;
    this.send({
      type: "location",
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      // `heading` غائبٌ على أجهزةٍ ثابتة، و`null` أصدقُ من صفرٍ يعني «شمالاً»
      heading: Number.isFinite(position.coords.heading)
        ? position.coords.heading
        : null,
    });
  }

  /** يبدأ البثَّ عبر REST — ولا يُشغَّل مؤقّتان. */
  private startFallback() {
    if (this.fallbackTicker !== null || this.closed) return;
    void this.pushOverRest();
    this.fallbackTicker = window.setInterval(
      () => void this.pushOverRest(),
      REST_FALLBACK_INTERVAL_MS,
    );
  }

  private stopFallback() {
    if (this.fallbackTicker !== null) window.clearInterval(this.fallbackTicker);
    this.fallbackTicker = null;
  }

  /** **ولا يتراكم**: طلبٌ بطيءٌ على شبكةٍ ضعيفةٍ لا يُتبَع بآخرَ فوقه. */
  private async pushOverRest(): Promise<void> {
    const position = this.last;
    if (!position || this.fallbackInFlight || this.closed) return;
    this.fallbackInFlight = true;
    try {
      await reportLocationOverRest({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        heading: Number.isFinite(position.coords.heading)
          ? position.coords.heading
          : null,
      });
    } catch {
      // **وفشلُه صامت**: الشبكةُ هي التي سقطت أصلاً، ورسالةُ خطأٍ كلَّ عشر
      // ثوانٍ على شاشة كبتنٍ يقود ضجيجٌ لا خبر
    } finally {
      this.fallbackInFlight = false;
    }
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
      // **والعودةُ تُطفئ البديل**: مقبسٌ وREST معاً بثٌّ مضاعفٌ لموقعٍ واحد
      this.stopFallback();
      this.broadcast();
      if (this.ticker !== null) window.clearInterval(this.ticker);
      this.ticker = window.setInterval(
        () => this.broadcast(),
        LOCATION_INTERVAL_MS,
      );
      this.options.onOpen?.();
    };

    socket.onmessage = (message) => {
      try {
        this.options.onEvent(JSON.parse(message.data) as DriverSocketEvent);
      } catch {
        // رسالةٌ تالفة لا تُسقط اتصالاً — الكبتن على الطريق
      }
    };

    socket.onclose = (event) => {
      this.socket = null;
      if (this.ticker !== null) window.clearInterval(this.ticker);
      this.ticker = null;

      // رفضٌ لسببٍ لا يزول بالمحاولة: يُبلَّغ ولا يُعاد
      if (event.code === WS_UNAUTHORIZED || event.code === WS_FORBIDDEN) {
        this.closed = true;
        this.options.onRejected?.(event.reason || "تعذّر بدء الاستقبال");
        this.options.onClose?.(true);
        return;
      }

      this.options.onClose?.(this.closed);
      if (this.closed) return;

      // **سقط المقبس ⇒ يُشتغَّل بديلُ REST فوراً** (SPEC §10). كبتنٌ غيرُ
      // مرئيٍّ لا تصله رحلة: يخسر دخلَه ويخسر الراكبُ سيارة. والبديلُ كان
      // مبنيّاً في الخلفية ومختبَراً **ولا ينادِيه أحد** — بابٌ بلا زرّ في
      // أخطر موضع.
      //
      // **وفترتُه أوسع من فترة المقبس**: طلبٌ كاملٌ كلَّ ثلاث ثوانٍ يستهلك
      // بطاريةً وحزمةً على طريقٍ ضعيف، ومفتاحُ الحضور في Redis عمرُه ٦٠ ثانية
      // — فما دون ذلك يُبقيه حيّاً بأمانٍ كافٍ.
      this.startFallback();

      const delay = Math.min(RETRY_BASE_MS * 2 ** this.retries, RETRY_MAX_MS);
      this.retries += 1;
      this.timer = window.setTimeout(() => this.connect(), delay);
    };

    socket.onerror = () => socket.close();
  }
}
