/** خريطةُ «مناطق التسعير» (SPEC §٧٤-أ/٥) — **عرضٌ لا كتابة**: حدودُ كلِّ منطقة، **والوعرةُ بالجمر** وغيرُها بخطٍّ خافت، والمختارةُ بحافّةٍ
 * أعرض. **والنقرُ على منطقةٍ يختارها** في الجدول بجانبها.
 *
 * **خامسُ ملفٍّ يعرف `mapbox-gl`، ولا يُدمج بأحدها** (علّةُ `AreaCanvas` نفسُها): ذاك يكتب، وهذا يعرض مجموعةً كاملة. **وقاعدتاه من أخيه**:
 * الطبقةُ تُعاد بعد كلِّ `setStyle` (`style.load`)، والألوانُ من رموز السمة لا ثوابت.
 */
import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

import { MAP_LANGUAGE } from "@/lib/map-rtl";
import { MAP_STYLE_DARK, MAP_STYLE_LIGHT, taxoLook, tokenColour } from "@/lib/taxo-map";
import { useTheme } from "@/lib/theme";

const SOURCE = "pricing-zones";
const FILL = "pricing-zones-fill";
const LINE = "pricing-zones-line";
const PICKED = "pricing-zones-picked";

interface Props {
  token: string;
  data: GeoJSON.FeatureCollection | null;
  picked: string | null;
  onPick: (zoneId: string) => void;
}

function paint(instance: mapboxgl.Map, data: GeoJSON.FeatureCollection, picked: string | null, host: HTMLElement | null) {
  const accent = tokenColour(host, "--t2-accent") || "#f05a28";
  const ink = tokenColour(host, "--t2-text") || "#14161a";
  const faint = tokenColour(host, "--t2-faint") || "#a8a398";
  const source = instance.getSource(SOURCE) as mapboxgl.GeoJSONSource | undefined;
  if (source) source.setData(data);
  else {
    instance.addSource(SOURCE, { type: "geojson", data });
    instance.addLayer({
      id: FILL,
      type: "fill",
      source: SOURCE,
      paint: { "fill-color": ["case", ["get", "rugged"], accent, faint], "fill-opacity": ["case", ["get", "rugged"], 0.28, 0.06] },
    });
    instance.addLayer({
      id: LINE,
      type: "line",
      source: SOURCE,
      paint: { "line-color": ["case", ["get", "rugged"], accent, faint], "line-width": 1 },
    });
    instance.addLayer({
      id: PICKED,
      type: "line",
      source: SOURCE,
      filter: ["==", ["get", "id"], picked ?? ""],
      paint: { "line-color": ink, "line-width": 3 },
    });
  }
  instance.setFilter(PICKED, ["==", ["get", "id"], picked ?? ""]);
}

export function ZonesCanvas({ token, data, picked, onPick }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const { dark } = useTheme();
  const shown = useRef<string | null>(null);
  const latest = useRef({ data, picked });
  latest.current = { data, picked };
  const report = useRef(onPick);
  report.current = onPick;

  useEffect(() => {
    if (!token || !holder.current || map.current) return;
    mapboxgl.accessToken = token;
    const host = holder.current;
    const style = dark ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;
    shown.current = style;
    const instance = new mapboxgl.Map({ container: host, style, language: MAP_LANGUAGE, center: [2.6, 28.0], zoom: 3.6, attributionControl: false });
    map.current = instance;
    const draw = () => {
      if (latest.current.data) paint(instance, latest.current.data, latest.current.picked, host);
    };
    instance.on("load", draw);
    instance.on("style.load", () => {
      taxoLook(instance, host);
      draw();
    });
    instance.on("click", FILL, (event) => {
      const id = event.features?.[0]?.properties?.id;
      if (typeof id === "string") report.current(id);
    });
    instance.on("mouseenter", FILL, () => (instance.getCanvas().style.cursor = "pointer"));
    instance.on("mouseleave", FILL, () => (instance.getCanvas().style.cursor = ""));
    return () => {
      instance.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    const instance = map.current;
    const style = dark ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;
    if (!instance || shown.current === style) return;
    shown.current = style;
    instance.setStyle(style, { diff: false } as Parameters<mapboxgl.Map["setStyle"]>[1]);
  }, [dark]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !data || !instance.isStyleLoaded()) return;
    paint(instance, data, picked, holder.current);
  }, [data, picked]);

  return <div ref={holder} className="h-[420px] w-full overflow-hidden rounded-16 border border-line" role="img" aria-label="خريطةُ مناطق التسعير" />;
}
