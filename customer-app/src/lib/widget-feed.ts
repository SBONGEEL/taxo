/** **ودجاتُ الراكب الأربعَ عشرة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن) — ما تعرضه يُكتب هنا **من أبوابه الحقيقيّة وحدَها**، والطرفُ الأصليُّ
 *  (`TaxoWidgets.java`) يرسم ولا يحسب.
 *
 *  **لا رقمَ مخترَع**: ما لا مصدرَ له `null` فتعرض الودجةُ فراغاً لطيفاً أو لا تُدرج في قائمة الودجات أصلاً (`kinds`). **ولا رحلةَ من
 *  الودجة**: كلُّ زرٍّ فيها يفتح التطبيقَ على ورقة الطلب أو الشاشة، والراكبُ يؤكّد. **ولا رقمَ هاتفٍ ولا اسمَ كبتن** — الرحلةُ الحيّةُ في
 *  `rider_ride` كما كانت. خلف `rider_widgets_plus` ومفاتيح البلد، **ومن خرج تُمحى بياناتُه** مع `signed_in`.
 *
 *  ويُكتب **حين يُفتح التطبيقُ ويعود إلى الواجهة** — لا مؤقّتَ في الخلفيّة (البطارية)، **و`at` وقتُه** فتقول الودجةُ «حتى ٢١:٣٠». */
import { useEffect } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { getMyLoyalty, getStorefront, getWallet, listBookings, listMyRides, type MyLoyalty } from "@/api/endpoints";
import type { Booking, CountryCode, PromoBanner, RideListItem, ServiceTile, Wallet } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { currencyLabel, digits, formatAmount } from "@/lib/utils";
import { carKey, type CarKey } from "@/taxo2/cars";

interface NativePrefs {
  setPrefs(options: Record<string, boolean | string | null>): Promise<void>;
}
const native = registerPlugin<NativePrefs>("Launcher");

/** أنواعُ الودجات — **وما لا يُدرج منها لا يظهر في قائمة الودجات** (`setComponentEnabledSetting` في الطرف الأصليّ). */
export const WIDGET_KINDS = [
  "request", "on_the_way", "quick", "favorites", "wallet", "discount", "schedule", "services",
  "current", "home", "work", "points", "recent", "offers", "nearest",
] as const;
export type WidgetKind = (typeof WIDGET_KINDS)[number];

export interface WidgetFeed {
  /** وقتُ الكتابة (مللي) — والودجةُ تقول «حتى …» بساعة الجهاز. */
  at: number;
  wallet: { amount: string; unit: string } | null;
  points: { points: string; tier: string; pct: number } | null;
  booking: { when: string; to: string } | null;
  last: { when: string; to: string; car: CarKey } | null;
  /** لافتاتُ المشرف للراكب — **العنوانُ والرقمُ الكبيرُ كما كتبهما المشرف**، لا نسبةٌ تُؤلَّف هنا. */
  offers: { count: number; title: string | null; headline: string | null };
  services: { title: string; go: string }[];
  /** أقربُ كبتنٍ متاحٍ بالدقائق من نقطة الرئيسيّة — و`null` حيث لا جواب. */
  nearest: number | null;
}

const TIER: Record<MyLoyalty["tier"], string> = { bronze: "برونزيّ", silver: "فضّيّ", gold: "ذهبيّ" };
const DAY = new Intl.DateTimeFormat("ar-u-nu-latn", { weekday: "long" });
const TIME = new Intl.DateTimeFormat("ar-u-nu-latn", { hour: "2-digit", minute: "2-digit", hour12: false });

function when(iso: string): string {
  const date = new Date(iso);
  return `${DAY.format(date)} ${digits(TIME.format(date))}`;
}

/** **أوّلُ مقطعٍ من العنوان** — «جبل عمّان، شارع …» يصير «جبل عمّان»: الودجةُ سطرٌ واحد. */
function shortPlace(address: string | null | undefined): string {
  return (address ?? "").split(/[،,]/)[0]?.trim() ?? "";
}

/** **مسارٌ داخليٌّ مقبول** — وجهةُ بلاطةٍ يكتبها المشرف تصير فعلاً `go:/…` لا رابطاً خارجيّاً. */
export function internalPath(destination: string | null | undefined): string | null {
  return destination && /^\/[a-z0-9/_-]*$/.test(destination) ? destination : null;
}

export interface FeedInputs {
  now: number;
  wallet: Wallet | null;
  loyalty: MyLoyalty | null;
  bookings: Booking[] | null;
  rides: RideListItem[] | null;
  tiles: ServiceTile[];
  banners: PromoBanner[];
  nearest: number | null;
}

/** خالصٌ ومختبَر. */
export function buildWidgetFeed(input: FeedInputs): WidgetFeed {
  const loyalty = input.loyalty?.enabled ? input.loyalty : null;
  const year = loyalty?.year_points ?? 0;
  const toNext = loyalty?.to_next ?? null;
  const upcoming = (input.bookings ?? [])
    .filter((row) => row.status === "pending" && Date.parse(row.scheduled_at) > input.now)
    .sort((a, b) => Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at))[0];
  const done = (input.rides ?? []).find((row) => row.ride.status === "completed" && row.ride.completed_at);
  const withHeadline = input.banners.find((banner) => banner.headline);
  return {
    at: input.now,
    wallet: input.wallet ? { amount: formatAmount(input.wallet.balance, input.wallet.currency), unit: currencyLabel(input.wallet.currency) } : null,
    points: loyalty
      ? {
          points: digits(String(loyalty.points)),
          tier: tr(TIER[loyalty.tier]),
          // **التقدّمُ إلى المستوى التالي من رقمَي الخلفيّة** — والذهبيُّ (لا تالي) حلقةٌ كاملة
          pct: toNext === null ? 1 : year + toNext > 0 ? Math.min(1, year / (year + toNext)) : 0,
        }
      : null,
    booking: upcoming ? { when: when(upcoming.scheduled_at), to: shortPlace(upcoming.dropoff_address) } : null,
    last: done && done.ride.completed_at
      ? { when: when(done.ride.completed_at), to: shortPlace(done.ride.dropoff_address), car: carKey("local_taxi", done.ride.vehicle_category) }
      : null,
    offers: {
      count: input.banners.length,
      title: (withHeadline ?? input.banners[0])?.title ?? null,
      headline: withHeadline?.headline ?? null,
    },
    services: input.tiles
      .filter((tile) => tile.status === "active" && internalPath(tile.destination))
      .slice(0, 4)
      .map((tile) => ({ title: tile.title, go: internalPath(tile.destination)! })),
    nearest: input.nearest,
  };
}

/** **ما يُدرج في قائمة الودجات** — المطفأُ في البلد أو ما لا مصدرَ له لا يُعرض للاختيار. */
export function widgetKinds(feed: WidgetFeed, flags: { schedule: boolean; eta: boolean; wallet: boolean }): WidgetKind[] {
  return WIDGET_KINDS.filter((kind) => {
    if (kind === "schedule") return flags.schedule;
    if (kind === "wallet") return flags.wallet;
    // **«خصم خاص» و«العروض» مع عرضٍ قائمٍ حقيقيٍّ وحدَه** — لافتاتُ المشرف للراكب
    if (kind === "discount" || kind === "offers") return feed.offers.count > 0;
    if (kind === "points") return feed.points !== null;
    if (kind === "nearest") return flags.eta;
    if (kind === "services") return feed.services.length > 0;
    return true;
  });
}

function available(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("Launcher");
}

/** يُنادى من الرئيسيّة: يجمع الأبوابَ مرّةً عند الفتح وكلَّما عاد التطبيقُ إلى الواجهة. */
export function useWidgetFeed(country: CountryCode | undefined, signedIn: boolean, nearest: number | null): void {
  const on = useFeature(country, "rider_widgets_plus");
  const schedule = useFeature(country, "scheduled_rides_enabled");
  const eta = useFeature(country, "eta_enabled");
  const walletOn = useFeature(country, "wallet_enabled");

  useEffect(() => {
    if (!available()) return;
    if (!on || !signedIn) {
      void native.setPrefs({ w_feed: null, w_kinds: JSON.stringify(on && !signedIn ? WIDGET_KINDS : []) }).catch(() => undefined);
      return;
    }
    let cancelled = false;
    const collect = async () => {
      const [wallet, loyalty, bookings, rides, store] = await Promise.all([
        getWallet().catch(() => null),
        getMyLoyalty().catch(() => null),
        schedule ? listBookings().catch(() => null) : Promise.resolve(null),
        listMyRides(5, 0, "completed").catch(() => null),
        getStorefront().catch(() => null),
      ]);
      if (cancelled) return;
      const feed = buildWidgetFeed({
        now: Date.now(),
        wallet,
        loyalty,
        bookings,
        rides,
        tiles: store?.tiles ?? [],
        banners: store?.banners ?? [],
        nearest,
      });
      await native.setPrefs({ w_feed: JSON.stringify(feed), w_kinds: JSON.stringify(widgetKinds(feed, { schedule, eta, wallet: walletOn })) });
    };
    void collect().catch(() => undefined);
    const again = () => {
      if (document.visibilityState === "visible") void collect().catch(() => undefined);
    };
    document.addEventListener("visibilitychange", again);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", again);
    };
  }, [on, signedIn, schedule, eta, walletOn, nearest]);
}
