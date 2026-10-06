/** **ما في هذه النقطة؟** — قراءةٌ عكسيةٌ واحدةٌ لبطاقة النقر على خريطة الكبتن الموسَّعة (§٦٢-ج/٤٨).
 *
 * **منقولٌ من خريطة الراكب بحرفه** (`customer-app/src/lib/geocode.ts`): Mapbox Geocoding بالتوكن العامّ من `GET /config`، **وبالعربية**،
 * **وكلُّ فشلٍ `null`** — فالبطاقةُ تقول «نقطة على الخريطة» ولا تصيح بخطأ: العنوانُ زينةُ النقطة لا شرطُها.
 * **ونداءٌ لكلِّ نقرةٍ يقصدها صاحبُها** في الخريطة الموسَّعة وحدَها — لا مع كلِّ تحريكٍ للكاميرا.
 */

import type { Coordinates } from "@/api/types";

const REVERSE = "https://api.mapbox.com/search/geocode/v6/reverse";

interface ReverseFeature {
  properties?: { name?: string; full_address?: string; place_formatted?: string };
}

export interface PlaceReading {
  name: string;
  address: string | null;
}

/** **عنوانٌ بلا فراغات**: Mapbox يكتب أحياناً جزءاً فارغاً («، عمّان، الأردن») — قِيس ٢٠٢٦-١٠-٠٦ — فيُطوى ما فرغ بين الفواصل. */
function tidy(text: string | null | undefined): string | null {
  if (!text) return null;
  const parts = text
    .split(/[،,]/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  return parts.length > 0 ? parts.join("، ") : null;
}

export async function reversePlace(
  token: string,
  point: Coordinates,
  signal?: AbortSignal,
): Promise<PlaceReading | null> {
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
    const body = (await response.json()) as { features?: ReverseFeature[] };
    const first = body.features?.[0]?.properties;
    const name = tidy(first?.name) ?? tidy(first?.full_address);
    if (!name) return null;
    return { name, address: tidy(first?.place_formatted) ?? tidy(first?.full_address) };
  } catch {
    return null;
  }
}
