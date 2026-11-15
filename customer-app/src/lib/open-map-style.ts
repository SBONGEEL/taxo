/** **خريطةُ TAXO ببياناتٍ مفتوحة** (SPEC §«الخرائطُ والبحثُ ببياناتٍ مفتوحة»/العرض) — نمطٌ كاملٌ يُبنى هنا لا يُنزَّل،
 *  **منسوخٌ حرفاً في التطبيقين** (`customer-app` · `driver-app`، `src/lib/open-map-style.ts`)؛ وخرائطُ اللوحة على Mapbox بعد.
 *
 * **المصدر**: بلاطاتُ OpenFreeMap المتّجهة (مخطّطُ OpenMapTiles من OSM) — **مجّانيّةٌ بلا مفتاحٍ ولا حدِّ طلبات**، ونسبتُها
 * «© OpenStreetMap contributors · OpenFreeMap» تُكتب في `attribution` فتظهر في زاوية الخريطة كما تشترط ODbL.
 *
 * **ولمَ يُبنى النمطُ هنا ولا يُؤخذ نمطُ OpenFreeMap الجاهز**: الجاهزُ إنجليزيٌّ أوّلاً وبألوانٍ ليست ألوانَنا؛ وصبغُه طبقةً طبقةً بعد
 * التحميل (كما يفعل `calmLook` بنمط Mapbox) يرسم الإطارَ الأوّلَ بألوانه ثمّ يرتجف. **فالطبقاتُ هنا قليلةٌ ومقصودة**:
 * الأرضُ والحدائقُ والماءُ والمباني والطرقُ، ثمّ الأسماءُ بالعربيّة — الأحياءُ والمعالمُ وأسماءُ الشوارع — **والمحلّيُّ حيث لا عربيّ**.
 *
 * **وأسماءُ الطبقات على أسماء Mapbox** (`settlement-*` · `poi-label` · `road-label` · `airport-label`) **بقصد**: فمفتاحُ الأسماء
 * (`applyLabels` في `lib/map-labels.ts`) يُظهرها ويُخفيها ويلوّنها في المحرّكين بلا فرع، وطبقةُ أماكن المالك تأخذ خطَّها من `poi-label`.
 *
 * **والألوانُ من رموز الحاوية** (`--t2-map-*`) تُمرَّر إلى `buildOpenStyle` — `paint` لا يقرأ `var()`، **ولا لونَ يُخترع هنا**.
 */

/** بلاطاتُ OpenFreeMap (TileJSON) وخطوطُها — وفيها نطاقُ العربيّة (U+0600–06FF) في «Noto Sans». */
export const OPEN_TILES_URL = "https://tiles.openfreemap.org/planet";
export const OPEN_GLYPHS_URL = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf";
export const OPEN_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

/** ألوانُ الحاوية — تُقرأ من رموز `--t2-map-*` بـ`openMapColors`. */
export interface OpenMapColors {
  land: string;
  park: string;
  water: string;
  building: string;
  road: string;
  roadMinor: string;
  label: string;
  labelMinor: string;
  halo: string;
}

/** **الرموزُ من الحاوية** — و`null` إن غاب أحدُها: لا خريطةَ بألوانٍ مخترعة. */
export function openMapColors(host: HTMLElement): OpenMapColors | null {
  const css = getComputedStyle(host);
  const t = (name: string) => css.getPropertyValue(name).trim();
  const out: OpenMapColors = {
    land: t("--t2-map-land"),
    park: t("--t2-map-park"),
    water: t("--t2-map-water"),
    building: t("--t2-map-building"),
    road: t("--t2-map-road"),
    roadMinor: t("--t2-map-road-minor"),
    label: t("--t2-map-label"),
    labelMinor: t("--t2-map-label-minor"),
    halo: t("--t2-map-label-halo"),
  };
  return Object.values(out).every(Boolean) ? out : null;
}

/** **الاسمُ بالعربيّة، والمحلّيُّ حيث لا عربيّ** — فلا تخرج خريطةٌ نصفُها إنجليزيّ (قرارُ المالك 2026-08-27، `MAP_LANGUAGE`). */
const NAME = ["coalesce", ["get", "name:ar"], ["get", "name"]];
const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];

const MAJOR = ["motorway", "trunk", "primary", "secondary", "tertiary"];
const ARTERIAL = ["motorway", "trunk", "primary", "secondary"];
/** **أصنافُ المعالم** في مخطّط OpenMapTiles — ما يدلّ عليه الراكبُ والكبتن. */
const LANDMARKS = [
  "hospital", "college", "school", "place_of_worship", "town_hall", "attraction", "museum", "stadium", "park",
  "lodging", "fuel", "police", "bus", "railway", "airport", "castle", "monument", "theatre", "cinema", "library", "post",
];

/** عرضُ الطريق بالتكبير — الكبرى أعرض، والصغرى تظهر قريباً وحدَه. */
function roadWidth(major: boolean) {
  return major
    ? ["interpolate", ["exponential", 1.5], ["zoom"], 10, 1.2, 14, 5, 17, 16, 20, 40]
    : ["interpolate", ["exponential", 1.5], ["zoom"], 13, 0.6, 15, 2.6, 17, 8, 20, 22];
}

/** **النمطُ كاملاً** — `labels` مطفأً يعيد الخريطةَ الهادئةَ بلا أسماء (كما هي اليوم حين `map_places_enabled` مطفأ). */
export function buildOpenStyle(c: OpenMapColors, labels: boolean): Record<string, unknown> {
  const visibility = labels ? "visible" : "none";
  const halo = { "text-color": c.label, "text-halo-color": c.halo, "text-halo-width": 1.4 };
  const haloMinor = { "text-color": c.labelMinor, "text-halo-color": c.halo, "text-halo-width": 1.4 };
  return {
    version: 8,
    name: "TAXO open",
    glyphs: OPEN_GLYPHS_URL,
    sources: {
      openmaptiles: { type: "vector", url: OPEN_TILES_URL, attribution: OPEN_ATTRIBUTION },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": c.land } },
      {
        id: "park",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "park",
        paint: { "fill-color": c.park },
      },
      {
        id: "landcover-green",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "landcover",
        filter: ["match", ["get", "class"], ["grass", "wood", "farmland", "wetland"], true, false],
        paint: { "fill-color": c.park, "fill-opacity": 0.7 },
      },
      {
        id: "landuse-green",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "landuse",
        filter: ["match", ["get", "class"], ["cemetery", "pitch", "stadium", "garden"], true, false],
        paint: { "fill-color": c.park },
      },
      {
        id: "water",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "water",
        filter: ["!=", ["get", "brunnel"], "tunnel"],
        paint: { "fill-color": c.water },
      },
      {
        id: "waterway",
        type: "line",
        source: "openmaptiles",
        "source-layer": "waterway",
        minzoom: 12,
        paint: { "line-color": c.water, "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 18, 4] },
      },
      {
        // **المباني**: تظهر قريباً (١٥ فما فوق) بلونٍ أغمقَ قليلاً من الأرض — تعطي الحيَّ شكلَه ولا تنافس المسار
        id: "building",
        type: "fill",
        source: "openmaptiles",
        "source-layer": "building",
        minzoom: 14.5,
        paint: {
          "fill-color": c.building,
          "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14.5, 0, 15.5, 1],
        },
      },
      {
        id: "road-minor",
        type: "line",
        source: "openmaptiles",
        "source-layer": "transportation",
        minzoom: 12.5,
        filter: ["match", ["get", "class"], ["minor", "service"], true, false],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": c.roadMinor, "line-width": roadWidth(false) },
      },
      {
        // **وتهدأ الشوارعُ حين تبتعد الكاميرا** — كـ`calmLook`: تحت ١٣ الشرايينُ وحدَها
        id: "road-major",
        type: "line",
        source: "openmaptiles",
        "source-layer": "transportation",
        filter: ["match", ["get", "class"], MAJOR, true, false],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": c.road,
          "line-width": roadWidth(true),
          "line-opacity": [
            "interpolate", ["linear"], ["zoom"],
            12, ["match", ["get", "class"], ARTERIAL, 1, 0],
            13.5, 1,
          ],
        },
      },
      {
        // **المعالم**: ما يُوصف به المشوار (مستشفى، جامعة، مسجد، مول، فندق، دائرة…) من ١٤٫٥، **والمحلّاتُ قريباً جدّاً وحدَه**
        // (١٧٫٥) — فلا تغرق الخريطةُ بأسماء المتاجر. بلا أيقونات: الخريطةُ بلغة الهوية، والاسمُ يُقرأ وحدَه
        id: "poi-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "poi",
        minzoom: 15,
        filter: [
          "any",
          ["match", ["get", "class"], LANDMARKS, true, false],
          ["match", ["get", "subclass"], ["mall", "department_store"], true, false],
          [">=", ["zoom"], 17.5],
        ],
        layout: {
          visibility,
          "text-field": NAME,
          "text-font": FONT,
          "text-size": 11,
          "text-max-width": 8,
          "symbol-sort-key": ["get", "rank"],
        },
        paint: halo,
      },
      {
        id: "airport-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "aerodrome_label",
        minzoom: 10,
        layout: { visibility, "text-field": NAME, "text-font": FONT, "text-size": 12 },
        paint: halo,
      },
      {
        // **أسماءُ الشوارع** على امتداد الطريق — **بعد المعالم في الترتيب فتُوضع قبلها** (المكتبةُ تضع الطبقةَ العليا أوّلاً):
        // الكبتنُ يقرأ اسمَ الشارع قبل اسم المحلّ
        id: "road-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "transportation_name",
        minzoom: 13.5,
        layout: {
          visibility,
          "symbol-placement": "line",
          "text-field": NAME,
          "text-font": FONT,
          "text-size": ["interpolate", ["linear"], ["zoom"], 13.5, 10, 18, 14],
          "text-max-angle": 30,
          "symbol-spacing": 280,
        },
        paint: haloMinor,
      },
      {
        // **الأحياء** — تظهر من ١٢ وتكبر مع التكبير
        id: "settlement-subdivision-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 12,
        filter: ["match", ["get", "class"], ["suburb", "quarter", "neighbourhood", "hamlet"], true, false],
        layout: {
          visibility,
          "text-field": NAME,
          "text-font": FONT,
          "text-size": ["interpolate", ["linear"], ["zoom"], 12, 11, 16, 14],
          "text-max-width": 8,
        },
        paint: haloMinor,
      },
      {
        id: "settlement-minor-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        minzoom: 8,
        filter: ["match", ["get", "class"], ["town", "village"], true, false],
        layout: {
          visibility,
          "text-field": NAME,
          "text-font": FONT,
          "text-size": ["interpolate", ["linear"], ["zoom"], 8, 11, 14, 15],
        },
        paint: halo,
      },
      {
        id: "settlement-major-label",
        type: "symbol",
        source: "openmaptiles",
        "source-layer": "place",
        maxzoom: 14,
        filter: ["==", ["get", "class"], "city"],
        layout: {
          visibility,
          "text-field": NAME,
          "text-font": FONT_BOLD,
          "text-size": ["interpolate", ["linear"], ["zoom"], 6, 13, 12, 19],
        },
        paint: halo,
      },
    ],
  };
}
