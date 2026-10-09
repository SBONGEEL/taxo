/** خريطة Mapbox — العنصر الوحيد الذي يعرف واجهة `mapbox-gl` (SPEC القسم 2).
 *
 * ثلاث مسؤوليات في تطبيق الكبتن:
 *
 * 1. **موقعُ الكبتن نفسه** — **مركبتُه المفعَّلة** تدور مع الاتجاه (أو تُعرض
 *    ثابتةً إن صُرِّح `map_rotates: false`)، وحركتُها منعَّمة بين البثّات (كل
 *    ثلاث ثوانٍ) فلا تقفز الأيقونة قفزةً كل دورة. **ويراها هو وحدَه**: لا
 *    تُنشر لأحد، ولا تغيّر شرطَ الأهلية، ولا تمسّ ما يصل الراكب. ومن لا
 *    اشتراكَ له يرى الرماديةَ الباهتةَ مكانَها — **حالُ حسابٍ على شاشته لا
 *    وشايةٌ بفئة**.
 *
 * 1-ب. **زملاؤه حوله** (اختياريّ، خلف مفتاحٍ مطفأ) — **مجهَّلين بالسيارة
 *    العامّة كما يراهم الراكبُ سواءً بسواء**، لا بمركبةِ أحد: ما يُرى ويندر
 *    يصير معرّفاً ينقض تجهيلَ §10.
 * 2. **دبوسا الانطلاق والوصول** أثناء الرحلة.
 * 3. **الخلفيةُ النائبة** حين لا توكن (عقد Mapbox غير مفعّل): شريطٌ مائل
 *    بلونَي `--sa`/`--sb` كما في التصميم، لا شاشةٌ بيضاء — بقيةُ التطبيق
 *    تعمل، وبطاقةُ الطلب لا تحتاج خريطة.
 *
 * 4. **خطُّ المسار على الطرق** (البند ٨، 2026-08-14) — يصل من الخلفية مجمَّداً
 *    على الرحلة منذ القبول، فما يراه الكبتن هو ما يراه راكبُه بالضبط.
 *
 * **ولا يزال لا يُرسم خطٌّ من عندنا**: هندسةُ المسار تأتي من Mapbox Directions
 * ونداؤها من الخلفية حصراً (القسم 2/14)، وخطٌّ نرسمه بين نقطتين يوهم بمسارٍ لم
 * يقله أحد (`DESIGN-DECISIONS` بند 38). والفرقُ بين الاثنين هو الفرقُ كلُّه:
 * هذا **مسارٌ قاله Mapbox**، وذاك خطٌّ نخترعه.
 */

import mapboxgl from "mapbox-gl";
import { Compass, LocateFixed, Navigation2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// **يقع باستيراد الاسم كما يقع بالاستيراد المجرَّد**: الوحدةُ تُقيَّم مرّةً
// عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";
import { applyLabels, drawOwnPlaces, labelColors, styleSymbolLayer, useMapPlaces } from "@/lib/map-labels";

import type { Coordinates, NearbyDriver, VehicleSkin } from "@/api/types";
import { type FollowMode, labelFor, nextMode } from "@/lib/follow";
import {
  applyMarkerHeading,
  headingTarget,
  nearbyMarkerElement,
  selfMarkerElement,
} from "@/lib/skin-marker";
import { trimRoute } from "@/lib/route-line";
import { useMapboxMissing } from "@/lib/config";
import { useTheme } from "@/lib/theme";
import { digits, cn } from "@/lib/utils";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

// أقصرُ قليلاً من دورة البثّ (3s) فتصل الأيقونة موضعها قبيل وصول التالي
const TWEEN_MS = 2_600;

interface Props {
  token: string | null;
  center: Coordinates | null;
  heading?: number | null;
  pickup?: Coordinates | null;
  dropoff?: Coordinates | null;
  /** يضم النقطتين في الإطار — أثناء الرحلة لا قبلها. */
  fit?: boolean;
  /** **والخطَّ كلَّه معهما** (مع `fit`) — للمسار الذي سارته رحلةٌ انتهت (C17d، §٦٢-ج/١١): طريقٌ انعطف بعيداً عن المستقيم
   *  يخرج من إطارٍ يضمّ طرفيه وحدهما. **وبلا هذا الوسيط لا يتغيّر إطارُ أحد** — الرئيسيةُ وورقتُها كما كانتا. */
  fitRoute?: boolean;
  /** **حشوُ الإطار بالبكسل** (مع `fit`) — والافتراضيُّ ٨٠ من كلِّ جهةٍ لخريطةٍ تملأ الشاشة. **وشريطٌ بارتفاع ٢٠٠** (C17) يبقى له
   *  منها ٤٠ بكسلاً فيُرسم الخطُّ نقطةً (قِيس) — فيمرّر حشوَه. */
  fitPadding?: number | { top: number; bottom: number; left: number; right: number };
  /** **مسارُ الرحلة على الطرق كما قاله Mapbox** — `[[lng, lat], …]` (البند ٨).
   *
   *  وهذا لا ينقض «لا خطَّ مسارٍ بين النقطتين» في رأس هذا الملف: ذاك يمنع خطاً
   *  **نرسمه نحن** فيوهم بمسارٍ لم يقله أحد، وهذا مسارٌ **قاله Mapbox** وجُمِّد
   *  على الرحلة لحظةَ القبول — فما يراه الكبتن هو ما يراه راكبُه بالضبط. */
  routePoints?: number[][] | null;
  /** موضعُه الآن — ما مضى من المسار يُقصّ خلفه (تتبّعُ التقدّم بعد البدء). */
  trimAt?: Coordinates | null;
  /** دقائقُ الوصول — **محسوبةٌ في الجهاز** (البند ١٧-٣)، و`null` فلا يُعرض شيء:
   *  رقمٌ مبنيٌّ على سرعةٍ لم تُقَس يُقرأ وعداً ثم يُخلَف. */
  etaMinutes?: number | null;
  /** **مركبتُه المفعَّلة** — و`null` تُرسم السيارةَ العامّة. */
  selfSkin?: VehicleSkin | null;
  /** **لا اشتراكَ له**: تُرسم رماديةً باهتة. ويأتي من الشاشة نفسِها التي
   *  ترسم لافتةَ الاشتراك وزرَّ الاستقبال، فلا يقول الموضعان شيئين. */
  subscribed?: boolean;
  /** **زملاؤه حوله — مجهَّلين كما يراهم الراكب**، و`null` تعني «الميزةُ غيرُ
   *  مفتوحةٍ في سوقه» فلا يُرسم شيءٌ ولا يُقال شيء. */
  colleagues?: NearbyDriver[] | null;
  className?: string;
  /** **خريطةُ TAXO 2.0 بلغة «TaxoMap»** (C04–C07، الليليُّ المرسوم وحدَه): الأرضُ والحدائقُ والطرقُ من رموز `--t2-map-*`
   *  بلا أسماءٍ ولا معالم، ودبوسا الهوية، وخطُّ الجمر فوق ظلّه، وزرُّ الموقع بلغة اللوحة — **والوصولُ المتوقَّعُ في
   *  الورقة لا فوق الخريطة**. **ولا يمرّره إلا `screens/t2`**: الشاشاتُ القائمةُ بخريطتها كما هي حرفاً. */
  t2?: boolean;
  /** **ما مضى من المسار يُرسم خافتاً** (C07) بدل أن يُقصّ — والباقي بالجمر فوقه. مع `t2` وحدَه. */
  routeTraveled?: boolean;
  /** **طبقةُ الزحام** (§٦٢-ج/٤٨) — تفضيلُ الجهاز (`driving-prefs`)؛ مع `t2` وحدَه. */
  traffic?: boolean;
  /** **النقرُ على الخريطة** (بطاقةُ النقر، §٦٢-ج/٤٨) — يُمرَّر حيث يُقصد وحدَه (الخريطةُ الموسَّعة)؛ مع `t2` وحدَه. */
  onTap?: ((at: Coordinates) => void) | null;
  /** دبوسُ النقطة المنقورة — حتى تُغلق بطاقتُها. */
  tapPin?: Coordinates | null;
}

/** **طبقةُ الزحام** من `mapbox-traffic-v1` (§٦٢-ج/٤٨): **المزدحمُ وحدَه يُرسم** (متوسّط · كثيف · شديد) — والطريقُ السالكُ لا خطَّ
 *  له، فلا تصير الخريطةُ كلُّها ألواناً. **وألوانُها من رموز الحاوية** (`--t2-warning` · `--t2-danger`) لا من لوحةٍ مكتوبة،
 *  **وتحت خطِّ المسار لا فوقه**: المسارُ هو ما يقوده الكبتن، والزحامُ سياقُه. */
const TRAFFIC = "taxo-traffic";
const ROUTE_LAYERS = ["taxo-route-line-done", "taxo-route-line-casing", "taxo-route-line"];

function addTraffic(instance: mapboxgl.Map, host: HTMLElement) {
  if (instance.getLayer(TRAFFIC)) return;
  const css = getComputedStyle(host);
  const warning = css.getPropertyValue("--t2-warning").trim();
  const danger = css.getPropertyValue("--t2-danger").trim();
  if (!warning || !danger) return;
  if (!instance.getSource(TRAFFIC)) {
    instance.addSource(TRAFFIC, { type: "vector", url: "mapbox://mapbox.mapbox-traffic-v1" });
  }
  const before = ROUTE_LAYERS.find((id) => instance.getLayer(id));
  instance.addLayer(
    {
      id: TRAFFIC,
      type: "line",
      source: TRAFFIC,
      "source-layer": "traffic",
      filter: ["in", ["get", "congestion"], ["literal", ["moderate", "heavy", "severe"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "congestion"], "moderate", warning, danger],
        "line-width": [
          "interpolate", ["linear"], ["zoom"],
          11, ["match", ["get", "congestion"], "severe", 2.5, 1.5],
          16, ["match", ["get", "congestion"], "severe", 6, 4],
        ],
        "line-opacity": 0.85,
      },
    },
    before,
  );
}

function removeTraffic(instance: mapboxgl.Map) {
  if (instance.getLayer(TRAFFIC)) instance.removeLayer(TRAFFIC);
  if (instance.getSource(TRAFFIC)) instance.removeSource(TRAFFIC);
}

/** الطرقُ الكبرى بلون الطريق، وما سواها بلون الشارع — كما في خريطة الراكب (`customer-app/components/map`). */
const MAJOR_ROADS = [
  "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
  "secondary", "secondary_link", "tertiary", "tertiary_link",
];
const ARTERIAL_ROADS = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"];

/** **صبغُ الخريطة بلغة الهوية** — منقولٌ من خريطة الراكب بحرفه: الأرضُ والحدائقُ والطرقُ من رموز `--t2-map-*` على الحاوية
 *  (وفي الليليّ قيمُ «TaxoMap» الداكنة)، **وكلُّ اسمٍ ومَعلمٍ ومبنى وحدٍّ يُخفى**. والألوانُ تُقرأ من الرموز لا تُكتب هنا:
 *  `paint` في mapbox لا يقرأ `var()`. **وبلا رموزٍ لا صبغ** — تبقى القاعدةُ كما هي، ولا لونَ يُخترع. */
function calmLook(instance: mapboxgl.Map, host: HTMLElement, labels: boolean) {
  const css = getComputedStyle(host);
  const token = (name: string) => css.getPropertyValue(name).trim();
  const land = token("--t2-map-land");
  const park = token("--t2-map-park");
  const road = token("--t2-map-road");
  const minor = token("--t2-map-road-minor");
  if (!land || !park || !road || !minor) return;
  const colors = labelColors(host, labels);
  const clutter = /building|^admin|waterway|-case|road-(path|steps|pedestrian|rail|construction)|aeroway|ferry|aerialway|transit|hillshade|contour/;
  for (const layer of instance.getStyle()?.layers ?? []) {
    const { id, type } = layer;
    try {
      // **الأسماءُ بمفتاحها** (SPEC §٧١-د، `lib/map-labels`): مشتعلاً تظهر بألوان الهوية، ومطفأً تُخفى كما كانت
      if (type === "symbol") {
        styleSymbolLayer(instance, id, colors);
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
        instance.setPaintProperty(id, "line-opacity", [
          "interpolate", ["linear"], ["zoom"],
          13, ["match", ["get", "class"], ARTERIAL_ROADS, 1, 0],
          14.5, 1,
        ]);
      }
    } catch {
      // طبقةٌ لا تحمل هذه الخاصّية — تُترك كما هي
    }
  }
}

/** **الانطلاقُ دائرةٌ بالحبر، والوجهةُ مربّعٌ بالجمر** — «لغة الخريطة» في الهوية بحافّةٍ بيضاء (أصنافُها في `screens/t2/ride.css`). */
function t2PinElement(kind: "from" | "to", label: string): HTMLElement {
  const element = document.createElement("div");
  element.setAttribute("aria-label", label);
  element.innerHTML = `<span class="t2-map-pin ${kind}"></span>`;
  return element;
}

/** أيقونةُ زرِّ الموقع بلغة اللوحة لكلِّ طور — **والطورُ يُقرأ من الأيقونة واسمِ الزرّ** كما في الشاشات القائمة. */
const T2_FOLLOW_ICON: Record<FollowMode, string> = {
  follow: "my_location",
  heading: "navigation",
  free: "location_searching",
};

const DEFAULT_CENTER: Coordinates = { lat: 31.9539, lng: 35.9106 };

/** مدّةُ تنعيمِ حركة الزملاء — أقصرُ قليلاً من دورة القراءة فتصل السيارةُ
 *  موضعَها قبيل وصول التالية، كما في خريطة الراكب. */
const NEARBY_TWEEN_MS = 7_000;

interface Tween {
  marker: mapboxgl.Marker;
  element: HTMLElement;
  from: Coordinates;
  to: Coordinates;
  headingFrom: number;
  headingTo: number;
  startedAt: number;
  /** **مصرَّحٌ لا مستنتَج**: الرندرُ الواقعيُّ يُعرض ثابتاً، فلا تُدار علامةٌ
   *  صُرِّح ألّا تدور — ولا يُقاس ذلك من الندرة. */
  rotates: boolean;
}

/** **قيمةُ رمزٍ من §1.1 كما يحسبها المتصفح** — لا نسخةً مكتوبةً بيد.
 *
 * **ولمَ لا `var(--tx)` مباشرةً**: `paint` في mapbox **ليس CSS** — تُمرَّر
 * القيمةُ إلى محرّك الرسم، فـ`var(...)` تصل نصّاً لا يُفهم. فكانت تُنسخ
 * القيمةُ الستّ عشريّةُ بيدٍ في التطبيقين، **ونسخةٌ لا يراها حارسٌ تفترق عن
 * أصلها عند أول تعديلٍ للوحة** — وهو ما وقع للأصفر في كنس 12-أ.
 */
function cssColor(token: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim();
  return value || fallback;
}

function pinElement(color: string, label: string): HTMLElement {
  const element = document.createElement("div");
  element.innerHTML = `
    <svg width="26" height="34" viewBox="0 0 24 32" aria-label="${label}"
         style="filter: drop-shadow(0 3px 4px rgb(0 0 0 / 0.35))">
      <path d="M12 0C5.9 0 1 4.9 1 11c0 8 11 21 11 21s11-13 11-21c0-6.1-4.9-11-11-11z"
            fill="${color}"/>
      <circle cx="12" cy="11" r="4.2" fill="white"/>
    </svg>`;
  return element;
}

export function MapView({
  token,
  center,
  heading,
  pickup,
  dropoff,
  fit = false,
  fitRoute = false,
  fitPadding = 80,
  routePoints = null,
  trimAt = null,
  etaMinutes = null,
  selfSkin = null,
  subscribed = true,
  colleagues = null,
  className,
  t2 = false,
  routeTraveled = false,
  traffic = false,
  onTap = null,
  tapPin = null,
}: Props) {
  const { dark } = useTheme();
  const host = useRef<HTMLDivElement | null>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const self = useRef<mapboxgl.Marker | null>(null);
  const pins = useRef<{ pickup?: mapboxgl.Marker; dropoff?: mapboxgl.Marker }>(
    {},
  );
  const animation = useRef<number | null>(null);
  const cars = useRef<Map<string, Tween>>(new Map());
  const carLoop = useRef<number | null>(null);
  // **التفضيلُ والنقرُ بمرجعين** — يقرؤهما مُعالِجا الخريطة المسجَّلان مرّةً عند البناء، فلا تُجمَّد أوّلُ قيمة
  const trafficRef = useRef(traffic);
  trafficRef.current = traffic;
  const onTapRef = useRef(onTap);
  onTapRef.current = onTap;
  const tapMarker = useRef<mapboxgl.Marker | null>(null);
  // **أسماءُ الأماكن وأماكنُ المالك** (§٧١-د) — بمرجعين كالتفضيل: يقرؤهما معالجُ `style.load` المسجَّلُ مرّةً عند البناء
  const { labels, places } = useMapPlaces();
  const labelsRef = useRef(labels);
  labelsRef.current = labels;
  const placesRef = useRef(places);
  placesRef.current = places;

  // **طورُ المتابعة** (البند ١٧-٢) — و`ref` بجانب الحالة لأن مُعالِج السحب
  // يُسجَّل مرةً واحدةً عند بناء الخريطة، فقراءتُه للحالة تُجمّد أوّلَ قيمة
  const [follow, setFollow] = useState<FollowMode>("follow");
  const followRef = useRef<FollowMode>("follow");
  followRef.current = follow;
  // **متابعةٌ برمجيةٌ لا تُفهم سحباً**: `easeTo` يُطلق `dragstart`? لا — لكنه
  // يُطلق `movestart`، ولو رُبط الخروجُ به لخرجت الكاميرا من المتابعة **بفعل
  // المتابعة نفسِها**. فالحدثُ المرصود `dragstart` و`touchstart` بإصبعين:
  // ما يفعله إنسانٌ بيده لا ما تفعله الكاميرا بنفسها


  useEffect(() => {
    if (!token || !host.current || map.current) return;
    mapboxgl.accessToken = token;
    map.current = new mapboxgl.Map({
      container: host.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      language: MAP_LANGUAGE,
      center: [
        center?.lng ?? DEFAULT_CENTER.lng,
        center?.lat ?? DEFAULT_CENTER.lat,
      ],
      zoom: 14,
      attributionControl: true,
      // **الإيماءاتُ الكاملةُ مكتوبةٌ صراحةً لا موروثةٌ من افتراضِ المكتبة**
      // (البند ١٧-١): دورانٌ وميلٌ ونقرةٌ مزدوجة. وقيمتُها اليومَ هي افتراضُ
      // `mapbox-gl` نفسِه — **وكتابتُها هي المقصود**: ترقيةُ مكتبةٍ تُبدّل
      // افتراضاً تُسقط إيماءةً بلا سطرٍ يتغيّر عندنا ولا اختبارٍ يفشل، وهو
      // الشكلُ الذي لا يُكتشف إلا بشكوى كبتن.
      dragRotate: true,
      pitchWithRotate: true,
      touchZoomRotate: true,
      touchPitch: true,
      doubleClickZoom: true,
      // **وسقفُ الميل ٦٠°** — وهو ما تحتاجه كاميرا الملاحة (البند ١٧-٦)، ولا
      // يُترك للافتراض كي لا يصير الحدُّ قراراً في مكتبةٍ لا نملكها
      maxPitch: 60,
    });
    // **السحبُ بيده يُخرج إلى `free`** — وكاميرا تعيده قسراً بعد ثانيةٍ تجعل
    // النظرَ إلى ما بعد المنعطف مستحيلاً، وهي أشيعُ شكوى في تطبيقات الملاحة
    const release = () => {
      if (followRef.current !== "free") setFollow("free");
    };
    map.current.on("dragstart", release);
    map.current.on("rotatestart", release);
    map.current.on("pitchstart", release);
    // **صبغُ «TaxoMap» مع كلِّ ستايلٍ يُحمَّل** — تبديلُ الستايل يمسح الصبغَ كما يمسح الطبقات
    if (t2) {
      const instance = map.current;
      instance.on("style.load", () => {
        if (host.current) {
          calmLook(instance, host.current, labelsRef.current);
          drawOwnPlaces(instance, host.current, labelsRef.current ? placesRef.current : []);
        }
        // **والزحامُ مع كلِّ ستايلٍ يُحمَّل** — التبديلُ يمسح الطبقات كما يمسح الصبغ
        if (host.current && trafficRef.current) addTraffic(instance, host.current);
      });
      // **النقرُ يُسأل عنه المرجعُ ساعتَه**: من لم يمرّر `onTap` (الخريطةُ الصغيرة والرحلة) لا تقع نقرتُه على شيء
      instance.on("click", (event) => {
        onTapRef.current?.({ lat: event.lngLat.lat, lng: event.lngLat.lng });
      });
      // **في التطوير وحدَه**: الخريطةُ على حاويتها، فيُقرأ ما رُسم (الطبقاتُ وألوانُها) من المتصفّح لا ظنّاً — كخريطة الراكب
      if (import.meta.env.DEV) (host.current as unknown as { __map?: mapboxgl.Map }).__map = instance;
    }

    // **الحاويةُ تتبدّل فتتبدّل معها اللوحة** (2026-08-30): البطاقةُ تتوسّع
    // إلى ملء الشاشة، **و`mapbox-gl` يقيس مقاسَه مرّةً عند البناء** — فبلا
    // هذا المراقب تبقى اللوحةُ ١٧٠ بكسل داخل حاويةٍ ملءَ الشاشة، **والخريطةُ
    // تُرسم في زاويةٍ والباقي فراغ**.
    //
    // **وموضعُه هنا لا في البطاقة**: من يملك اللوحةَ هو من يعيد قياسَها —
    // وأيُّ حاويةٍ تتبدّل غداً تجد الجوابَ مبنيّاً، ولا يُكتب الإصلاحُ مرّتين.
    const watcher = new ResizeObserver(() => map.current?.resize());
    if (host.current) watcher.observe(host.current);

    return () => {
      watcher.disconnect();
      if (animation.current !== null) cancelAnimationFrame(animation.current);
      map.current?.remove();
      map.current = null;
    };
    // مرةً واحدة: تبديلُ الستايل يقع في تأثيرٍ آخر بلا إعادة بناء
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // **طبقةُ الزحام تتبع التفضيل** — وقبل تحميل الستايل يتولّاها `style.load` أعلاه
  // **و«الستايلُ لم يكتمل» ليس «لا زحام»**: `isStyleLoaded` يبقى كاذباً ما دامت مصادرُ تُحمَّل — ولو بعد `style.load` — فطبقةٌ
  // تُطلب حينها كانت تضيع بصمت (قِيس ٢٠٢٦-١٠-٠٦: صفرُ نداءٍ للزحام في إحدى السِمتين). فتُؤجَّل إلى أوّل سكونٍ بعدها
  useEffect(() => {
    const instance = map.current;
    if (!t2 || !instance || !host.current) return;
    const apply = () => {
      if (!host.current) return;
      if (trafficRef.current) addTraffic(instance, host.current);
      else removeTraffic(instance);
    };
    if (instance.isStyleLoaded()) apply();
    else instance.once("idle", apply);
  }, [traffic, t2]);

  // **دبوسُ النقطة المنقورة** — دائرةٌ بالجمر بحافّة الدبوسين، ويُرفع بإغلاق بطاقتها
  useEffect(() => {
    const instance = map.current;
    tapMarker.current?.remove();
    tapMarker.current = null;
    if (!t2 || !instance || !tapPin) return;
    const element = document.createElement("div");
    element.innerHTML = `<span class="t2-map-pin tap"></span>`;
    tapMarker.current = new mapboxgl.Marker({ element }).setLngLat([tapPin.lng, tapPin.lat]).addTo(instance);
  }, [tapPin, t2]);

  useEffect(() => {
    // **ولا يُعاد الستايلُ تحت «TaxoMap»** — قِيس: هذا السطرُ يقع مع الإنشاء، **والتطبيقُ بالفرق يعيد ألوانَ الستايل وأسماءَه
    // فوق الصبغ** بعد أن يقع. والشاشةُ المرسومةُ تُفكّ مع تبديل المظهر (`ByTheme`) فلا تحتاجه (وهو ما تفعله خريطةُ الراكب)
    if (t2) return;
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  // موقعُ الكبتن — يُنعَّم بين البثّتين بدل القفز
  useEffect(() => {
    const instance = map.current;
    if (!instance || !center) return;

    if (!self.current) {
      const element = selfMarkerElement({ skin: selfSkin, subscribed });
      applyMarkerHeading(element, heading, selfSkin?.map_rotates ?? true);
      // **`rotationAlignment: "map"`** — العلامةُ تُعاكس دورانَ الكاميرا فتبقى
      // مقدّمتُها في اتجاه السير الحقيقيّ. وبالافتراض (`viewport`) كانت تدور
      // **مع** الخريطة في طور «الاتجاه»، فتشير إلى غير ما يسير إليه
      self.current = new mapboxgl.Marker({ element, rotationAlignment: "map" })
        .setLngLat([center.lng, center.lat])
        .addTo(instance);
      instance.easeTo({ center: [center.lng, center.lat], duration: 400 });
      return;
    }

    // **الكاميرا تتبع في الطورين لا في `free`** — والتحريكُ برمجيٌّ فلا يُقرأ
    // سحباً (`easeTo` لا يُطلق `dragstart`)
    if (followRef.current !== "free" && !fit) {
      instance.easeTo({
        center: [center.lng, center.lat],
        bearing: followRef.current === "heading" ? (heading ?? 0) : 0,
        duration: 900,
        // **ولا نبضةَ ولا قفزة**: `easeTo` بمدّةٍ أطول قليلاً من دورة البثّ
        // يجعل الحركةَ مستمرةً بدل وثباتٍ كل ثلاث ثوانٍ
        essential: true,
      });
    }

    const marker = self.current;
    const from = marker.getLngLat();
    const startedAt = performance.now();
    if (animation.current !== null) cancelAnimationFrame(animation.current);

    const step = (now: number) => {
      const progress = Math.min((now - startedAt) / TWEEN_MS, 1);
      marker.setLngLat([
        from.lng + (center.lng - from.lng) * progress,
        from.lat + (center.lat - from.lat) * progress,
      ]);
      if (progress < 1) animation.current = requestAnimationFrame(step);
    };
    animation.current = requestAnimationFrame(step);
  }, [center]);

  const cycle = useCallback(() => {
    const instance = map.current;
    setFollow((current) => {
      const next = nextMode(current);
      if (instance && center) {
        instance.easeTo({
          center: [center.lng, center.lat],
          bearing: next === "heading" ? (heading ?? 0) : 0,
          duration: 500,
          essential: true,
        });
      }
      return next;
    });
  }, [center, heading]);

  // **تبديلُ المركبة أو حالِ الاشتراك يُعيد بناءَ العلامة**، ولا يُنتظر بثٌّ
  // جديدٌ للموقع: من فعّل مركبةً في كراجه يعود فيجدها على خريطته في الحال —
  // وعلامةٌ لا تتبدّل إلا بعد ثلاث ثوانٍ تُقرأ «لم يُحفظ الاختيار»
  useEffect(() => {
    const marker = self.current;
    const instance = map.current;
    if (!marker || !instance) return;
    const element = selfMarkerElement({ skin: selfSkin, subscribed });
    applyMarkerHeading(element, heading, selfSkin?.map_rotates ?? true);
    const at = marker.getLngLat();
    marker.remove();
    self.current = new mapboxgl.Marker({ element, rotationAlignment: "map" })
      .setLngLat(at)
      .addTo(instance);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selfSkin?.id ?? null, subscribed]);

  // **الاتجاه** — و`null` يُرسم كالصفر: الشكلُ نفسُه والمقاسُ نفسُه، فلا
  // يُعرَف من الخارج من لا يبثّ اتجاهه (الشكلُ الثالثَ عشر)
  useEffect(() => {
    const element = self.current?.getElement();
    if (element) {
      applyMarkerHeading(element, heading, selfSkin?.map_rotates ?? true);
    }
  }, [heading, center, selfSkin?.map_rotates]);

  // **زملاؤه حوله** — و`null` تعني «الميزةُ غيرُ مفتوحة»: لا علاماتٌ تُرسم
  // ولا رسالةٌ تُقال. **وتُرسم بالسيارة العامّة** لا بمركبةِ أحد: ما يُرى
  // ويندر يصير معرّفاً ينقض تجهيلَ §10
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (colleagues === null) {
      for (const entry of cars.current.values()) entry.marker.remove();
      cars.current.clear();
      return;
    }

    const seen = new Set<string>();
    for (const driver of colleagues) {
      seen.add(driver.ref);
      const point = { lat: driver.lat, lng: driver.lng };
      const existing = cars.current.get(driver.ref);
      if (existing) {
        const at = existing.marker.getLngLat();
        existing.from = { lat: at.lat, lng: at.lng };
        existing.to = point;
        existing.headingFrom = existing.headingTo;
        existing.headingTo = driver.heading ?? existing.headingTo;
        existing.startedAt = performance.now();
        continue;
      }
      // **الدورانُ من صفِّ المركبة لا من الندرة** — والعامّةُ تدور دائماً
      const element = nearbyMarkerElement(driver.skin);
      applyMarkerHeading(element, driver.heading, driver.skin?.rotates ?? true);
      const marker = new mapboxgl.Marker({ element, rotationAlignment: "map" })
        .setLngLat([point.lng, point.lat])
        .addTo(instance);
      cars.current.set(driver.ref, {
        marker,
        element,
        from: point,
        to: point,
        headingFrom: driver.heading ?? 0,
        headingTo: driver.heading ?? 0,
        startedAt: performance.now(),
        rotates: driver.skin?.rotates ?? true,
      });
    }
    for (const [ref, entry] of cars.current) {
      if (seen.has(ref)) continue;
      entry.marker.remove();
      cars.current.delete(ref);
    }

    if (carLoop.current !== null) return;
    const step = (now: number) => {
      for (const entry of cars.current.values()) {
        const progress = Math.min(
          (now - entry.startedAt) / NEARBY_TWEEN_MS,
          1,
        );
        entry.marker.setLngLat([
          entry.from.lng + (entry.to.lng - entry.from.lng) * progress,
          entry.from.lat + (entry.to.lat - entry.from.lat) * progress,
        ]);
        if (entry.rotates) {
          // **الابنُ الداخليُّ لا القشرة** — القشرةُ لـmapbox وإدارتُها تُدير
          // إزاحتَها (`lib/skin-marker.ts::rotatable`)
          headingTarget(entry.element).style.rotate = `${
            entry.headingFrom + (entry.headingTo - entry.headingFrom) * progress
          }deg`;
        }
      }
      carLoop.current = cars.current.size > 0 ? requestAnimationFrame(step) : null;
    };
    carLoop.current = requestAnimationFrame(step);
  }, [colleagues]);

  useEffect(
    () => () => {
      if (carLoop.current !== null) cancelAnimationFrame(carLoop.current);
    },
    [],
  );

  // دبوسا الرحلة
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    for (const [key, point, color, label] of [
      ["pickup", pickup, "var(--ok)", "نقطة الانطلاق"],
      ["dropoff", dropoff, "var(--dng)", "الوجهة"],
    ] as const) {
      const existing = pins.current[key];
      if (!point) {
        existing?.remove();
        pins.current[key] = undefined;
        continue;
      }
      if (existing) existing.setLngLat([point.lng, point.lat]);
      else {
        pins.current[key] = new mapboxgl.Marker(
          t2
            ? { element: t2PinElement(key === "pickup" ? "from" : "to", label), anchor: "center" }
            : {
          element: pinElement(color, label),
          anchor: "bottom",
        })
          .setLngLat([point.lng, point.lat])
          .addTo(instance);
      }
    }
  }, [pickup, dropoff, t2]);

  // **الأسماءُ وأماكنُ المالك حين يتبدّل المفتاحُ أو تصل الأماكن** — وتحميلُ الستايل يعيدها من معالجه
  useEffect(() => {
    const instance = map.current;
    const element = host.current;
    if (!instance || !element || !t2) return;
    const run = () => {
      applyLabels(instance, element, labels);
      drawOwnPlaces(instance, element, labels ? places : []);
    };
    if (instance.isStyleLoaded()) run();
    else instance.once("style.load", run);
  }, [labels, places, t2]);

  // **خطُّ المسار** (البند ٨) — يُضاف حين يصل ويُحدَّث حين يتقدّم الكبتن.
  // و`styleVersion` ليست هنا كما في تطبيق الراكب لأن هذا المكوّن لا يعيد بناء
  // الستايل إلا بتبديل الوضع، فيُعاد الرسمُ من `dark` نفسِها
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    const id = "taxo-route-line";
    const coordinates =
      routePoints && routePoints.length >= 2 ? trimRoute(routePoints, trimAt) : null;

    const draw = () => {
      const source = instance.getSource(id) as mapboxgl.GeoJSONSource | undefined;
      // **ما مضى خافتاً تحت الباقي** (C07): المسارُ كاملاً بلون ما مضى، والباقي بالجمر فوقه — فلا يُرى الخافتُ إلا خلفه
      if (t2) {
        const doneId = `${id}-done`;
        const done = instance.getSource(doneId) as mapboxgl.GeoJSONSource | undefined;
        const whole =
          routeTraveled && routePoints && routePoints.length >= 2
            ? {
                type: "Feature" as const,
                properties: {},
                geometry: { type: "LineString" as const, coordinates: routePoints },
              }
            : { type: "FeatureCollection" as const, features: [] };
        if (done) done.setData(whole);
        else if (host.current) {
          const css = getComputedStyle(host.current);
          const faint =
            css.getPropertyValue("--t2-map-route-done").trim() ||
            css.getPropertyValue("--t2-faint").trim();
          instance.addSource(doneId, { type: "geojson", data: whole });
          instance.addLayer({
            id: doneId,
            type: "line",
            source: doneId,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": faint || cssColor("--mut", "#8b949e"), "line-width": 5 },
          });
        }
      }
      if (!coordinates) {
        source?.setData({ type: "FeatureCollection", features: [] });
        return;
      }
      const data = {
        type: "Feature" as const,
        properties: {},
        geometry: { type: "LineString" as const, coordinates },
      };
      if (source) {
        source.setData(data);
        return;
      }
      instance.addSource(id, { type: "geojson", data });
      // **خطُّ الجمر فوق ظلٍّ خافت** («TaxoMap»): الظلُّ والجمرُ من رموز الحاوية لا من لوحةٍ مكتوبة
      if (t2 && host.current) {
        const css = getComputedStyle(host.current);
        const accent = css.getPropertyValue("--t2-accent").trim();
        const casing = css.getPropertyValue("--t2-map-casing").trim();
        if (accent && casing) {
          instance.addLayer({
            id: `${id}-casing`,
            type: "line",
            source: id,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": casing, "line-width": 10 },
          });
          instance.addLayer({
            id,
            type: "line",
            source: id,
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": accent, "line-width": 5 },
          });
          return;
        }
      }
      instance.addLayer({
        id,
        type: "line",
        source: id,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          // `paint` في mapbox لا يقرأ متغيّرات CSS — فالقيمةُ تُختار من الوضع
          // كما يُختار ستايلُ الخريطة نفسُه
          "line-color": cssColor("--tx", dark ? "#e6edf3" : "#171b20"),
          "line-width": 5,
          "line-opacity": 0.9,
        },
      });
    };

    // **الستايلُ قد لا يكون جاهزاً**: `addLayer` قبل تحميله يرمي، وتبديلُ الوضع
    // يمسح المصادر كلَّها — فيُعاد الرسمُ على `style.load` كذلك
    if (instance.isStyleLoaded()) draw();
    else instance.once("style.load", draw);
  }, [routePoints, trimAt, dark, t2, routeTraveled]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !fit || !pickup || !dropoff) return;
    // **والخطُّ داخلٌ في الإطار حين يُطلب** (`fitRoute`) — نقاطُه `[lng, lat]`، وحسابُ هندسةٍ للعرض لا يُسعَّر منه شيء
    const traced = fitRoute && routePoints && routePoints.length >= 2 ? routePoints : [];
    const lngs = [pickup.lng, dropoff.lng, ...traced.map((point) => point[0])];
    const lats = [pickup.lat, dropoff.lat, ...traced.map((point) => point[1])];
    instance.fitBounds(
      [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
      { padding: fitPadding, duration: 600, maxZoom: 15 },
    );
    // **و`routePoints` في التبعيّات حين يُطلب وحدَه** — فلا يُعاد إطارُ الرئيسية مع كلِّ قصٍّ للمسار وراء الكبتن. **والحشوُ
    // قيمةٌ ثابتةٌ من مناديه** فلا يُتابَع (كائنٌ جديدٌ في كلِّ رسمٍ كان سيعيد الإطارَ مع كلِّ رسم)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fit, pickup, dropoff, fitRoute ? routePoints : null]);

  // **غيابُ توكن iOS يُسمّى باسمه** (SPEC §58) — وغيرُ iOS كما كان حرفاً
  const missing = useMapboxMissing();
  if (!token) {
    return (
      <div
        role={missing ? "alert" : undefined}
        className={cn(
          "flex h-full w-full items-center justify-center bg-stripe font-mono text-10 tracking-map text-muted",
          className,
        )}
      >
        {missing ?? "الخريطة غير مهيأة — راجع عقد Mapbox"}
      </div>
    );
  }

  // **المقاسُ بالطول والعرض لا بالإزاحة** — والسببُ مقيسٌ في المتصفح:
  // `mapbox-gl.css` يعلن `.mapboxgl-map { position: relative }`، وهو ملفٌ
  // يُحمَّل **بعد** أدوات Tailwind وبنفس الأولوية (قِيس: `.absolute` في
  // `index-*.css` والقاعدةُ المقابلة في `MapView-*.css` بعدها) — فيفوز
  // `relative` ويصير `inset-0` كلاماً بلا أثرٍ على المقاس. وارتفاعُ الحاوية
  // **صفر** بينما أبوها 844: خريطةٌ مبنيّةٌ ومقبسٌ مفتوحٌ وشاشةٌ لا خريطةَ فيها.
  // ولا يُدفع الصنفُ إلى العنصر الذي تملكه Mapbox: هي تكتب صنفَها عليه، وما
  // نكتبه نحن قد يُهزم — فالمقاسُ يُطلب من الأب (`h-full w-full`) لا من موضعٍ
  // تملكه هي. وهو نفسُ ما يفعله تطبيقُ الراكب ولوحةُ الإدارة أصلاً.
  return (
    <div className={cn("relative h-full w-full", className)}>
      <div ref={host} className="h-full w-full" />

      {/* **زرُّ التموضع بلغة اللوحة** (C04 · C06): دائرةٌ بأيقونة الطور — **والأطوارُ الثلاثةُ نفسُها** (`cycle`) واسمُ الزرّ
          يقول الطورَ الحاليّ. **وموضعُه من صنف الحاوية** في `screens/t2/ride.css` (البطاقةُ أو الخريطةُ الكاملة) */}
      {t2 ? (
        center ? (
          <button
            type="button"
            onClick={cycle}
            aria-label={labelFor(follow)}
            title={labelFor(follow)}
            className={`t2-maploc ${follow}`}
          >
            <span className="t2-icon" aria-hidden="true">
              {T2_FOLLOW_ICON[follow]}
            </span>
          </button>
        ) : null
      ) : null}

      {/* **الوصولُ المتوقَّع** — يظهر حين يُقاس ويختفي حين لا يُقاس */}
      {!t2 && etaMinutes !== null ? (
        <div className="pointer-events-none absolute start-14 top-64 z-10 rounded-full border border-line bg-surface px-12 py-7 text-12 font-bold text-ink shadow-md">
          {digits(String(etaMinutes))} دقيقة
        </div>
      ) : null}

      {/* **زرُّ التموضع ثلاثيُّ الأطوار** (البند ١٧-٢) — وموضعُه فوق الخريطة
          وتحت بطاقةِ الرحلة، فلا يزاحم قراراً (قاعدةُ «لا شيءَ يعلو قراراً»).
          **ونصُّه يقول الطورَ الحاليَّ لا الفعلَ التالي**: أيقونةٌ وحدَها تجعل
          الكبتنَ يضغط ليعرف ماذا تفعل، وهو يقود */}
      {!t2 && center ? (
        <button
          type="button"
          onClick={cycle}
          aria-label={labelFor(follow)}
          title={labelFor(follow)}
          className={cn(
            "pressable absolute end-14 top-64 z-10 flex size-40 items-center justify-center rounded-full border shadow-md",
            follow === "free"
              ? "border-line bg-surface text-muted"
              : "border-ok bg-surface text-ok",
          )}
        >
          {follow === "heading" ? (
            <Navigation2 size={18} />
          ) : follow === "follow" ? (
            <LocateFixed size={18} />
          ) : (
            <Compass size={18} />
          )}
        </button>
      ) : null}
    </div>
  );
}
