/** لوحُ مسارِ رحلةٍ جاريةٍ داخل ملفِّ الكبتن — البند ٦ (§39٫٦).
 *
 * **وهو ثالثُ ملفٍّ في اللوحة يعرف `mapbox-gl`** (مع `LiveCanvas` و
 * `SkinMapPreview`) — **ولا يُدمج بأولهما**. ذاك يرسم **جماعةً بلا خطّ**:
 * عشراتِ الكباتن وطلباتٍ معلّقة، علاماتٍ تُنقل ولا تُبنى. وهذا يرسم **واحداً
 * ومعه خطُّه**: مصدرَ `GeoJSON` وطبقةَ خطٍّ تُعادان بعد كلِّ تبديل سمة، ومجالاً
 * يُضبط مرّةً واحدةً على الرحلة. **ومكوّنٌ واحدٌ بخصائصَ اختياريةٍ لهما** يجعل
 * نصفَ خصائصه ميتاً في كلِّ موضعٍ يُستعمل فيه، ويُخفي أن أحدهما يحمل طبقةَ
 * أسلوبٍ والآخرَ لا يحمل.
 *
 * ## ثلاثةُ فروقٍ عن `LiveCanvas` كلُّها من واقع الأداة لا من الذوق
 *
 * ١. **`Marker` ينجو من `setStyle` والطبقةُ لا تنجو.** تبديلُ السمة يمسح كلَّ
 *    مصدرٍ وطبقةٍ أضافها المستعمل، **ولا خطأَ يظهر** — يختفي الخطُّ وحدَه
 *    وتبقى الدبابيس. فالخطُّ يُعاد رسمُه على `style.load`، والدبابيسُ علامات.
 *
 * ٢. **والمجالُ يُضبط مرّةً**: `fitBounds` عند كلِّ استطلاعٍ ينتزع التقريبَ
 *    من يد المشرف كلَّ خمس ثوانٍ — وهي علّةُ «التوسيطُ مرّةً عند الاختيار»
 *    في `LiveCanvas` بحرفها.
 *
 * ٣. **ولا تنعيمَ لحركة الدبّوس**: المشرف يسأل «أين هو الآن»، ودبّوسٌ يزحف
 *    نحو موضعٍ قديمٍ يجيبه بموضعٍ لم يكن صحيحاً حين نظر.
 *
 * **وبلا توكن Mapbox** (عقدٌ غيرُ مفعَّل) تظهر لوحةٌ تقول السببَ ويبقى ما
 * حولها من نصّ — كما في `LiveCanvas`: الخريطةُ عرضٌ لِما تقوله السطور، لا
 * بديلٌ عنها.
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// يقع عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import type { DriverLivePosition, RidePoint } from "@/api/types";
import { useTheme } from "@/lib/theme";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

const ROUTE_SOURCE = "ride-route";
const ROUTE_LAYER = "ride-route-line";

interface Props {
  token: string | null;
  pickup: { lat: number; lng: number };
  dropoff: { lat: number; lng: number };
  route: RidePoint[];
  /** `null` = لا بثّ الآن. **فلا دبّوسَ يُرسم**، ولا يُوضع عند الصفر. */
  position: DriverLivePosition | null;
}

/** غلافُ العلامة **يملكه mapbox** — والشكلُ في ابنٍ داخله.
 *
 * `Marker` يضيف صنفَه (`mapboxgl-marker`، وفيه `position:absolute`) إلى
 * العنصر الممرَّر، **فكتابةُ `className` عليه تُسقط العلامةَ إلى تدفّق الصفحة
 * وتختفي بلا خطأٍ في الطرفية**. وهو عطبٌ وقع في `LiveCanvas` فعلاً.
 */
function shell(className: string, title: string): HTMLElement {
  const node = document.createElement("div");
  const face = document.createElement("span");
  face.className = className;
  face.title = title;
  node.appendChild(face);
  return node;
}

const PIN_PICKUP = "block size-12 rounded-full border-2 border-ok bg-bg";
const PIN_DROPOFF = "block size-12 rounded-full border-2 border-ink bg-ink";
const DOT_LIVE = "block size-16 rounded-full border-2 border-bg bg-accent";
const DOT_STALE = "block size-16 rounded-full border-2 border-bg bg-warn";

export function RouteCanvas({ token, pickup, dropoff, route, position }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const pins = useRef<{
    pickup: mapboxgl.Marker;
    dropoff: mapboxgl.Marker;
  } | null>(null);
  const live = useRef<mapboxgl.Marker | null>(null);
  const fitted = useRef(false);
  const { dark } = useTheme();

  // **آخرُ مسارٍ في مرجع**: مُصغي `style.load` يعيش أطولَ من الرسمة التي
  // سجّلته، **فقراءةُ `route` من إغلاقه تعيد رسمَ مسارِ لحظةِ التسجيل**.
  const latest = useRef(route);
  latest.current = route;

  useEffect(() => {
    if (!token || !holder.current || map.current) return;
    mapboxgl.accessToken = token;
    const instance = new mapboxgl.Map({
      container: holder.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      language: MAP_LANGUAGE,
      center: [pickup.lng, pickup.lat],
      zoom: 12,
      attributionControl: false,
    });
    map.current = instance;

    const paint = () => paintRoute(instance, latest.current);
    instance.on("load", paint);
    // **يُعاد بعد كلِّ تبديل سمة**: `setStyle` يمسح المصادرَ والطبقات
    instance.on("style.load", paint);

    return () => {
      instance.remove();
      map.current = null;
      pins.current = null;
      live.current = null;
      fitted.current = false;
    };
    // التوكنُ وحدَه ينشئ الخريطة — والسمةُ والمركزُ الأوّليّان يُقرآن مرّةً
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  // ── دبّوسا الانطلاق والوجهة ──────────────────────────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    if (!pins.current) {
      pins.current = {
        // **الموضع قبل `addTo`**: الإضافة ترسم فوراً وتقرأ الإحداثيات،
        // فعلامةٌ بلا موضعٍ ترمي داخل تأثيرٍ وتُبيّض الشاشةَ كلَّها
        pickup: new mapboxgl.Marker({
          element: shell(PIN_PICKUP, "نقطة الانطلاق"),
        })
          .setLngLat([pickup.lng, pickup.lat])
          .addTo(instance),
        dropoff: new mapboxgl.Marker({ element: shell(PIN_DROPOFF, "الوجهة") })
          .setLngLat([dropoff.lng, dropoff.lat])
          .addTo(instance),
      };
      return;
    }
    pins.current.pickup.setLngLat([pickup.lng, pickup.lat]);
    pins.current.dropoff.setLngLat([dropoff.lng, dropoff.lat]);
  }, [pickup.lat, pickup.lng, dropoff.lat, dropoff.lng]);

  // ── الخطّ ────────────────────────────────────────────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance || !instance.isStyleLoaded()) return;
    paintRoute(instance, route);
  }, [route]);

  // ── الدبّوس الحيّ — **يُنقل ولا يُبنى** ───────────────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    if (position === null) {
      live.current?.remove();
      live.current = null;
      return;
    }
    const face = position.stale ? DOT_STALE : DOT_LIVE;
    const title = position.stale ? "بثُّه توقّف — آخرُ موضعٍ وصل" : "موقعُه الآن";
    if (!live.current) {
      live.current = new mapboxgl.Marker({ element: shell(face, title) })
        .setLngLat([position.lng, position.lat])
        .addTo(instance);
      return;
    }
    live.current.setLngLat([position.lng, position.lat]);
    const node = live.current.getElement().firstElementChild as HTMLElement;
    node.className = face;
    node.title = title;
  }, [position]);

  // ── المجال: **مرّةً واحدة** ──────────────────────────────────────────────
  useEffect(() => {
    const instance = map.current;
    if (!instance || fitted.current) return;
    fitted.current = true;
    const bounds = new mapboxgl.LngLatBounds();
    bounds.extend([pickup.lng, pickup.lat]);
    bounds.extend([dropoff.lng, dropoff.lat]);
    for (const point of route) bounds.extend([point.lng, point.lat]);
    if (position) bounds.extend([position.lng, position.lat]);
    instance.fitBounds(bounds, { padding: 40, maxZoom: 15, duration: 0 });
  }, [pickup.lat, pickup.lng, dropoff.lat, dropoff.lng, route, position]);

  if (!token) {
    return (
      <div className="flex h-170 items-center justify-center rounded-14 border border-line bg-surface-2 px-20 text-center">
        <p className="text-11 leading-note text-muted">
          عقدُ Mapbox غير مفعّل لهذه الدولة، فلا خريطة. والسطورُ تحتها تقول حالَ
          الرحلة وطرفَيها.
        </p>
      </div>
    );
  }

  return <div ref={holder} className="h-170 w-full rounded-14" />;
}

/** يضيف مصدرَ المسار وطبقتَه إن غابا، ثمّ يكتب فيهما — **لا يبنيهما مرّتين**. */
function paintRoute(instance: mapboxgl.Map, route: RidePoint[]) {
  const data: GeoJSON.Feature<GeoJSON.LineString> = {
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      // **أقلُّ من نقطتين ليس خطّاً**: مصفوفةٌ فارغةٌ ترسم لا شيء — وهي الحالُ
      // الصحيحة في أوّل دقيقةٍ من الرحلة، لا عطب
      coordinates:
        route.length >= 2 ? route.map((point) => [point.lng, point.lat]) : [],
    },
  };

  const source = instance.getSource(ROUTE_SOURCE) as
    | mapboxgl.GeoJSONSource
    | undefined;
  if (source) {
    source.setData(data);
    return;
  }
  instance.addSource(ROUTE_SOURCE, { type: "geojson", data });
  instance.addLayer({
    id: ROUTE_LAYER,
    type: "line",
    source: ROUTE_SOURCE,
    layout: { "line-cap": "round", "line-join": "round" },
    // **لونٌ من رمز السمة لا قيمةٌ ثابتة**: السمتان تتبادلان تحت الخطّ، ولونٌ
    // واحدٌ يذوب في إحداهما
    paint: {
      "line-color": lineColour(),
      "line-width": 3,
      "line-opacity": 0.9,
    },
  });
}

/** لونُ الخطّ من متغيّر السمة القائم — و`#2563eb` مخرجٌ لا يقع إلا بلا سمة. */
function lineColour(): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue("--acc")
    .trim();
  return value || "#2563eb";
}
