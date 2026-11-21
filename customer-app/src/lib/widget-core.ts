/** **ما تحسبه ودجاتُ الراكب خالصاً** (أمرُ المالك ٢١/١١) — بلا React ولا Capacitor، فيُختبر في `tests/widget-core.test.ts`.
 *
 *  - **«المطار» في المفضّلة**: أقربُ مطارٍ **حقيقيٍّ** من مطارات السوق (`GET /airports` — الأسماءُ كما كتبها المشرف)، **ومكانُ الراكب
 *    المحفوظُ للمطار يغلب**. ولا مطارَ قريباً ⇐ `null` فيُخفى الزرّ — **لا مكانَ يُخترع**.
 *  - **مسارُ الرحلة للودجة**: النقاطُ نفسُها التي ترسمها الخريطة (`/rides/{id}/route-line`، `[lng, lat]`)، مُخفَّفةً ومقرَّبةً
 *    لتُحفظ في تفضيلات الهاتف. */

export interface LatLng {
  lat: number;
  lng: number;
}

export interface AirportLike extends LatLng {
  id: string;
  name: string;
}

export interface PlaceLike extends LatLng {
  id: string;
  label: string;
}

export interface WidgetAirport extends LatLng {
  /** `airport:<id>` أو `place:<id>` — والودجةُ تحمل المعرّفَ لا الإحداثيّة. */
  id: string;
  name: string;
}

/** أبعدُ من هذا لا يُقال «المطار»: مطارٌ في مدينةٍ أخرى ليس مطارَ الراكب. */
export const AIRPORT_MAX_KM = 100;
/** مكانٌ محفوظٌ على هذا القرب من مطارٍ هو المطار — وإن لم يُسمَّ «مطار». */
export const AIRPORT_PLACE_KM = 3;

/** المسافةُ على سطح الأرض بالكيلومتر (هافرساين). */
export function km(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** **مطارُ الراكب** — المحفوظُ أوّلاً (اسمُه فيه «مطار»، أو على ٣ كم من مطارٍ حقيقيّ)، ثمّ الأقربُ من مطارات السوق ضمن ١٠٠ كم. */
export function nearestAirport(
  airports: AirportLike[] | null | undefined,
  here: LatLng | null | undefined,
  places: PlaceLike[] | null | undefined,
): WidgetAirport | null {
  const list = airports ?? [];
  const saved =
    (places ?? []).find((place) => /مطار/.test(place.label)) ??
    (places ?? []).find((place) => list.some((airport) => km(airport, place) <= AIRPORT_PLACE_KM));
  if (saved) return { id: `place:${saved.id}`, name: saved.label, lat: saved.lat, lng: saved.lng };
  if (!here || list.length === 0) return null;
  let best: AirportLike | null = null;
  let bestKm = Infinity;
  for (const airport of list) {
    const d = km(here, airport);
    if (d < bestKm) {
      best = airport;
      bestKm = d;
    }
  }
  return best && bestKm <= AIRPORT_MAX_KM ? { id: `airport:${best.id}`, name: best.name, lat: best.lat, lng: best.lng } : null;
}

/** **مسارٌ للودجة**: ≤ `max` نقطة (الأولى والأخيرة دائماً)، مقرَّبةً إلى خمس خانات (~١ م) — وأقلُّ من نقطتين ⇐ `null`. */
export function thinRoute(points: number[][] | null | undefined, max = 120): number[][] | null {
  const valid = (points ?? []).filter((p) => p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]));
  if (valid.length < 2) return null;
  const step = Math.max(1, Math.ceil((valid.length - 1) / (max - 1)));
  const out: number[][] = [];
  for (let i = 0; i < valid.length - 1; i += step) out.push(valid[i]);
  out.push(valid[valid.length - 1]);
  return out.map(([lng, lat]) => [Math.round(lng * 1e5) / 1e5, Math.round(lat * 1e5) / 1e5]);
}
