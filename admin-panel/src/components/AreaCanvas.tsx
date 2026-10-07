/** لوحُ رسمِ منطقة مرفقٍ حيويّ — «المرافق الحيوية» (§٦٣-ج/٢).
 *
 * **وهو رابعُ ملفٍّ في اللوحة يعرف `mapbox-gl`** (مع `LiveCanvas` و`RouteCanvas` و`SkinMapPreview`) — **ولا يُدمج بأحدها**:
 * أولئك يعرضون ما وقع، **وهذا وحدَه يكتب**: النقرُ يضيف نقطة، والسحبُ يحرّكها. ومكوّنٌ واحدٌ بخصائصَ اختياريةٍ للعرض والكتابة
 * يجعل الخريطةَ الحيّةَ يوماً تضيف نقطةً بنقرةٍ منسيّة.
 *
 * **والتوكنُ من حيث يأخذه أخواه** (`config.providers.mapbox.public_token` يمرّره المستدعي) — لا مصدرَ ثانٍ. **والملحقُ العربيُّ**
 * من `lib/map-rtl` الواحد، لأن `setRTLTextPlugin` عامٌّ على الوحدة ويرمي إن نُودي مرّتين.
 *
 * ## ثلاثُ قواعدَ كلُّها من واقع الأداة لا من الذوق
 *
 * ١. **`Marker` ينجو من `setStyle` والطبقةُ لا تنجو** (درسُ `RouteCanvas`): تبديلُ السمة يمسح المصدرَ والطبقتين بلا خطأ،
 *    فيُعاد رسمُهما على `style.load` — **والرؤوسُ علاماتٌ** تبقى، ويُسحب كلٌّ منها بسحب mapbox نفسِه (`draggable`).
 * ٢. **النقرةُ على رأسٍ ليست نقطةً جديدة**: النقرُ على علامةٍ يصعد إلى الخريطة فيطلق `click`، **فبلا الفحص تضيف كلُّ
 *    محاولةِ سحبٍ قصيرةٍ نقطةً فوق رأسٍ قائم**. ولا يُوقف صعودُه من العلامة — سحبُها نفسُه يقرأ `mousedown` الخريطة.
 * ٣. **والمجالُ يُضبط مرّةً** عند الفتح على المضلّع القائم — **ولا يُعاد مع كلِّ نقطة**: خريطةٌ تقفز تحت المؤشّر بين نقرتين
 *    تضع الثالثةَ حيث لم يقصد.
 *
 * **والحلقةُ لا تُغلق في البيانات**: النقطةُ الأولى تُكرَّر في آخر المضلّع **للرسم وحدَه** (GeoJSON يشترطها)، وما يصل الخلفيةَ
 * هو ما رسمه المشرفُ بلا تكرار — والخلفيةُ تُغلقه (`services/facilities.py::_ring_wkt`).
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// يقع عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import type { LngLat } from "@/api/types";
import { MAP_STYLE_DARK, MAP_STYLE_LIGHT, taxoLook, tokenColour } from "@/lib/taxo-map";
import { useTheme } from "@/lib/theme";

const AREA_SOURCE = "facility-area";
const AREA_FILL = "facility-area-fill";
const AREA_LINE = "facility-area-line";

interface Props {
  token: string | null;
  /** مركزُ البداية حين لا مضلّعَ بعد — **مطارُ العاصمة** يمرّره المستدعي لسوقه. */
  center: LngLat;
  points: LngLat[];
  onChange: (next: LngLat[]) => void;
}

/** غلافُ العلامة **يملكه mapbox** والشكلُ في ابنٍ داخله — `className` على الغلاف يمسح `mapboxgl-marker` فتسقط العلامةُ
 *  إلى تدفّق الصفحة بلا خطأ (عطبٌ وقع في `LiveCanvas`). */
function vertexShell(): HTMLElement {
  const shell = document.createElement("div");
  shell.appendChild(document.createElement("span"));
  return shell;
}

/** **الأولى ممتلئةٌ بالجمر** — منها بدأ الرسم وإليها تعود الحلقة، **والبقيّةُ حلقاتٌ** تُسحب. والرقمُ في التلميح. */
function paintVertex(shell: HTMLElement, index: number) {
  const face = shell.firstElementChild as HTMLElement;
  face.className = index === 0 ? "ad-map-vertex first" : "ad-map-vertex";
  face.title = `النقطة ${index + 1} — اسحبها لتحرّكها`;
}

export function AreaCanvas({ token, center, points, onChange }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const vertices = useRef<mapboxgl.Marker[]>([]);
  const { dark } = useTheme();
  // **الستايلُ المعروضُ الآن** — يُقارَن به قبل التبديل (تحت)
  const shown = useRef<string | null>(null);

  // **آخرُ النقاط والمُبلِّغ في مرجعين**: مُصغيا `click` و`dragend` يعيشان أطولَ من الرسمة التي سجّلتهما، **فقراءتُهما من
  // إغلاقهما تبني على نقاطِ لحظةِ التسجيل** — فتمحو النقرةُ الثالثةُ الثانية.
  const latest = useRef(points);
  latest.current = points;
  const report = useRef(onChange);
  report.current = onChange;

  useEffect(() => {
    if (!token || !holder.current || map.current) return;
    mapboxgl.accessToken = token;
    const host = holder.current;
    const style = dark ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;
    shown.current = style;
    const instance = new mapboxgl.Map({
      container: host,
      style,
      language: MAP_LANGUAGE,
      center,
      zoom: 12,
      attributionControl: false,
    });
    map.current = instance;
    // **مؤشّرُ الرسم** — النقرُ هنا يضيف، ولا يُقرأ يداً تسحب الخريطة
    instance.getCanvas().style.cursor = "crosshair";

    // **المجالُ مرّةً على المضلّع القائم** (رأسُ الملفّ ٣) — ومضلّعٌ جديدٌ يبدأ من المطار
    if (latest.current.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      for (const point of latest.current) bounds.extend(point);
      instance.fitBounds(bounds, { padding: 48, maxZoom: 16, duration: 0 });
    }

    const paint = () => paintArea(instance, latest.current, host);
    instance.on("load", paint);
    // **يُعاد بعد كلِّ تبديل سمة**: `setStyle` يمسح المصادرَ والطبقات — **والصبغُ معه** («TaxoMap»)
    instance.on("style.load", () => {
      taxoLook(instance, host);
      paint();
    });

    instance.on("click", (event) => {
      // **النقرةُ على رأسٍ قائمٍ ليست نقطة** (رأسُ الملفّ ٢)
      const target = event.originalEvent.target as HTMLElement | null;
      if (target?.closest(".mapboxgl-marker")) return;
      // **ستُّ خاناتٍ عشرية** — ما تردّه الخلفيةُ نفسُها (`area_points`)، فلا يُقرأ المضلّعُ «تغيّر» لفرقٍ تحت المتر
      const point: LngLat = [
        Number(event.lngLat.lng.toFixed(6)),
        Number(event.lngLat.lat.toFixed(6)),
      ];
      report.current([...latest.current, point]);
    });

    return () => {
      instance.remove();
      map.current = null;
      vertices.current = [];
    };
    // التوكنُ وحدَه ينشئ الخريطة — والسمةُ والمركزُ الأوّليّان يُقرآن مرّةً
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // **يُبدَّل الستايلُ حين تتبدّل السمةُ لا عند التركيب** — وبـ`diff: false` تحميلٌ كاملٌ يطلق `style.load` فيعود الصبغُ
  // والمضلّع (العلّةُ مقيسةٌ ومكتوبةٌ في `RouteCanvas`)
  useEffect(() => {
    const instance = map.current;
    const style = dark ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;
    if (!instance || shown.current === style) return;
    shown.current = style;
    instance.setStyle(style, { diff: false } as Parameters<mapboxgl.Map["setStyle"]>[1]);
  }, [dark]);

  // ── المضلّع ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance || !instance.isStyleLoaded()) return;
    paintArea(instance, points, holder.current);
  }, [points]);

  // ── الرؤوس — **تُنقل ولا تُبنى**، والزائدُ يُزال ───────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const list = vertices.current;
    points.forEach((point, index) => {
      const existing = list[index];
      if (existing) {
        existing.setLngLat(point);
        paintVertex(existing.getElement(), index);
        return;
      }
      const element = vertexShell();
      paintVertex(element, index);
      // **الموضع قبل `addTo`**: الإضافةُ ترسم فوراً وتقرأ الإحداثيات، فعلامةٌ بلا موضعٍ ترمي داخل تأثيرٍ وتُبيّض الشاشة
      const marker = new mapboxgl.Marker({ element, draggable: true })
        .setLngLat(point)
        .addTo(instance);
      marker.on("dragend", () => {
        // **موضعُ العلامة في القائمة ساعةَ الإفلات** لا ساعةَ البناء — فالتراجعُ قبلها لا يُزيح الفهرس
        const at = vertices.current.indexOf(marker);
        if (at < 0) return;
        const moved = marker.getLngLat();
        const next = [...latest.current];
        next[at] = [Number(moved.lng.toFixed(6)), Number(moved.lat.toFixed(6))];
        report.current(next);
      });
      list.push(marker);
    });
    while (list.length > points.length) list.pop()?.remove();
  }, [points]);

  if (!token) {
    return (
      <div className="ad-map-off">
        <p>
          عقدُ Mapbox غير مفعّل لهذه الدولة، فلا خريطةَ تُرسم عليها المنطقة.
          <br />
          الاسمُ والرسمُ والتفعيلُ تُحفظ، والمنطقةُ القائمةُ تبقى كما هي.
        </p>
      </div>
    );
  }

  return <div ref={holder} className="ad-map" />;
}

/** يضيف مصدرَ المنطقة وطبقتيه إن غابت، ثمّ يكتب فيها — **لا يبنيها مرّتين**.
 *
 * **ثلاثُ نقاطٍ فأكثر مضلّعٌ مملوء، ونقطتان خطٌّ بينهما، وأقلُّ لا شيء** — فيرى المشرفُ ما رسمه منذ النقرة الثانية. */
function paintArea(instance: mapboxgl.Map, points: LngLat[], host: HTMLElement | null) {
  const features: GeoJSON.Feature[] = [];
  if (points.length >= 3) {
    features.push({
      type: "Feature",
      properties: {},
      // **الإغلاقُ للرسم وحدَه** (رأسُ الملفّ) — لا يُرسل
      geometry: { type: "Polygon", coordinates: [[...points, points[0]]] },
    });
  } else if (points.length === 2) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: points },
    });
  }
  const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features };

  const source = instance.getSource(AREA_SOURCE) as mapboxgl.GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
    return;
  }
  // **لونٌ من رمز السمة لا قيمةٌ ثابتة** — `paint` لا يقرأ `var()`، والرموزُ على الحاوية لا على `<html>` (درسُ `RouteCanvas`)
  const accent = tokenColour(host, "--t2-accent") || "#f05a28";
  instance.addSource(AREA_SOURCE, { type: "geojson", data });
  instance.addLayer({
    id: AREA_FILL,
    type: "fill",
    source: AREA_SOURCE,
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": accent, "fill-opacity": 0.18 },
  });
  instance.addLayer({
    id: AREA_LINE,
    type: "line",
    source: AREA_SOURCE,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": accent, "line-width": 2.5 },
  });
}
