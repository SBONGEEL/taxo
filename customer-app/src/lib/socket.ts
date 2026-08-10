/** مقبس الراكب — `WS /ws/rider` (SPEC القسم 10).
 *
 * ثلاثة أشياء يفعلها هذا الملف ولا يفعلها غيره:
 *
 * - **يفتح المقبس بنفس `device_id`** الذي سجّل رمز الجهاز. بغيره يصل الحدث
 *   مرتين: على الشاشة ومن نظام التشغيل (SPEC القسم 10/11.8).
 * - **يرسل `viewport`**: الخلفية ترسم السيارات القريبة حول المركز الذي
 *   يرسله العميل، فبلا مركزٍ لا سيارات.
 * - **يعيد الاتصال تلقائياً بتباعدٍ متزايد**، ويترك للمستدعي استرجاع الحالة
 *   عبر REST عند كل اتصالٍ ناجح (القسم 10: «Reconnect تلقائي مع استرجاع آخر
 *   حالة عبر REST»).
 *
 * لا يقرأ التوكن من التخزين بنفسه: يأخذه دالةً، فيلتقط التوكن **المجدَّد**
 * عند كل محاولة اتصالٍ بدل أن يعيد المحاولة بتوكنٍ انتهى.
 */

import { WS_URL, tokens } from "@/api/client";
import { deviceId } from "@/lib/device";
import type { Coordinates, NearbyDriver, Ride } from "@/api/types";

export type SocketEvent =
  | { type: "connected"; active_ride: Ride | null }
  | { type: "nearby_drivers"; drivers: NearbyDriver[] }
  | { type: "driver_location"; driver_id: string; lat: number; lng: number; heading: number | null }
  | { type: "driver_assigned" | "driver_arrived" | "ride_started" | "ride_completed" | "ride_cancelled"; ride: Ride }
  | { type: "no_driver_found"; ride: Ride }
  | { type: "driver_connection_lost" | "driver_reconnected"; ride?: Ride }
  | { type: "error"; detail: string }
  | { type: string; [key: string]: unknown };

interface Options {
  onEvent: (event: SocketEvent) => void;
  /** يُستدعى بعد كل اتصالٍ ناجح — مكانُ الاسترجاع عبر REST. */
  onOpen?: () => void;
  onClose?: () => void;
}

const RETRY_BASE_MS = 1_000;
const RETRY_MAX_MS = 15_000;

export class RiderSocket {
  private socket: WebSocket | null = null;
  private retries = 0;
  private timer: number | null = null;
  private closed = false;
  private viewport: Coordinates | null = null;

  constructor(private readonly options: Options) {}

  open() {
    this.closed = false;
    this.connect();
  }

  close() {
    this.closed = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.socket?.close();
    this.socket = null;
  }

  /** مركز الخريطة الحالي — يُحفظ ويُعاد إرساله بعد كل إعادة اتصال. */
  setViewport(center: Coordinates) {
    this.viewport = center;
    this.send({ type: "viewport", lat: center.lat, lng: center.lng });
  }

  private send(payload: unknown) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  private connect() {
    const token = tokens.access();
    if (!token || this.closed) return;

    const url = new URL(`${WS_URL}/rider`);
    url.searchParams.set("token", token);
    // نفس المعرّف الذي سُجّل به رمز الجهاز — وإلا وصل الحدث مرتين
    url.searchParams.set("device_id", deviceId());

    const socket = new WebSocket(url.toString());
    this.socket = socket;

    socket.onopen = () => {
      this.retries = 0;
      if (this.viewport) this.setViewport(this.viewport);
      this.options.onOpen?.();
    };

    socket.onmessage = (message) => {
      try {
        this.options.onEvent(JSON.parse(message.data) as SocketEvent);
      } catch {
        // رسالةٌ تالفة لا تُسقط اتصالاً
      }
    };

    socket.onclose = () => {
      this.socket = null;
      this.options.onClose?.();
      if (this.closed) return;

      // تباعدٌ متزايد بسقف: خادمٌ متوقف لا يُقصف بمحاولةٍ كل ثانية
      const delay = Math.min(RETRY_BASE_MS * 2 ** this.retries, RETRY_MAX_MS);
      this.retries += 1;
      this.timer = window.setTimeout(() => this.connect(), delay);
    };

    socket.onerror = () => socket.close();
  }
}
