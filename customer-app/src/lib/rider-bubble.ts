/** **جسرُ فقاعة الراكب وودجته** (أمرُ المالك ٢٠/١١ الرابع، الجزءان ٢ و٣، SPEC §١١٠).
 *
 * **الفقاعةُ اختياريّة**: مفتاحُ السوق (`rider_bubble`) **واختيارُ الراكب** (`rider_bubble_user`)، وإذنُ «الظهور فوق التطبيقات» يُطلب
 * حين يُشعلها هو لا قبل. **والودجةُ خلف `rider_widgets_plus`**. وكلُّ ما يُكتب للطرف الأصليّ هنا: المفاتيحُ والطورُ والكابتنُ باسمه
 * الأوّل والمركبةُ والأماكنُ (أموجودةٌ أم لا) وأسماءُ الوجهات الأخيرة — **لا رقمَ هاتفٍ ولا إحداثيّةَ بيتٍ ولا مبلغ**.
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { API_URL, api, setAccessWriter, tokens } from "@/api/client";
import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { launcherAvailable } from "@/lib/launcher";
import { askPermission } from "@/lib/permissions-center";
import { riderBubbleRide, riderPhase, type BubbleRideInput } from "@/lib/rider-bubble-core";
import { thinRoute } from "@/lib/widget-core";

interface NativePrefs {
  setPrefs(options: Record<string, boolean | string | null>): Promise<void>;
}
interface NativeSession {
  remember(options: { base: string | null; token: string | null }): Promise<void>;
}

const native = registerPlugin<NativePrefs>("Launcher");
const session = registerPlugin<NativeSession>("RiderBubble");

const KEY = "taxo.rider.bubble";

export function riderBubbleChosen(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/** **يُشعلها الراكبُ من الإعدادات** — وحينها وحدَها يُسأل إذنُ الظهور فوق التطبيقات. */
export function setRiderBubbleChosen(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    // تخزينٌ محجوب — يُكتب للطرف الأصليّ وحدَه
  }
  if (!launcherAvailable()) return;
  void native.setPrefs({ rider_bubble_user: on }).catch(() => undefined);
  if (on) void askPermission("overlay").catch(() => undefined);
}

/** جلسةُ نداءَي الفقاعة (الردُّ السريع والطوارئ) — تُمحى بالخروج. */
export function setRiderBubbleSession(base: string | null, token: string | null): void {
  // الغلافُ الأقدمُ لا ملحقَ فيه — فلا نداءَ يسقط في السجلّ
  if (!launcherAvailable() || !Capacitor.isPluginAvailable("RiderBubble")) return;
  void session.remember({ base: token === null ? null : base, token }).catch(() => undefined);
}

interface Options {
  country: CountryCode | undefined;
  ride: BubbleRideInput | null;
  approachMinutes: number | null;
  places: { icon: string }[];
  recent: string[];
  /** **مسارُ الرحلة كما ترسمه الخريطة** (`[lng, lat]`) — لخريطة الودجة الصغيرة، و`null` بلا مسار. */
  routePoints?: number[][] | null;
}

/** **صورةُ الكبتن مصغّرةً للودجة** — من باب الرحلة نفسِه (`/rides/{id}/driver/photo`): المعتمَدةُ أو حرفُ الاسم بطولٍ ثابت،
 *  **فلا يصير غيابُها علامة**. ٩٦ بكسلاً JPEG، وفشلٌ ⇐ `null` (تبقى الدائرةُ الافتراضيّة). */
async function driverThumb(rideId: string): Promise<string | null> {
  try {
    const blob = await api.blob(`/rides/${rideId}/driver/photo`);
    const bitmap = await createImageBitmap(blob);
    const side = Math.min(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 96;
    canvas.getContext("2d")?.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, 96, 96);
    bitmap.close();
    const url = canvas.toDataURL("image/jpeg", 0.82);
    return url.startsWith("data:image/jpeg;base64,") ? url.slice("data:image/jpeg;base64,".length) : null;
  } catch {
    return null;
  }
}

export function useRiderBubbleBridge({ country, ride, approachMinutes, places, recent, routePoints = null }: Options): void {
  const bubble = useFeature(country, "rider_bubble");
  const widgets = useFeature(country, "rider_widgets_plus");
  const quick = useFeature(country, "quick_replies");
  const sos = useFeature(country, "bubble_sos");
  const editDest = useFeature(country, "destination_change_in_ride");
  // **أوّلُ وقت وصولٍ عُرف لهذه الرحلة** — منه تمتلئ حلقةُ الاقتراب
  const first = useRef<{ id: string; eta: number } | null>(null);
  if (ride && approachMinutes !== null && ride.status === "accepted" && first.current?.id !== ride.id) {
    first.current = { id: ride.id, eta: approachMinutes };
  }
  const etaFirst = ride && first.current?.id === ride.id ? first.current.eta : null;
  const rideJson = riderBubbleRide(ride, approachMinutes, etaFirst);
  const placesJson = JSON.stringify({
    home: places.some((place) => place.icon === "home"),
    work: places.some((place) => place.icon === "work"),
  });
  const recentJson = JSON.stringify(recent.slice(0, 3));

  useEffect(() => {
    if (!launcherAvailable()) return;
    void native
      .setPrefs({
        rider_bubble: bubble,
        rider_bubble_user: riderBubbleChosen(),
        rider_widgets_plus: widgets,
        quick_replies: quick,
        bubble_sos: sos,
        rider_edit_dest: editDest,
      })
      .catch(() => undefined);
  }, [bubble, widgets, quick, sos, editDest]);

  // **الرمزُ لا يُحفظ أصلياً إلا لمن أشعل الفقاعةَ والمفتاحُ مشتعل** — وإلا يُمحى
  const chosen = riderBubbleChosen();
  useEffect(() => {
    const wanted = bubble && chosen;
    const write = (access: string | null) => {
      setRiderBubbleSession(API_URL, wanted ? access : null);
      // **الودجةُ تعرف من دخل ومن خرج** — ولا تبقى رحلةُ من خرج ولا أماكنُه على الشاشة الرئيسيّة
      if (!launcherAvailable()) return;
      void native
        .setPrefs(
          access === null
            ? { signed_in: false, rider_ride: null, rider_recent: null, rider_places: null, w_feed: null, rider_ride_photo: null, rider_ride_route: null }
            : { signed_in: true },
        )
        .catch(() => undefined);
    };
    write(tokens.access());
    setAccessWriter(write);
  }, [bubble, chosen]);

  useEffect(() => {
    if (!launcherAvailable()) return;
    void native.setPrefs({ rider_ride: rideJson, rider_places: placesJson, rider_recent: recentJson }).catch(() => undefined);
  }, [rideJson, placesJson, recentJson]);

  // **صورةُ الكبتن ومسارُ الرحلة في الودجة** (أمرُ المالك ٢١/١١) — **أثناء الرحلة وحدَها** وخلف `rider_widgets_plus`، وتُمحى بانتهائها
  const liveId = widgets && ride && ride.driver && riderPhase(ride.status) !== null && riderPhase(ride.status) !== "searching" ? ride.id : null;
  const routeJson = liveId ? (() => {
    const pts = thinRoute(routePoints);
    return pts ? JSON.stringify({ id: liveId, pts }) : null;
  })() : null;
  useEffect(() => {
    if (!launcherAvailable()) return;
    void native.setPrefs({ rider_ride_route: routeJson }).catch(() => undefined);
  }, [routeJson]);
  useEffect(() => {
    if (!launcherAvailable()) return;
    if (!liveId) {
      void native.setPrefs({ rider_ride_photo: null }).catch(() => undefined);
      return;
    }
    let cancelled = false;
    void driverThumb(liveId).then((b64) => {
      if (cancelled) return;
      void native.setPrefs({ rider_ride_photo: b64 ? JSON.stringify({ id: liveId, b64 }) : null }).catch(() => undefined);
    });
    return () => {
      cancelled = true;
    };
  }, [liveId]);
}
