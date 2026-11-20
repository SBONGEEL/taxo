/** **جسرُ فقاعة الراكب وودجته** (أمرُ المالك ٢٠/١١ الرابع، الجزءان ٢ و٣، SPEC §١١٠).
 *
 * **الفقاعةُ اختياريّة**: مفتاحُ السوق (`rider_bubble`) **واختيارُ الراكب** (`rider_bubble_user`)، وإذنُ «الظهور فوق التطبيقات» يُطلب
 * حين يُشعلها هو لا قبل. **والودجةُ خلف `rider_widgets_plus`**. وكلُّ ما يُكتب للطرف الأصليّ هنا: المفاتيحُ والطورُ والكابتنُ باسمه
 * الأوّل والمركبةُ والأماكنُ (أموجودةٌ أم لا) وأسماءُ الوجهات الأخيرة — **لا رقمَ هاتفٍ ولا إحداثيّةَ بيتٍ ولا مبلغ**.
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { API_URL, setAccessWriter, tokens } from "@/api/client";
import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { launcherAvailable } from "@/lib/launcher";
import { askPermission } from "@/lib/permissions-center";
import { riderBubbleRide, type BubbleRideInput } from "@/lib/rider-bubble-core";

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
}

export function useRiderBubbleBridge({ country, ride, approachMinutes, places, recent }: Options): void {
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
        .setPrefs(access === null ? { signed_in: false, rider_ride: null, rider_recent: null, rider_places: null, w_feed: null } : { signed_in: true })
        .catch(() => undefined);
    };
    write(tokens.access());
    setAccessWriter(write);
  }, [bubble, chosen]);

  useEffect(() => {
    if (!launcherAvailable()) return;
    void native.setPrefs({ rider_ride: rideJson, rider_places: placesJson, rider_recent: recentJson }).catch(() => undefined);
  }, [rideJson, placesJson, recentJson]);
}
