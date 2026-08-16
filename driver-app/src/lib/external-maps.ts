/** «افتح في خرائط قوقل» — تسليمُ الوجهة لتطبيق الخرائط المثبَّت (البند ١٦).
 *
 * **والحجّةُ ليست الكسل**: تطبيقُ قوقل يعرف الزحامَ والطرقَ المغلقةَ وأعمالَ
 * الحفر أفضلَ مما سنعرف، ويعرفها **الآن** بلا أن نبني شيئاً. وكبتنٌ لا يعرف
 * طريقَه سيفتح قوقل على أيّ حال — فإمّا أن يكتب العنوانَ بيده **وهو يقود**، أو
 * نسلّمه بضغطة.
 *
 * **ووجهةٌ واحدةٌ صحيحةٌ في كل لحظة، لا قائمةٌ يختار منها**: قائمةٌ تجعله يقرأ
 * ويقرّر عند إشارةٍ خضراء، وهو ما وُجد الزرُّ ليمنعه.
 */

import type { Ride } from "@/api/types";

export type MapTarget = {
  lat: number;
  lng: number;
  label: string;
  /** ما يُكتب على الزرّ — فالكبتنُ يعرف **إلى أين** يُرسَل قبل أن يضغط. */
  cta: string;
};

/** **الوجهةُ تتبع حالَ الرحلة**، وهي القاعدةُ كلُّها.
 *
 * قبل الوصول: نقطةُ الالتقاء. بعد البدء: الوجهة. وعند محطةٍ: **المحطةُ التالية**
 * — ولولا ذلك لأرسله الزرُّ إلى وجهةٍ نهائيةٍ وهو واقفٌ ينتظر راكباً عند محطة.
 */
export function targetFor(ride: Ride): MapTarget | null {
  if (ride.status === "accepted") {
    if (!ride.pickup) return null;
    return {
      lat: ride.pickup.lat,
      lng: ride.pickup.lng,
      label: ride.pickup_address ?? "نقطة الالتقاء",
      cta: "الاتجاه إلى نقطة الالتقاء",
    };
  }

  if (ride.status === "arrived") return null; // واقفٌ عندها — لا وجهةَ بعد

  if (ride.status === "at_stop" || ride.status === "in_progress") {
    // **المحطةُ التالية غيرُ المزارة** إن وُجدت، وإلا الوجهة
    const next = (ride.stops ?? []).find((stop) => stop.arrived_at == null);
    if (next) {
      return {
        lat: next.lat,
        lng: next.lng,
        label: next.address ?? "المحطة التالية",
        cta: "الاتجاه إلى المحطة",
      };
    }
    if (!ride.dropoff) return null;
    return {
      lat: ride.dropoff.lat,
      lng: ride.dropoff.lng,
      label: ride.dropoff_address ?? "الوجهة",
      cta: "الاتجاه إلى الوجهة",
    };
  }

  return null;
}

function isIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

/** الروابطُ الثلاثة بالترتيب — **والويبُ آخرُها وهو ما يجعل الزرَّ لا يموت**. */
export function linksFor(target: MapTarget): string[] {
  const { lat, lng, label } = target;
  const point = `${lat},${lng}`;
  const web = `https://www.google.com/maps/dir/?api=1&destination=${point}&travelmode=driving`;

  if (isIOS()) {
    return [
      `comgooglemaps://?daddr=${point}&directionsmode=driving`,
      `maps://?daddr=${point}&dirflg=d`,
      web,
    ];
  }
  // **أندرويد: `geo:` لا رابطُ قوقل** — فيفتح أيَّ تطبيق خرائطَ مثبَّت لا قوقل
  // وحدَه، وكبتنٌ يستعمل غيرَه لا يُجبَر على ما لم يختره
  return [`geo:${point}?q=${encodeURIComponent(`${point}(${label})`)}`, web];
}

/** يفتح أوّلَ ما ينجح — **وينتهي دائماً بالويب**.
 *
 * **و`window.open` لا `location.href`**: داخل غلاف Capacitor يمسك WebView
 * التنقّلَ في الإطار نفسِه، فمخطَّطٌ لا يعرفه يترك الشاشةَ بيضاء — وقد فقد
 * الكبتنُ رحلتَه الجارية. و`_system` هو ما يخرج بالنيّة إلى نظام التشغيل.
 *
 * **ولم يُقَل إنه يعمل حتى يُجرَّب على الجهاز داخل الغلاف** (تحذيرُ البند ١٦):
 * سلوكُ المتصفح ليس سلوكَ الغلاف، وهذا الملفُّ يُختبر هناك لا هنا.
 */
export function openIn(target: MapTarget): void {
  const links = linksFor(target);
  for (const url of links.slice(0, -1)) {
    const opened = window.open(url, "_system") ?? window.open(url, "_blank");
    if (opened) return;
  }
  window.open(links[links.length - 1], "_blank", "noopener");
}
