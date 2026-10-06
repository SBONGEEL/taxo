/** **لغةُ «TaxoMap» على خرائط اللوحة** (A03 · A04) — الأرضُ والحدائقُ والطرقُ من رموز الهوية (`--t2-map-*`).
 *
 * **كما يصبغ التطبيقان خرائطَهما** (`MapView` عند الراكب والكبتن: قاعدةُ Mapbox الهادئة ثمّ الصبغُ عند كلِّ تحميلٍ للستايل)،
 * **بفرقٍ واحدٍ مقصود**: اللوحةُ أداةُ مراقبة، **ومشرفٌ يرى سيارةً بلا اسمِ حيٍّ أو شارعٍ حولها لا يعرف أين هي** — فتبقى أسماءُ
 * الطرق والأحياء وتُخفى المعالمُ والمباني والحدود كما في الهوية. **ولا لونَ يُكتب هنا**: `paint` في mapbox لا يقرأ `var()`،
 * فتُقرأ القيمُ من الرموز على الحاوية — **وبلا رموزٍ لا صبغ**، فتبقى القاعدةُ كما هي.
 */

import type { Map as MapboxMap } from "mapbox-gl";

/** القاعدتان الهادئتان — والصبغُ فوقهما. */
export const MAP_STYLE_LIGHT = "mapbox://styles/mapbox/light-v11";
export const MAP_STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

/** الطرقُ الكبرى بلون الطريق والصغرى أخفت — كما ترسمهما «TaxoMap». */
const MAJOR_ROADS = [
  "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
  "secondary", "secondary_link", "tertiary", "tertiary_link",
];

/** ما يبقى من الأسماء: الطرقُ والأحياءُ والمدن — **والمعالمُ تُخفى** كما في الهوية. */
const KEEP_LABELS = /road-label|settlement|place-/;

export function taxoLook(instance: MapboxMap, host: HTMLElement) {
  const css = getComputedStyle(host);
  const token = (name: string) => css.getPropertyValue(name).trim();
  const land = token("--t2-map-land");
  const park = token("--t2-map-park");
  const road = token("--t2-map-road");
  const minor = token("--t2-map-road-minor");
  if (!land || !park || !road || !minor) return;
  const clutter = /building|^admin|waterway|-case|road-(path|steps|pedestrian|rail|construction)|aeroway|ferry|aerialway|transit|hillshade|contour/;
  for (const layer of instance.getStyle()?.layers ?? []) {
    const { id, type } = layer;
    try {
      if (type === "symbol") {
        if (!KEEP_LABELS.test(id)) instance.setLayoutProperty(id, "visibility", "none");
      } else if (clutter.test(id)) {
        instance.setLayoutProperty(id, "visibility", "none");
      } else if (type === "background") {
        instance.setPaintProperty(id, "background-color", land);
      } else if (type === "fill" && id === "land") {
        instance.setPaintProperty(id, "fill-color", land);
      } else if (type === "fill" && (id.startsWith("landcover") || id.startsWith("national-park"))) {
        instance.setPaintProperty(id, "fill-color", park);
      } else if (type === "fill" && id.startsWith("landuse")) {
        instance.setPaintProperty(id, "fill-color", [
          "match", ["get", "class"],
          ["park", "pitch", "grass", "wood", "scrub", "garden", "national_park", "cemetery"], park,
          land,
        ]);
      } else if (type === "line" && /^(road|bridge|tunnel)-/.test(id)) {
        instance.setPaintProperty(id, "line-color", ["match", ["get", "class"], MAJOR_ROADS, road, minor]);
      }
    } catch {
      // طبقةٌ لا تحمل هذه الخاصّية — تُترك كما هي
    }
  }
}

/** **لونٌ من رمزٍ على الحاوية** — للخطوط التي ترسمها mapbox (لا تقرأ `var()`). */
export function tokenColour(host: HTMLElement | null, name: string): string {
  if (!host) return "";
  return getComputedStyle(host).getPropertyValue(name).trim();
}
