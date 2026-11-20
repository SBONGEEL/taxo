/** **طبقاتُ الخريطة المفتوحة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢ و٣؛ `design/MAP-OPEN-DATA-TRAFFIC.md`) — **منسوخٌ حرفاً في التطبيقين**.
 *
 * ١) **الأماكنُ والمباني والصيانة** من مربّعاتنا (`GET /map/tiles/places/…` ⇐ `places-search`): أماكنُ البحث نفسُها، باسمٍ عربيٍّ أوّلاً
 *    وأيقونةِ نوع، **والكثافةُ بالتكبير** (`minzoom` لكلِّ فئةٍ في البناء، وكشفُ التصادم وترتيبُ الرتبة هنا) — فلا تزدحم. وتُخفي طبقةَ
 *    محلّات المزوّد فلا يُكتب المكانُ مرّتين. **ومطفأً (`map_open_places`) تعود الخريطةُ كما كانت حرفاً.**
 * ٢) **الازدحام** (`GET /map/traffic`): أخضرُ وبرتقاليٌّ وأحمر، **وما لا لونَ له لا يُرسم** — لا «سالكٌ» لطريقٍ لم يمرّ به أحد.
 * ٣) **بلاغاتُ الطريق** (`GET /map/road-reports`): صيانة · طريق مغلق · حادث · ازدحام، بأيقونةٍ وكلمة.
 *
 * **وكلُّها تحت خطِّ المسار وأماكنِ المالك**، **ولا شيءَ منها يمسّ الأجرة**: عرضٌ وحده.
 */
import type { GeoJSONSource, Map as MapboxMap } from "mapbox-gl";
import { useEffect, useState } from "react";

import { api } from "@/api/client";
import { openPlacesTiles } from "@/api/endpoints";
import { arabicOnlyExpression } from "@/lib/arabic-name";
import { addPinImages } from "@/lib/map-pin-icons";
import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export const OPEN_PLACES_FLAG = "map_open_places";
export const TRAFFIC_FLAG = "map_live_traffic";
export const REPORTS_FLAG = "map_road_reports";
export const SUGGESTIONS_FLAG = "map_place_suggestions";

const SOURCE = "taxo-open";
const BUILDINGS = "taxo-open-buildings";
const PLACES = "taxo-open-places";
const WORKS = "taxo-open-works";
const TRAFFIC_SOURCE = "taxo-live-traffic";
const TRAFFIC = "taxo-live-traffic-line";
const REPORTS_SOURCE = "taxo-road-reports";
const REPORTS = "taxo-road-reports-icon";
const OPEN_PREFIX = "taxo-open-";
/** **فوق هذه لا تحتها** — المسارُ وأماكنُ المالك */
const ABOVE = ["taxo-places-dot", "taxo-route-line-done", "taxo-route-line-casing", "taxo-route-line", "taxo-trip-line-casing", "taxo-trip-line"];
/** **فئاتُ المربّعات** (`places-search/build_map_data.py`) — وكلُّها لها أيقونةٌ في `map-pin-icons` */
export const OPEN_CATEGORIES = [
  "hospital", "clinic", "pharmacy", "university", "school", "mosque", "bank", "government", "fuel", "restaurant", "cafe", "hotel",
  "mall", "landmark", "transport", "shop", "place", "works", "closed", "accident", "jam",
];
/** اسمُ الفئة بالعربيّة — لبطاقة المكان («نوعه») */
export const OPEN_CATEGORY_LABEL: Record<string, string> = {
  hospital: "مستشفى", clinic: "عيادة", pharmacy: "صيدلية", university: "جامعة", school: "مدرسة", mosque: "مسجد", bank: "بنك",
  government: "دائرة حكومية", fuel: "محطة وقود", restaurant: "مطعم", cafe: "مقهى", hotel: "فندق", mall: "مركز تسوّق",
  landmark: "معلم", transport: "مواصلات", shop: "محلّ", place: "مكان",
};
export const REPORT_LABEL: Record<string, string> = { works: "صيانة", closed: "طريق مغلق", accident: "حادث", jam: "ازدحام" };
const TRAFFIC_COLOR = { free: "#2fa365", slow: "#f08c1a", heavy: "#d6343a" };

function tokens(host: HTMLElement) {
  const css = getComputedStyle(host);
  const token = (name: string) => css.getPropertyValue(name).trim();
  return {
    label: token("--t2-map-label") || "#3b3f45",
    halo: token("--t2-map-label-halo") || "#ffffff",
    building: token("--t2-map-building") || "#e4e0d8",
    pin: token("--t2-map-label-minor") || token("--t2-map-label") || "#6b7076",
    accent: token("--t2-accent-text") || "#f05a28",
  };
}

function firstPresent(instance: MapboxMap, ids: string[]): string | undefined {
  return ids.find((id) => instance.getLayer(id));
}

function firstSymbol(instance: MapboxMap): string | undefined {
  return instance.getStyle()?.layers?.find((layer) => layer.type === "symbol")?.id;
}

/** **أسماءُ المشرف** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب) — مفتاحُ المكان (`k` في المربّع) ⇐ اسمٌ عربيٌّ كتبه في «أماكن بلا اسم عربي»،
 *  **يُرسم فوق اسم المربّع** فلا ينتظر البناءَ الشهريّ. يُقرأ مرّةً كلَّ عشر دقائق، وغيابُه لا يُخفي شيئاً: الاسمُ الأصليُّ باقٍ. */
let nameFixes: Record<string, string> = {};
let nameFixesAt = 0;
let nameFixesLoading: Promise<void> | null = null;
function loadNameFixes(): Promise<void> {
  if (Date.now() - nameFixesAt < 600_000) return Promise.resolve();
  nameFixesLoading ??= api
    .get<Record<string, string>>("/map/name-fixes")
    .then((data) => {
      nameFixes = data ?? {};
      nameFixesAt = Date.now();
    })
    .catch(() => undefined)
    .finally(() => {
      nameFixesLoading = null;
    });
  return nameFixesLoading;
}

/** اسمُ المكان: اسمُ المشرف بمفتاحه، وإلا اسمُ المربّع */
function placeName(): unknown {
  // اسمُ المشرف كما كتبه؛ واسمُ المربّع **عربيُّه وحدَه إن كان مزدوجاً** (`arabic-name.ts`، أمرُ ٢٠/١١ الثالث §١)
  return ["coalesce", ["get", ["to-string", ["get", "k"]], ["literal", nameFixes]], arabicOnlyExpression(["get", "n"])];
}

function placeLabel(): unknown {
  return [
    "case",
    ["==", ["get", "o"], "public"], ["concat", placeName(), " · حكومي"],
    ["==", ["get", "o"], "private"], ["concat", placeName(), " · خاص"],
    placeName(),
  ];
}

/** **الأماكنُ والمباني والصيانة** — `on=false` يزيلها ويعيد محلّاتِ المزوّد كما كانت. يُنادى مع كلِّ ستايلٍ يُحمَّل. */
export function drawOpenPlaces(instance: MapboxMap, host: HTMLElement, on: boolean) {
  const provider = instance.getLayer("poi-label") ? "poi-label" : null;
  if (!on) {
    for (const id of [PLACES, WORKS, BUILDINGS]) if (instance.getLayer(id)) instance.removeLayer(id);
    if (instance.getSource(SOURCE)) instance.removeSource(SOURCE);
    return;
  }
  // **المكانُ لا يُكتب مرّتين** — محلّاتُ المزوّد من OSM نفسِه، وطبقتُنا تحملها ومعها Overture
  if (provider) instance.setLayoutProperty(provider, "visibility", "none");
  void loadNameFixes().then(() => {
    if (instance.getLayer(PLACES)) instance.setLayoutProperty(PLACES, "text-field", placeLabel() as never);
  });
  if (instance.getSource(SOURCE)) return;
  const colors = tokens(host);
  instance.addSource(SOURCE, {
    type: "vector",
    tiles: [openPlacesTiles()],
    minzoom: 11,
    maxzoom: 16,
    attribution: "© OpenStreetMap contributors · Overture Maps Foundation",
  } as never);
  instance.addLayer(
    {
      id: BUILDINGS,
      type: "fill",
      source: SOURCE,
      "source-layer": "buildings",
      minzoom: 14,
      paint: { "fill-color": colors.building, "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14, 0.35, 16, 0.75] },
    } as never,
    firstSymbol(instance),
  );
  const before = firstPresent(instance, ABOVE);
  const font = (provider && instance.getLayoutProperty(provider, "text-font")) as string[] | undefined;
  const label = (field: unknown) => ({
    "text-field": field,
    ...(font ? { "text-font": font } : {}),
    "text-size": ["interpolate", ["linear"], ["zoom"], 13, 10.5, 17, 12.5],
    "text-anchor": "top",
    "text-offset": [0, 1.05],
    "text-max-width": 8,
    "text-optional": true,
  });
  void addPinImages(instance as never, OPEN_CATEGORIES, colors.pin, colors.halo, colors.halo, OPEN_PREFIX).then(() => {
    if (!instance.getSource(SOURCE) || instance.getLayer(PLACES)) return;
    instance.addLayer(
      {
        id: PLACES,
        type: "symbol",
        source: SOURCE,
        "source-layer": "places",
        minzoom: 12,
        // **«مكان» بلا نوعٍ لا يظهر إلا قريباً جدّاً** — لا يزاحم ما له نوع
        filter: ["any", [">=", ["zoom"], 16.5], ["!=", ["get", "c"], "place"]],
        layout: {
          "icon-image": ["concat", OPEN_PREFIX, ["get", "c"]],
          "icon-size": ["interpolate", ["linear"], ["zoom"], 12, 0.62, 16, 0.85],
          "symbol-sort-key": ["-", 0, ["get", "r"]],
          ...label(placeLabel()),
        },
        paint: { "text-color": colors.label, "text-halo-color": colors.halo, "text-halo-width": 1.4 },
      } as never,
      before,
    );
    instance.addLayer(
      {
        id: WORKS,
        type: "symbol",
        source: SOURCE,
        "source-layer": "works",
        minzoom: 13,
        layout: {
          "icon-image": ["concat", OPEN_PREFIX, ["get", "k"]],
          "icon-size": 0.85,
          "icon-allow-overlap": true,
          ...label(["match", ["get", "k"], "closed", "طريق مغلق", "صيانة"]),
        },
        paint: { "text-color": colors.accent, "text-halo-color": colors.halo, "text-halo-width": 1.4 },
      } as never,
      before,
    );
  });
}

/** **لمسُ مكانٍ من الطبقة المفتوحة** — الاسمُ والنوعُ والموضع لمن يسأل (بطاقةُ «اذهب إلى هنا / انطلق من هنا»). مرّةً لكلِّ خريطة. */
const tapBound = new WeakSet<object>();
export function bindOpenTap(instance: MapboxMap, handler: (place: { name: string; lat: number; lng: number; kind?: string }) => void) {
  if (tapBound.has(instance)) return;
  tapBound.add(instance);
  instance.on("click", (event) => {
    if (!instance.getLayer(PLACES)) return;
    const { x, y } = event.point;
    const hit = instance.queryRenderedFeatures([[x - 12, y - 12], [x + 12, y + 12]] as never, { layers: [PLACES] })[0];
    if (!hit || hit.geometry.type !== "Point") return;
    const [lng, lat] = hit.geometry.coordinates as [number, number];
    const key = String(hit.properties?.k ?? "");
    const name = String((key && nameFixes[key]) || hit.properties?.n || "").trim();
    const category = String(hit.properties?.c ?? "place");
    const owner = hit.properties?.o === "public" ? " حكومي" : hit.properties?.o === "private" ? " خاص" : "";
    if (name) handler({ name, lat, lng, kind: (OPEN_CATEGORY_LABEL[category] ?? "مكان") + owner });
  });
}

type Collection = { type: "FeatureCollection"; features: unknown[] };
const EMPTY: Collection = { type: "FeatureCollection", features: [] };

/** **الازدحام** — خطوطٌ بلون مستواها تحت المسار؛ ومجموعةٌ فارغةٌ تُفرغها. */
export function drawTraffic(instance: MapboxMap, data: Collection | null) {
  const source = instance.getSource(TRAFFIC_SOURCE) as GeoJSONSource | undefined;
  if (!data) {
    if (instance.getLayer(TRAFFIC)) instance.removeLayer(TRAFFIC);
    if (source) instance.removeSource(TRAFFIC_SOURCE);
    return;
  }
  if (source) {
    source.setData(data as never);
    return;
  }
  instance.addSource(TRAFFIC_SOURCE, { type: "geojson", data: data as never });
  instance.addLayer(
    {
      id: TRAFFIC,
      type: "line",
      source: TRAFFIC_SOURCE,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "l"], "heavy", TRAFFIC_COLOR.heavy, "slow", TRAFFIC_COLOR.slow, TRAFFIC_COLOR.free],
        "line-width": ["interpolate", ["linear"], ["zoom"], 11, 2, 16, 5],
        "line-opacity": 0.85,
      },
    } as never,
    firstPresent(instance, ABOVE),
  );
}

export interface RoadReportSpot {
  id: string;
  kind: string;
  lat: number;
  lng: number;
}

/** **بلاغاتُ الطريق** — أيقونةٌ وكلمة («صيانة» · «طريق مغلق» · «حادث» · «ازدحام»)؛ وقائمةٌ فارغةٌ تُفرغها. */
export function drawReports(instance: MapboxMap, host: HTMLElement, reports: RoadReportSpot[] | null) {
  const data = {
    type: "FeatureCollection" as const,
    features: (reports ?? []).map((report) => ({
      type: "Feature" as const,
      properties: { k: report.kind, t: REPORT_LABEL[report.kind] ?? "" },
      geometry: { type: "Point" as const, coordinates: [report.lng, report.lat] },
    })),
  };
  const source = instance.getSource(REPORTS_SOURCE) as GeoJSONSource | undefined;
  if (!reports) {
    if (instance.getLayer(REPORTS)) instance.removeLayer(REPORTS);
    if (source) instance.removeSource(REPORTS_SOURCE);
    return;
  }
  if (source) {
    source.setData(data);
    return;
  }
  const colors = tokens(host);
  instance.addSource(REPORTS_SOURCE, { type: "geojson", data });
  void addPinImages(instance as never, ["works", "closed", "accident", "jam"], colors.accent, colors.halo, colors.halo, OPEN_PREFIX).then(() => {
    if (!instance.getSource(REPORTS_SOURCE) || instance.getLayer(REPORTS)) return;
    const font = (instance.getLayer("poi-label") && instance.getLayoutProperty("poi-label", "text-font")) as string[] | undefined;
    instance.addLayer(
      {
        id: REPORTS,
        type: "symbol",
        source: REPORTS_SOURCE,
        layout: {
          "icon-image": ["concat", OPEN_PREFIX, ["get", "k"]],
          "icon-allow-overlap": true,
          "text-field": ["get", "t"],
          ...(font ? { "text-font": font } : {}),
          "text-size": 11,
          "text-anchor": "top",
          "text-offset": [0, 1.05],
          "text-optional": true,
        },
        paint: { "text-color": colors.accent, "text-halo-color": colors.halo, "text-halo-width": 1.5 },
      } as never,
      firstPresent(instance, ABOVE),
    );
  });
}

const REFRESH_MS = 120_000;

/** **المفاتيحُ وحدَها** — لأزرار الشاشة («الازدحام» · «أضف مكاناً» · «بلّغ») بلا قراءة طبقات. */
export function useOpenFlags() {
  const { user } = useSession();
  return {
    places: useFeature(user?.country_code, OPEN_PLACES_FLAG),
    traffic: useFeature(user?.country_code, TRAFFIC_FLAG),
    reports: useFeature(user?.country_code, REPORTS_FLAG),
    suggestions: useFeature(user?.country_code, SUGGESTIONS_FLAG),
  };
}

/** **مفاتيحُ الخريطة المفتوحة لسوق المستخدم، والازدحامُ والبلاغاتُ إن اشتعلت** — يُقرآن كلَّ دقيقتين ما دامت الخريطةُ معروضة.
 *  `trafficWanted=false` لا يطلب الازدحام (الراكبُ أطفأه، أو الكبتنُ خارج رحلة). */
export function useOpenLayers(trafficWanted: boolean) {
  const { user } = useSession();
  const places = useFeature(user?.country_code, OPEN_PLACES_FLAG);
  const trafficOn = useFeature(user?.country_code, TRAFFIC_FLAG);
  const reportsOn = useFeature(user?.country_code, REPORTS_FLAG);
  const suggestions = useFeature(user?.country_code, SUGGESTIONS_FLAG);
  const [traffic, setTraffic] = useState<Collection | null>(null);
  const [reports, setReports] = useState<RoadReportSpot[] | null>(null);

  useEffect(() => {
    if (!trafficOn || !trafficWanted || !user) {
      setTraffic(null);
      return;
    }
    let live = true;
    const load = () =>
      void api
        .get<Collection>("/map/traffic")
        .then((data) => live && setTraffic(data))
        .catch(() => live && setTraffic(EMPTY));
    load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [trafficOn, trafficWanted, user]);

  useEffect(() => {
    if (!reportsOn || !user) {
      setReports(null);
      return;
    }
    let live = true;
    const load = () =>
      void api
        .get<RoadReportSpot[]>("/map/road-reports")
        .then((rows) => live && setReports(rows))
        .catch(() => undefined);
    load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [reportsOn, user]);

  return { places, trafficAvailable: trafficOn, traffic, reportsOn, reports, suggestions };
}
