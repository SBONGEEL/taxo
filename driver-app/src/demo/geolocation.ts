/** **موقعُ العرض بدل GPS** (SPEC §٧٦-ن/٢) — الكبتنُ الضيفُ في عمّان أينما كان في العالم، ويتحرّك على الخريطة كما يقوده المحرّك.
 *
 * يُركَّب مرّةً عند الإقلاع وفي العرض وحدَه (`main.tsx`): كلُّ من يسأل `navigator.geolocation` — الخريطةُ وزرُّ «موقعي» والمقبس — يجد
 * موضعَ المحرّك، **فلا شاشةَ تحتاج أن تعرف أنها في عرض**.
 */

import { demoPosition, onDemoPosition } from "@/demo/engine";

function fix(): GeolocationPosition {
  const where = demoPosition();
  const coords = {
    latitude: where.lat,
    longitude: where.lng,
    accuracy: 8,
    altitude: null,
    altitudeAccuracy: null,
    heading: null,
    speed: null,
  };
  return { coords: { ...coords, toJSON: () => coords }, timestamp: Date.now(), toJSON: () => ({ coords, timestamp: Date.now() }) } as GeolocationPosition;
}

export function installDemoGeolocation(): void {
  if (!("geolocation" in navigator)) return;
  const watchers = new Map<number, () => void>();
  let next = 1;
  const fake: Geolocation = {
    getCurrentPosition: (success) => window.setTimeout(() => success(fix()), 0),
    watchPosition: (success) => {
      const n = next++;
      window.setTimeout(() => success(fix()), 0);
      watchers.set(n, onDemoPosition(() => success(fix())));
      return n;
    },
    clearWatch: (n) => {
      watchers.get(n)?.();
      watchers.delete(n);
    },
  };
  Object.defineProperty(navigator, "geolocation", { configurable: true, get: () => fake });
}
