/** **جسرُ الفقاعة الجديدة** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — ما تقرؤه الفقاعةُ والقائمةُ الدائريّةُ والودجةُ الأصليّةُ في الكبتن.
 *
 * **كلُّ بندٍ بمفتاحه لدولته**، ويُكتب إلى `taxo_launcher` في كلِّ تغيّر — مطفأً يعود كلُّ شيءٍ كما كان. **ولا رقمَ مالٍ يُحسب هنا**:
 * الأرباحُ والأيّامُ تقرؤها الفقاعةُ من الخادم بحرفها، والهدفُ اليوميُّ **رقمٌ يكتبه الكبتنُ لنفسه** ويُقارن للعرض وحدَه.
 * **والغلافُ الأقدمُ لا ملحقَ فيه** (`launcherAvailable`) — فلا شيءَ يُنادى.
 */
import { useEffect } from "react";
import { registerPlugin } from "@capacitor/core";

import type { CountryCode, Ride } from "@/api/types";
import { useFeature } from "@/lib/config";
import { launcherAvailable } from "@/lib/launcher";
import { bubbleRide, cleanGoal } from "@/lib/bubble-core";

export { bubbleRide, cleanGoal };

interface NativePrefs {
  setPrefs(options: Record<string, boolean | string | null>): Promise<void>;
}

const native = registerPlugin<NativePrefs>("Launcher");

/** مفاتيحُ الفقاعة كما يقرؤها `DriverBubbleMenu.FLAGS` و`OfferVoice` و`DriverWidget` — **بحرفها**. */
export const BUBBLE_FLAGS = [
  "bubble_radial_menu",
  "bubble_online_toggle",
  "bubble_today_card",
  "driver_break",
  "bubble_busy_area",
  "bubble_last_ride",
  "bubble_goal_ring",
  "bubble_subscription_ring",
  "bubble_ride_panel",
  "quick_replies",
  "bubble_wait_counter",
  "bubble_road_report",
  "map_road_reports",
  "bubble_sos",
  "voice_offer_answer",
  "driver_widgets_plus",
] as const;

export type BubbleSize = "s" | "m" | "l";
export type BubbleAlpha = "100" | "80" | "60";

export interface BubbleSettings {
  size: BubbleSize;
  alpha: BubbleAlpha;
  snap: boolean;
  /** هدفُ اليوم نصّاً كما كتبه (`"25"`)، و`""` بلا هدف — **للعرض وحدَه** */
  goal: string;
  voice: boolean;
}

const KEY = "taxo.bubble.settings";
export const DEFAULT_SETTINGS: BubbleSettings = { size: "m", alpha: "100", snap: true, goal: "", voice: false };


export function readSettings(): BubbleSettings {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<BubbleSettings>;
    return {
      size: raw.size === "s" || raw.size === "l" ? raw.size : "m",
      alpha: raw.alpha === "80" || raw.alpha === "60" ? raw.alpha : "100",
      snap: raw.snap !== false,
      goal: typeof raw.goal === "string" ? cleanGoal(raw.goal) : "",
      voice: raw.voice === true,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function pushSettings(s: BubbleSettings): void {
  if (!launcherAvailable()) return;
  void native
    .setPrefs({
      bubble_size: s.size,
      bubble_alpha: s.alpha,
      bubble_snap: s.snap,
      bubble_goal: s.goal === "" ? null : s.goal,
      voice_offer_user: s.voice,
    })
    .catch(() => undefined);
}

export function saveSettings(next: BubbleSettings): BubbleSettings {
  const clean = { ...next, goal: cleanGoal(next.goal) };
  try {
    localStorage.setItem(KEY, JSON.stringify(clean));
  } catch {
    // تخزينٌ محجوب — يُكتب للطرف الأصليّ وحدَه
  }
  pushSettings(clean);
  return clean;
}

/** **دخل أو خرج** — الودجةُ تقول «سجّل الدخول» لمن خرج، ولا تعرض حالَ حسابٍ سابق. */
export function setSignedIn(on: boolean): void {
  if (!launcherAvailable()) return;
  const cleared: Record<string, boolean | string | null> = { signed_in: on };
  if (!on) {
    // **لا يبقى رقمُ من خرج على الشاشة الرئيسيّة**
    for (const key of ["today_earned", "today_rides", "today_minutes", "sub_days", "busy_json", "bubble_ride", "break_until", "quick_json"]) {
      cleared[key] = null;
    }
  }
  void native.setPrefs(cleared).catch(() => undefined);
}


interface Options {
  country: CountryCode | undefined;
  ride: Pick<Ride, "id" | "status" | "arrived_at" | "pickup" | "dropoff"> | null;
  currencyLabel: string | null;
  breakUntil: string | null;
}

export function useBubbleBridge({ country, ride, currencyLabel, breakUntil }: Options): void {
  // نداءٌ صريحٌ لكلِّ مفتاح — بترتيب `BUBBLE_FLAGS` نفسِه (والاختبارُ يقارن الطولين)
  const values = [
    useFeature(country, "bubble_radial_menu"),
    useFeature(country, "bubble_online_toggle"),
    useFeature(country, "bubble_today_card"),
    useFeature(country, "driver_break"),
    useFeature(country, "bubble_busy_area"),
    useFeature(country, "bubble_last_ride"),
    useFeature(country, "bubble_goal_ring"),
    useFeature(country, "bubble_subscription_ring"),
    useFeature(country, "bubble_ride_panel"),
    useFeature(country, "quick_replies"),
    useFeature(country, "bubble_wait_counter"),
    useFeature(country, "bubble_road_report"),
    useFeature(country, "map_road_reports"),
    useFeature(country, "bubble_sos"),
    useFeature(country, "voice_offer_answer"),
    useFeature(country, "driver_widgets_plus"),
  ];
  const rideJson = bubbleRide(ride);
  const flagsKey = values.map((on) => (on ? "1" : "0")).join("");

  useEffect(() => {
    if (!launcherAvailable()) return;
    const prefs: Record<string, boolean | string | null> = { signed_in: true };
    BUBBLE_FLAGS.forEach((key, i) => (prefs[key] = values[i]));
    void native.setPrefs(prefs).catch(() => undefined);
    pushSettings(readSettings());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- البصمةُ تجمع المفاتيح
  }, [flagsKey]);

  useEffect(() => {
    if (!launcherAvailable()) return;
    void native
      .setPrefs({ bubble_ride: rideJson, currency_label: currencyLabel, break_until: breakUntil })
      .catch(() => undefined);
  }, [rideJson, currencyLabel, breakUntil]);
}
