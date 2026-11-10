/** **طبقةُ خريطة الطلب** (البند ١٨، ٢٠٢٦-١١-١٠) — `heatmap` من نقاطٍ موزونة (مراكزُ خلايا لا مواضعُ ركّاب)، **و`null` تزيلها**.
 *  وتُعاد مع كلِّ ستايلٍ يُحمَّل كطبقة الزحام: التبديلُ يمسح الطبقات. */
import type { GeoJSONSource, Map as MapboxMap } from "mapbox-gl";

export interface HeatPoint {
  lat: number;
  lng: number;
  /** ٠…١ */
  weight: number;
}

const HEAT = "taxo-heat";

export function drawHeat(instance: MapboxMap, points: HeatPoint[] | null): void {
  if (points === null) {
    if (instance.getLayer(HEAT)) instance.removeLayer(HEAT);
    if (instance.getSource(HEAT)) instance.removeSource(HEAT);
    return;
  }
  const data: GeoJSON.FeatureCollection = {
    type: "FeatureCollection",
    features: points.map((point) => ({
      type: "Feature",
      properties: { w: point.weight },
      geometry: { type: "Point", coordinates: [point.lng, point.lat] },
    })),
  };
  const source = instance.getSource(HEAT) as GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
    return;
  }
  instance.addSource(HEAT, { type: "geojson", data });
  // **تحت الأسماء** — أوّلُ طبقةِ رموزٍ في الستايل، فلا تغطّي الحرارةُ اسمَ شارع
  const before = instance.getStyle()?.layers?.find((layer) => layer.type === "symbol")?.id;
  instance.addLayer(
    {
      id: HEAT,
      type: "heatmap",
      source: HEAT,
      paint: {
        "heatmap-weight": ["get", "w"],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 9, 0.7, 14, 1.4],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 9, 18, 13, 42, 16, 80],
        "heatmap-opacity": 0.75,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(255, 140, 50, 0)",
          0.3,
          "rgba(255, 170, 60, 0.45)",
          0.6,
          "rgba(255, 110, 40, 0.7)",
          1,
          "rgba(215, 40, 20, 0.9)",
        ],
      },
    },
    before,
  );
}
