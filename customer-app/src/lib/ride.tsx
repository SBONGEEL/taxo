/** حالة الرحلة الجارية والسيارات القريبة — مصدرٌ واحد للشاشتين.
 *
 * الشاشة الرئيسية وشاشة التتبع تقرآن نفس الرحلة ونفس المقبس؛ ومقبسان لحسابٍ
 * واحد يعنيان بثَّ جيرانٍ مضاعفاً وأثرَي حضورٍ متضاربين في Redis. فالمقبس
 * يُفتح هنا مرةً ويعيش ما دام المستخدم داخلاً.
 *
 * و**الاسترجاع بعد الانقطاع عبر REST** كما ينص القسم 10: كل اتصالٍ ناجح يتبعه
 * `GET /rides/me/active` — لأن ما فات أثناء الانقطاع لا يُبثّ ثانيةً.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { getActiveRide } from "@/api/endpoints";
import type { Coordinates, NearbyDriver, Ride } from "@/api/types";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { onForegroundMessage } from "@/lib/firebase";
import { ACTIVE_RIDE_STATUSES } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { RiderSocket, type SocketEvent } from "@/lib/socket";

export interface DriverPing {
  lat: number;
  lng: number;
  heading: number | null;
}

/** ما يصل والتطبيق مفتوح: لا يعرضه المتصفح، فيُعرض داخل الشاشة. */
export interface Toast {
  id: number;
  title: string;
  body?: string;
}

interface RideState {
  ride: Ride | null;
  drivers: NearbyDriver[];
  driverPing: DriverPing | null;
  connected: boolean;
  toasts: Toast[];
  dismissToast: (id: number) => void;
  notify: (title: string, body?: string) => void;
  setViewport: (center: Coordinates) => void;
  /** يعيد قراءة الرحلة الجارية من REST — بعد طلبٍ أو إلغاءٍ أو دفع. */
  refresh: () => Promise<Ride | null>;
  /** يثبّت رحلةً عرفتها الشاشة قبل أن يصل بثُّها. */
  setRide: (ride: Ride | null) => void;
}

const RideContext = createContext<RideState>({
  ride: null,
  drivers: [],
  driverPing: null,
  connected: false,
  toasts: [],
  dismissToast: () => undefined,
  notify: () => undefined,
  setViewport: () => undefined,
  refresh: async () => null,
  setRide: () => undefined,
});

const TERMINAL_EVENTS = new Set([
  "ride_completed",
  "ride_cancelled",
  "no_driver_found",
]);

const EVENT_TOAST: Record<string, { title: string; body?: string }> = {
  driver_assigned: { title: "قَبِل كبتنٌ رحلتك", body: "هو الآن في طريقه إليك" },
  driver_arrived: { title: "وصل الكبتن", body: "الكبتن بانتظارك في نقطة الانطلاق" },
  ride_started: { title: "بدأت الرحلة", body: "رحلة موفقة" },
  ride_completed: { title: "انتهت الرحلة", body: "شاشة الدفع بانتظارك" },
  ride_cancelled: { title: "أُلغيت الرحلة" },
  no_driver_found: {
    title: "لم نجد كبتناً متاحاً",
    body: "لم يقبل أي كبتن الطلب — حاول مرة أخرى",
  },
  driver_connection_lost: {
    title: "انقطع اتصال الكبتن",
    body: "الرحلة مستمرة — نحاول استعادة موقعه",
  },
  driver_reconnected: { title: "عاد اتصال الكبتن" },
};

export function RideProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const { config } = useConfig();
  const [ride, setRide] = useState<Ride | null>(null);
  const [drivers, setDrivers] = useState<NearbyDriver[]>([]);
  const [driverPing, setDriverPing] = useState<DriverPing | null>(null);
  const [connected, setConnected] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const socket = useRef<RiderSocket | null>(null);
  const toastId = useRef(0);

  const notify = useCallback((title: string, body?: string) => {
    const id = ++toastId.current;
    setToasts((current) => [...current, { id, title, body }]);
    window.setTimeout(
      () => setToasts((current) => current.filter((toast) => toast.id !== id)),
      6_000,
    );
  }, []);

  const dismissToast = useCallback(
    (id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)),
    [],
  );

  const refresh = useCallback(async () => {
    const active = await getActiveRide().catch(() => null);
    setRide(active);
    if (!active?.driver) setDriverPing(null);
    return active;
  }, []);

  const onEvent = useCallback(
    (event: SocketEvent) => {
      switch (event.type) {
        case "connected":
          setRide((event as { active_ride: Ride | null }).active_ride);
          return;

        case "nearby_drivers":
          setDrivers((event as { drivers: NearbyDriver[] }).drivers);
          return;

        case "driver_location": {
          const ping = event as unknown as DriverPing;
          setDriverPing({ lat: ping.lat, lng: ping.lng, heading: ping.heading });
          return;
        }

        case "error":
          return;

        default: {
          const withRide = event as { ride?: Ride };
          if (withRide.ride) {
            // الحدث النهائي يترك الرحلة معروضةً: شاشة الدفع والتقييم تبنيان
            // عليها، وتنظيفُها من هنا يمسح ما جاء المستخدم لأجله
            setRide(withRide.ride);
          }
          if (TERMINAL_EVENTS.has(event.type)) setDriverPing(null);

          const toast = EVENT_TOAST[event.type];
          if (toast) {
            // «لم نجد كبتناً» على طلبٍ نسائي يحتاج سببَه: نصٌّ عامّ يقول
            // «لم يقبل أحد» يُقرأ رفضاً شخصياً، والصحيحُ أن المتاحات كنّ
            // بعيداتٍ أو مشغولات — ومعه المخرجُ الفعلي (المرحلة 10-ج)
            const gendered =
              withRide.ride && withRide.ride.gender_preference !== "any";
            if (event.type === "no_driver_found" && gendered) {
              notify(
                "لم نجد كبتنة متاحة",
                "لا كبتنة قريبة الآن. جرّبي بعد قليل، أو اطلبي أي كبتن.",
              );
            } else {
              notify(toast.title, toast.body);
            }
          }
        }
      }
    },
    [notify],
  );

  useEffect(() => {
    if (!user) {
      socket.current?.close();
      socket.current = null;
      setRide(null);
      setDrivers([]);
      setDriverPing(null);
      setConnected(false);
      return;
    }

    const instance = new RiderSocket({
      onEvent,
      onOpen: () => {
        setConnected(true);
        // ما فات أثناء الانقطاع لا يُبثّ ثانيةً (SPEC القسم 10)
        void refresh();
      },
      onClose: () => setConnected(false),
    });
    instance.open();
    socket.current = instance;

    return () => {
      instance.close();
      socket.current = null;
    };
  }, [user, onEvent, refresh]);

  // إشعارٌ يصل والتطبيق مفتوح لا يعرضه المتصفح (SPEC القسم 10) — فيُعرض هنا
  useEffect(() => {
    if (!user) return;
    const fcm = firebaseConfigOf(config?.providers.fcm);
    if (!fcm) return;

    let unsubscribe: (() => void) | null = null;
    onForegroundMessage(fcm, (payload) => {
      if (payload.title) notify(payload.title, payload.body);
    })
      .then((off) => (unsubscribe = off))
      .catch(() => undefined);

    return () => unsubscribe?.();
  }, [user, config, notify]);

  const setViewport = useCallback((center: Coordinates) => {
    socket.current?.setViewport(center);
  }, []);

  const value = useMemo<RideState>(
    () => ({
      ride,
      drivers,
      driverPing,
      connected,
      toasts,
      dismissToast,
      notify,
      setViewport,
      refresh,
      setRide,
    }),
    [ride, drivers, driverPing, connected, toasts, dismissToast, notify, setViewport, refresh],
  );

  return <RideContext.Provider value={value}>{children}</RideContext.Provider>;
}

export function useRide() {
  return useContext(RideContext);
}

export function isActive(ride: Ride | null): boolean {
  return ride !== null && ACTIVE_RIDE_STATUSES.includes(ride.status);
}
