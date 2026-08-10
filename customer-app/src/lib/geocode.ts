/** بحث العناوين على Mapbox Geocoding (SPEC القسم 2).
 *
 * **الاعتماد الأساسي على الدبوس** والبحث مكمّل (القسم 11.3): عنوانٌ لم يُعثر
 * عليه لا يمنع طلب رحلة، والعنوان النصّي حقلٌ اختياري في `POST /rides` أصلاً.
 * ولذلك كل فشلٍ هنا يعود قائمةً فارغة أو `null` ولا يرفع خطأً يُعرض.
 *
 * التوكن العام (pk) يأتي من `GET /config` لا من ملف في الواجهة (القسم 4).
 * و**Directions لا تُستدعى من هنا أبداً**: المسافة والمدة والسعر تحسبها
 * الخلفية وحدها (القسم 14).
 */

import type { CountryCode, Coordinates } from "@/api/types";

const FORWARD = "https://api.mapbox.com/search/geocode/v6/forward";
const REVERSE = "https://api.mapbox.com/search/geocode/v6/reverse";

export interface Place {
  id: string;
  name: string;
  address: string;
  coordinates: Coordinates;
}

interface MapboxFeature {
  id?: string;
  properties?: {
    mapbox_id?: string;
    name?: string;
    full_address?: string;
    place_formatted?: string;
    coordinates?: { latitude: number; longitude: number };
  };
}

function toPlace(feature: MapboxFeature, index: number): Place | null {
  const properties = feature.properties;
  const point = properties?.coordinates;
  if (!point) return null;
  return {
    id: properties?.mapbox_id ?? feature.id ?? `place-${index}`,
    name: properties?.name ?? properties?.full_address ?? "موقع",
    address:
      properties?.full_address ?? properties?.place_formatted ?? properties?.name ?? "",
    coordinates: { lat: point.latitude, lng: point.longitude },
  };
}

export async function searchPlaces(
  token: string,
  query: string,
  country: CountryCode,
  near?: Coordinates,
  signal?: AbortSignal,
): Promise<Place[]> {
  if (!token || query.trim().length < 2) return [];

  const url = new URL(FORWARD);
  url.searchParams.set("q", query.trim());
  url.searchParams.set("access_token", token);
  url.searchParams.set("language", "ar");
  url.searchParams.set("country", country.toLowerCase());
  url.searchParams.set("limit", "6");
  if (near) url.searchParams.set("proximity", `${near.lng},${near.lat}`);

  try {
    const response = await fetch(url, { signal });
    if (!response.ok) return [];
    const body = (await response.json()) as { features?: MapboxFeature[] };
    return (body.features ?? [])
      .map(toPlace)
      .filter((place): place is Place => place !== null);
  } catch {
    return [];
  }
}

/** عنوانٌ نصّي لدبوسٍ على الخريطة — يُعرض ويُرسل اختيارياً مع الرحلة. */
export async function reverseGeocode(
  token: string,
  point: Coordinates,
  signal?: AbortSignal,
): Promise<string | null> {
  if (!token) return null;

  const url = new URL(REVERSE);
  url.searchParams.set("longitude", String(point.lng));
  url.searchParams.set("latitude", String(point.lat));
  url.searchParams.set("access_token", token);
  url.searchParams.set("language", "ar");
  url.searchParams.set("limit", "1");

  try {
    const response = await fetch(url, { signal });
    if (!response.ok) return null;
    const body = (await response.json()) as { features?: MapboxFeature[] };
    const first = body.features?.[0]?.properties;
    return first?.full_address ?? first?.name ?? null;
  } catch {
    return null;
  }
}

/** موقع الجهاز — يُطلب مرةً ولا يُلحّ: من رفض يضع دبوسه بيده. */
export function currentPosition(): Promise<Coordinates | null> {
  if (!("geolocation" in navigator)) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8_000, maximumAge: 30_000 },
    );
  });
}

/** مركزٌ افتراضي حين لا إذن موقع ولا رحلة جارية. */
export const DEFAULT_CENTER: Record<CountryCode, Coordinates> = {
  JO: { lat: 31.9539, lng: 35.9106 }, // عمّان
  LY: { lat: 32.8872, lng: 13.1913 }, // طرابلس
};
