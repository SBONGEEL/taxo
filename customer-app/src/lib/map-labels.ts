/** **أسماءُ الأماكن على الخريطة** (SPEC §٧١-د) — بيتٌ واحدٌ لما يُرسم من أسماء، **منسوخٌ حرفاً في التطبيقين** (`driver-app/src/lib/map-labels.ts`).
 *
 * **ما يفعله حين يشتعل `map_places_enabled` لسوق المستخدم**:
 * 1. **أسماءُ الخريطة تظهر** بدل الخريطة الهادئة بلا أسماء: المدنُ والأحياءُ والشوارعُ والمحلّاتُ والمعالمُ الطبيعيّة والمطارات — **بالعربيّة،
 *    والمحلّيُّ حيث لا عربيّ** (`MAP_LANGUAGE` في `map-rtl.ts`، خيارُ إنشاء). **والتكبيرُ يحكم ما يظهر** كما رسمه المزوّد: المدنُ بعيداً
 *    والأزقّةُ قريباً، **ولا تتراكم** — كشفُ التصادم في المكتبة نفسِها. **ولا أسماءُ دولٍ ولا حدود**: لا يحتاجها مشوارٌ داخل مدينة.
 * 2. **وأماكنُ المالك فوقها** (`GET /map-places`) — طبقةٌ فوق أسماء المزوّد، **فاسمُ المالك يُوضع أوّلاً ويُخفي ما تحته في موضعه**
 *    (المكتبةُ تضع الطبقةَ العليا قبل السفلى): فيصحّح اسماً خاطئاً أو ناقصاً هناك.
 * 3. **والسياراتُ والمسارُ فوق الجميع**: السياراتُ علاماتُ DOM فوق اللوحة أصلاً، **وطبقةُ الأماكن تُدرج تحت خطِّ المسار** إن سبقها.
 *
 * **ومطفأً لا يتغيّر شيء**: الخريطةُ هادئةٌ بلا أسماء كما كانت حرفاً، ولا يُطلب جدولُ الأماكن.
 *
 * **والألوانُ من رموز الحاوية** (`--t2-map-label*`) في الفاتح والداكن والنسائيّ — `paint` في mapbox لا يقرأ `var()`. **وبلا رموزٍ لا
 * أسماء**: لا لونَ يُخترع هنا.
 */

import type { GeoJSONSource, Map as MapboxMap } from "mapbox-gl";
import { useEffect, useState } from "react";

import { mapPlaces } from "@/api/endpoints";
import type { MapPlaceSpot } from "@/api/types";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export const PLACES_FLAG = "map_places_enabled";

/** **ما يُظهر من طبقات المزوّد** — الأسماءُ وحدَها: لا دروعَ أرقام الطرق، ولا النقل، ولا الدولُ والأقاليم. */
const SHOWN = /^(settlement|natural|water-(point|line)-label|waterway-label|poi-label|road-label|airport-label)/;
/** الشوارعُ بلونٍ أخفت من المدن والمحلّات — اسمٌ يُقرأ ولا ينافس. */
const MINOR = /^(road-label|waterway-label|natural-line|water-line)/;

const SOURCE = "taxo-places";
const DOT = "taxo-places-dot";
const LABEL = "taxo-places-label";
/** **خطُّ المسار والزحامُ فوق الأماكن** — أوّلُ ما يوجد منها يُدرج قبله. */
const ABOVE = ["taxo-traffic", "taxo-route-line-done", "taxo-route-line-casing", "taxo-route-line", "taxo-trip-line-casing", "taxo-trip-line"];

interface Palette {
  label: string;
  minor: string;
  halo: string;
  own: string;
  ring: string;
}

function palette(host: HTMLElement): Palette | null {
  const css = getComputedStyle(host);
  const token = (name: string) => css.getPropertyValue(name).trim();
  const out = {
    label: token("--t2-map-label"),
    minor: token("--t2-map-label-minor"),
    halo: token("--t2-map-label-halo"),
    own: token("--t2-accent-text"),
    ring: token("--t2-map-pin-ring") || token("--t2-map-label-halo"),
  };
  return out.label && out.minor && out.halo && out.own ? out : null;
}

/** **طبقةُ رموزٍ واحدة**: تُظهَر بألوان الهوية إن كانت من الأسماء والمفتاحُ مشتعل، **وتُخفى كما كانت في غير ذلك**. يناديها `calmLook`. */
export function styleSymbolLayer(instance: MapboxMap, id: string, colors: Palette | null) {
  if (!colors || !SHOWN.test(id)) {
    instance.setLayoutProperty(id, "visibility", "none");
    return;
  }
  instance.setLayoutProperty(id, "visibility", "visible");
  try {
    instance.setPaintProperty(id, "text-color", MINOR.test(id) ? colors.minor : colors.label);
    instance.setPaintProperty(id, "text-halo-color", colors.halo);
    instance.setPaintProperty(id, "text-halo-width", 1.4);
    // **الاسمُ بلا أيقونته الملوّنة** — الخريطةُ تبقى بلغة الهوية، والاسمُ وحدَه يُقرأ
    instance.setPaintProperty(id, "icon-opacity", 0);
  } catch {
    // طبقةٌ بلا أيقونة — يكفي لونُ النصّ
  }
}

/** **ألوانُ الأسماء لهذه الحاوية** — و`null` إن كان المفتاحُ مطفأً أو الرموزُ غائبة (فتُخفى الأسماءُ كما كانت). */
export function labelColors(host: HTMLElement, on: boolean): Palette | null {
  return on ? palette(host) : null;
}

/** يعيد تطبيقَ الإظهار والإخفاء على طبقات الرموز وحدَها — حين يتبدّل المفتاحُ بعد تحميل الستايل. */
export function applyLabels(instance: MapboxMap, host: HTMLElement, on: boolean) {
  const colors = labelColors(host, on);
  for (const layer of instance.getStyle()?.layers ?? []) {
    if (layer.type !== "symbol" || layer.id.startsWith(SOURCE)) continue;
    try {
      styleSymbolLayer(instance, layer.id, colors);
    } catch {
      // طبقةٌ تُركت كما هي
    }
  }
}

/** **أماكنُ المالك فوق أسماء المزوّد وتحت المسار** — نقطةٌ صغيرةٌ واسمٌ بلون الجمر (البرقوق في النسائيّ). وقائمةٌ فارغةٌ تُفرغ الطبقة. */
export function drawOwnPlaces(instance: MapboxMap, host: HTMLElement, places: MapPlaceSpot[]) {
  const data = {
    type: "FeatureCollection" as const,
    features: places.map((place) => ({
      type: "Feature" as const,
      properties: { name: place.name_ar },
      geometry: { type: "Point" as const, coordinates: [place.lng, place.lat] },
    })),
  };
  const source = instance.getSource(SOURCE) as GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
    return;
  }
  if (!places.length) return;
  const colors = palette(host);
  if (!colors) return;
  instance.addSource(SOURCE, { type: "geojson", data });
  const before = ABOVE.find((id) => instance.getLayer(id));
  // **خطُّ المزوّد نفسُه** — فالعربيّةُ تُرسم بحروف الخريطة لا بخطٍّ لا يحمل الحروف
  const font = (instance.getLayer("poi-label") && instance.getLayoutProperty("poi-label", "text-font")) as string[] | undefined;
  instance.addLayer(
    {
      id: DOT,
      type: "circle",
      source: SOURCE,
      minzoom: 11,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2.5, 16, 4.5],
        "circle-color": colors.own,
        "circle-stroke-color": colors.ring,
        "circle-stroke-width": 1.5,
      },
    },
    before,
  );
  instance.addLayer(
    {
      id: LABEL,
      type: "symbol",
      source: SOURCE,
      minzoom: 11,
      layout: {
        "text-field": ["get", "name"],
        ...(font ? { "text-font": font } : {}),
        "text-size": ["interpolate", ["linear"], ["zoom"], 11, 11, 16, 14],
        "text-anchor": "top",
        "text-offset": [0, 0.6],
        "text-max-width": 9,
      },
      paint: {
        "text-color": colors.own,
        "text-halo-color": colors.halo,
        "text-halo-width": 1.6,
      },
    },
    before,
  );
}

/** **عمرُ ما قُرئ من الأماكن** — مكانٌ يضيفه المالكُ يصل الخرائطَ المفتوحةَ بعد هذا، لا بعد إعادة تشغيل التطبيق. */
const FRESH_MS = 10 * 60_000;
let held: { key: string; at: number; rows: Promise<MapPlaceSpot[]> } | null = null;

/** **المفتاحُ لسوق المستخدم، والأماكنُ إن اشتعل** — قراءةٌ واحدةٌ تتشاركها خرائطُ التطبيق كلُّها في نافذتها. */
export function useMapPlaces(): { labels: boolean; places: MapPlaceSpot[] } {
  const { user } = useSession();
  const labels = useFeature(user?.country_code, PLACES_FLAG);
  const [places, setPlaces] = useState<MapPlaceSpot[]>([]);
  const key = user ? `${user.id}:${user.country_code}` : "";

  useEffect(() => {
    if (!labels || !key) {
      setPlaces([]);
      return;
    }
    const now = Date.now();
    if (!held || held.key !== key || now - held.at > FRESH_MS) {
      // **فشلُ القراءة خريطةٌ بلا أماكن المالك لا خطأٌ يُعرض** — أسماءُ المزوّد تبقى
      held = { key, at: now, rows: mapPlaces().catch(() => []) };
    }
    let live = true;
    void held.rows.then((rows) => {
      if (live) setPlaces(rows);
    });
    return () => {
      live = false;
    };
  }, [labels, key]);

  return { labels, places };
}
