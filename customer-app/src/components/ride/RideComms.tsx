/** **وصلُ طبقة المحادثة والمكالمة بتطبيق الراكب** (SPEC §٦٦) — ما يخصّ الراكبَ وحدَه، والطبقةُ نفسُها في `lib/comms.tsx`.
 *
 * - **الطرفُ الآخر هو الكبتن باسمه ومركبته ولوحته** — كما يراه في بطاقة R08 اليوم، من الرحلة نفسِها (`ride.driver`).
 * - **والمقبسُ مقبسُ الرحلة القائم** (`useRide().connected`) — الإشارةُ تصل منه، ولا مقبسَ ثانٍ.
 * - **والبلاغُ الصغيرُ بلاغُ التطبيق بصوته** (`notify` و`notify.mp3`) — **ومرّةً لا مرّتين** (`firstSighting`): إشعارُ
 *   «مكالمةٌ فائتة» قد يصل على المقبس بعد أن قالتها الطبقة.
 * - **ونقرةُ إشعار النظام في الغلاف** (`pushNotificationActionPerformed`): لم يكن للراكب مستمعٌ لها قبل هذا — فيُصغى هنا
 *   **لأنواع المحادثة والمكالمة وحدها**، وما عداها كما كان.
 */

import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";
import { useCallback, useEffect, useMemo } from "react";
import type { ReactNode } from "react";

import { DriverAvatar } from "@/components/ride/DriverAvatar";
import { CommsProvider, inCommsWindow, type CommsPeer } from "@/lib/comms";
import { firstSighting } from "@/lib/notice";
import { useRide } from "@/lib/ride";
import { play } from "@/lib/sound";
import { routeCommsPush } from "@/lib/trip-comms";
import { CommsLayerT2 } from "@/screens/t2/CommsT2";

export function RideComms({ children }: { children: ReactNode }) {
  const { ride, connected, notify } = useRide();

  const driver = ride && inCommsWindow(ride) ? ride.driver : null;
  const peer = useMemo<CommsPeer | null>(() => {
    if (!ride || !driver) return null;
    const vehicle = driver.vehicle;
    return {
      name: driver.name,
      meta: vehicle ? `${vehicle.make} ${vehicle.model}` : null,
      plate: vehicle?.plate_number ?? null,
      avatar: <DriverAvatar rideId={ride.id} name={driver.name} />,
    };
  }, [ride, driver]);

  const toast = useCallback(
    (title: string, body?: string) => {
      if (!firstSighting(title, body)) return;
      notify(title, body);
      play("notify");
    },
    [notify],
  );

  // **نقرةُ إشعار الويب وفتحت نافذةً جديدة** (`public/firebase-messaging-sw.js`): الحمولةُ في الرابط — تُسلَّم مرّةً وتُمحى منه
  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const type = query.get("comms");
    const rideId = query.get("ride");
    if (!type || !rideId) return;
    const data: Record<string, string> = { type, ride_id: rideId };
    const callId = query.get("call");
    if (callId) data.call_id = callId;
    window.history.replaceState(window.history.state, "", window.location.pathname);
    routeCommsPush(data, "tap");
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let handle: { remove: () => Promise<void> } | null = null;
    void PushNotifications.addListener("pushNotificationActionPerformed", (item) => {
      routeCommsPush((item.notification.data ?? {}) as Record<string, string>, "tap");
    }).then((listener) => {
      handle = listener;
    });
    return () => void handle?.remove();
  }, []);

  return (
    <CommsProvider side="rider" ride={ride} peer={peer} live={connected} toast={toast}>
      {children}
      <CommsLayerT2 />
    </CommsProvider>
  );
}
