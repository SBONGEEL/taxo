/** حالةُ العمل: الاتصال، والعرض الوارد، والرحلة الجارية.
 *
 * **مصدرٌ واحد لحالة الكبتن أثناء العمل**، فوق الشاشات لا داخل واحدة: بطاقةُ
 * الطلب تصل على المقبس وقد يكون الكبتن في أي شاشة، والرحلة الجارية تسبق كل
 * شيء عند فتح التطبيق.
 *
 * ثلاث قواعد من SPEC القسم 10 تسكن هنا:
 *
 * - **الاسترجاع عبر REST عند كل اتصال**: رسالة `connected` تحمل الرحلة
 *   الجارية، فانقطاعٌ وعودة لا يتركان الشاشة على حالةٍ قديمة.
 * - **مهلةُ العرض عشرون ثانية**، ومصدرُها الخلفية (`expires_in_seconds`) لا
 *   رقمٌ مكتوبٌ هنا — القيمة قاعدةٌ في `services/dispatch.py` والاختبارات
 *   تضغطها، فرقمٌ ثابتٌ في الواجهة يفترق عنها.
 * - **العرض يسقط بانقضاء مهلته** بلا انتظار حدث: `offer_expired` قد لا يصل
 *   إن كان المقبس منقطعاً في تلك اللحظة بالضبط.
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
import { onlineService } from "@/lib/online-service";

import { getActiveRide, goOfflineOverRest, goOnlineOverRest } from "@/api/endpoints";
import type { Coordinates, Ride } from "@/api/types";
import type { CliqTransfer } from "@/components/CliqTransferSheet";
import { DriverSocket, type DriverSocketEvent } from "@/lib/socket";
import { useSession } from "@/lib/session";

/** حالاتُ الرحلة التي تعني «الكبتن مشغول الآن» — مرآةُ `ACTIVE_DRIVER_STATUSES`. */
const ACTIVE: ReadonlySet<string> = new Set([
  "accepted",
  "arrived",
  "in_progress",
  // الوقوفُ عند محطةٍ رحلةٌ جارية (المرحلة 12-ب) — ونقصُها هنا كان يُسقط
  // الرحلةَ من الشاشة فيعود الكبتن إلى «ابدأ الاستقبال» وهو واقفٌ بالراكب
  "at_stop",
]);

export function isActive(ride: Ride | null): ride is Ride {
  return ride !== null && ACTIVE.has(ride.status);
}

export interface Offer {
  ride: Ride;
  distanceKm: number;
  /** لحظةُ انتهاء المهلة — منها يُحسب العدّاد، فلا ينجرف مع إعادة الرسم. */
  expiresAt: number;
  totalSeconds: number;
}

interface RideState {
  online: boolean;
  connecting: boolean;
  ride: Ride | null;
  offer: Offer | null;
  /** حوالةُ كليك أدخل الراكب مرجعها وتنتظر قولَ الكبتن (القسم 6.2). */
  transfer: CliqTransfer | null;
  position: Coordinates | null;
  error: string | null;
  goOnline: () => void;
  goOffline: () => void;
  setRide: (ride: Ride | null) => void;
  dismissOffer: () => void;
  dismissTransfer: () => void;
  clearError: () => void;
}

const RideContext = createContext<RideState>({
  online: false,
  connecting: false,
  ride: null,
  offer: null,
  transfer: null,
  position: null,
  error: null,
  goOnline: () => undefined,
  goOffline: () => undefined,
  setRide: () => undefined,
  dismissOffer: () => undefined,
  dismissTransfer: () => undefined,
  clearError: () => undefined,
});

export function RideProvider({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const [online, setOnline] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [ride, setRide] = useState<Ride | null>(null);
  const [offer, setOffer] = useState<Offer | null>(null);
  const [transfer, setTransfer] = useState<CliqTransfer | null>(null);
  const [position, setPosition] = useState<Coordinates | null>(null);
  const [error, setError] = useState<string | null>(null);
  const socket = useRef<DriverSocket | null>(null);

  const handle = useCallback((event: DriverSocketEvent) => {
    switch (event.type) {
      case "connected":
        setRide(isActive(event.active_ride ?? null) ? event.active_ride : null);
        break;
      case "ride_offer":
        setOffer({
          ride: event.ride,
          distanceKm: event.distance_to_pickup_km,
          expiresAt: Date.now() + event.expires_in_seconds * 1_000,
          totalSeconds: event.expires_in_seconds,
        });
        break;
      case "offer_expired":
        setOffer(null);
        break;
      case "driver_assigned":
      case "driver_arrived":
      case "ride_started":
        setOffer(null);
        setRide(event.ride);
        break;
      case "ride_completed":
      case "ride_cancelled":
        setOffer(null);
        setRide(event.ride);
        break;
      case "cliq_transfer_submitted":
        setTransfer({
          rideId: event.ride_id,
          paymentId: event.payment_id,
          amount: event.amount,
          currency: event.currency,
          transferReference: event.transfer_reference,
          expiresAt: event.expires_at,
        });
        break;
      default:
        break;
    }
  }, []);

  const goOnline = useCallback(() => {
    if (socket.current || !user) return;
    setError(null);
    setConnecting(true);
    const client = new DriverSocket({
      onEvent: handle,
      onOpen: () => {
        setConnecting(false);
        setOnline(true);
        // **الخدمةُ تبدأ مع الاستقبال لا مع فتح التطبيق** (شرطُ المالك): لا
        // إشعارَ دائمٌ لكبتنٍ غيرِ عامل
        onlineService.start();
        // الاسترجاع عبر REST عند كل اتصال (القسم 10) — ورسالةُ `connected`
        // تحمل نفس اللقطة، فأيّهما وصل أولاً يصحّح الآخر
        getActiveRide()
          .then((active) => setRide(isActive(active) ? active : null))
          .catch(() => undefined);
      },
      onClose: (permanent) => {
        setOnline(false);
        // **والإشعارُ يقول أيَّ الحالين**: انقطاعٌ يُعاد وصلُه، أو انتهاءٌ.
        // **وصمتٌ هنا يترك كبتناً يظنّ نفسه مستقبِلاً وليس كذلك** — وهو
        // أخطرُ من ألّا يتصل أصلاً، لأنه يعدّ الصمتَ «لا طلبات اليوم»
        if (permanent) {
          setConnecting(false);
          socket.current = null;
          onlineService.stop();
          // **وانتهاءٌ يُنهي الحضورَ صراحةً** — فمقبسٌ أُغلق يترك
          // `drivers.is_online = true` وقد قِيس ذلك على الإنتاج: صفوفٌ تقول
          // «متصل» ولا مفتاحَ حضورٍ في Redis. **والعمودُ الذي يقول ما ليس
          // كذلك يُضلّل تقريراً يوماً ما.**
          void goOfflineOverRest().catch(() => undefined);
        } else {
          onlineService.degraded();
          // **بديلُ REST في اللحظة التي وُجد لها** (SPEC §10): المقبسُ سقط
          // وسيُعاد وصلُه، **والكبتنُ في هذه الأثناء غيرُ مرئيٍّ للتوزيع** —
          // فلا تصله رحلةٌ ويحسب الصمتَ «لا طلبات».
          //
          // **وكان مبنيّاً في الخلفية ومختبَراً ولا ينادِيه أحد** — بابٌ بلا
          // زرٍّ في أخطر موضع، ووصلُه هنا هو ما كان ناقصاً. **ولا يُفشِل
          // شيئاً**: فشلُه يعني أن الشبكةَ ساقطةٌ أصلاً، وإعادةُ الوصل هي
          // المخرجُ لا رسالةُ خطأٍ لمن لا يستطيع فعل شيء.
          void goOnlineOverRest().catch(() => undefined);
        }
      },
      onRejected: (reason) => {
        setError(reason);
        setConnecting(false);
      },
    });
    socket.current = client;
    client.open();
  }, [handle, user]);

  const goOffline = useCallback(() => {
    socket.current?.close();
    socket.current = null;
    onlineService.stop();
    setOnline(false);
    setConnecting(false);
    setOffer(null);
  }, []);

  // **الرحلة الجارية تُقرأ عند فتح التطبيق، لا عند فتح المقبس وحده.**
  //
  // كان الاسترجاع معلّقاً بـ`goOnline().onOpen` فقط، فكبتنٌ أُغلق تطبيقه وسط
  // رحلة يعود إلى شاشةٍ تعرض عليه «ابدأ الاستقبال» — كأنه فارغ — وراكبُه في
  // سيارته. ولا يستعيد رحلته إلا إن ضغط زرَّ الاستقبال، وهو آخرُ ما يخطر لمن
  // يظن أنه فقدها. وهذا ما كان سطرُ الوصف أعلى الملف يعِد به («والرحلة
  // الجارية تسبق كل شيء عند فتح التطبيق») ولا ينفّذه أحد.
  //
  // والنداءان لا يتعارضان: كلاهما يكتب نفس القيمة من نفس المصدر، وأيُّهما
  // وصل ثانياً كتب الأحدث.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getActiveRide()
      .then((active) => {
        if (!cancelled) setRide(isActive(active) ? active : null);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [user]);

  // الخروج من الحساب يغلق المقبس: مقبسٌ حيٌّ بعد الخروج يبقي الكبتن في
  // التوزيع وقد أغلق تطبيقه
  useEffect(() => {
    if (!user) goOffline();
  }, [user, goOffline]);

  useEffect(() => () => socket.current?.close(), []);

  // موقعُ الجهاز للخريطة — يُقرأ من المقبس نفسه فلا يُفتح مُراقبان
  useEffect(() => {
    if (!online) return;
    const timer = window.setInterval(() => {
      const fix = socket.current?.position();
      if (fix) {
        setPosition({ lat: fix.coords.latitude, lng: fix.coords.longitude });
      }
    }, 2_000);
    return () => window.clearInterval(timer);
  }, [online]);

  // العرض يسقط بانقضاء مهلته بلا انتظار حدث
  useEffect(() => {
    if (!offer) return;
    const remaining = offer.expiresAt - Date.now();
    if (remaining <= 0) {
      setOffer(null);
      return;
    }
    const timer = window.setTimeout(() => setOffer(null), remaining);
    return () => window.clearTimeout(timer);
  }, [offer]);

  const value = useMemo<RideState>(
    () => ({
      online,
      connecting,
      ride,
      offer,
      transfer,
      position,
      error,
      goOnline,
      goOffline,
      setRide,
      dismissOffer: () => setOffer(null),
      dismissTransfer: () => setTransfer(null),
      clearError: () => setError(null),
    }),
    [
      online,
      connecting,
      ride,
      offer,
      transfer,
      position,
      error,
      goOnline,
      goOffline,
    ],
  );

  return <RideContext.Provider value={value}>{children}</RideContext.Provider>;
}

export function useRide() {
  return useContext(RideContext);
}
