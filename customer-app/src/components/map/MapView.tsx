/** خريطة Mapbox — العنصر الوحيد الذي يعرف واجهة `mapbox-gl` (SPEC القسم 2).
 *
 * ثلاث مسؤوليات:
 *
 * 1. **سيارات الكباتن القريبين** قبل الطلب: أيقونةٌ تدور مع الاتجاه، وحركتُها
 *    **مُنعَّمة بالـ interpolation** كما ينص القسم 10 — البثّ يصل كل خمس
 *    ثوانٍ، فبلا تنعيمٍ تقفز السيارة قفزةً كل خمس ثوانٍ.
 * 2. **موقع الكبتن المُسنَد** أثناء الرحلة (كل ثلاث ثوانٍ، بنفس التنعيم).
 * 3. **دبوسا الانطلاق والوصول**، والخطُّ بينهما.
 *
 * الخط بين النقطتين **مستقيمٌ لا مسار طريق**: هندسة المسار تأتي من Mapbox
 * Directions، ونداؤها من الخلفية حصراً (القسم 2/14) وما تعيده للواجهة مسافةٌ
 * ومدةٌ وسعر لا خطٌّ مرسوم. وخطٌّ نرسمه من عندنا يوهم بمسارٍ لم يقله أحد.
 *
 * وبلا توكن (عقد Mapbox غير مفعّل) تظهر خلفيةٌ محايدة بدل شاشةٍ بيضاء: بقية
 * التطبيق تعمل — الطلبُ يقع بالإحداثيات لا بالخريطة.
 */

import mapboxgl from "mapbox-gl";
import {
  type CSSProperties,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
} from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// **يقع باستيراد الاسم كما يقع بالاستيراد المجرَّد**: الوحدةُ تُقيَّم مرّةً
// عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import type { Coordinates, NearbyDriver, RideDriverSkin } from "@/api/types";
import { trimRoute } from "@/lib/route-line";
import { skinImageUrl, skinSizePx } from "@/lib/skin";
import { useMapboxMissing } from "@/lib/config";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/** **خريطةُ TAXO 2.0 هادئةٌ في المظهرين** (§٦١-د: «بلا معالمَ ولا ازدحامِ شوارع»): قاعدةُ Mapbox الأهدأ لكلِّ مظهر، ثمّ تُصبغ
 *  بلغة «TaxoMap» من رموز الهوية عند كلِّ تحميلٍ للستايل (`calmLook`) — **وفي الليل برموزه الداكنة كخريطة الكبتن**. كان الليلُ
 *  «كما كان» (بنمط Mapbox القديم ودبابيسَ حمراءَ وخضراء) يومَ كانت الشاشاتُ الليليةُ قديمة؛ **وصارت TAXO 2.0 (§٦٢/٣) فتبعتها
 *  الخريطة** (رآه وكيلُ «p3a» ٢٠٢٦-١٠-٠٦). */
const STYLE_LIGHT = "mapbox://styles/mapbox/light-v11";

/** الطرقُ الكبرى بيضاء والصغرى أخفتُ منها — كما ترسمهما «TaxoMap». */
const MAJOR_ROADS = [
  "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
  "secondary", "secondary_link", "tertiary", "tertiary_link",
];
/** ما يبقى من الطرق حين تبتعد الكاميرا (تحت ١٣) — الشرايينُ وحدَها. */
const ARTERIAL_ROADS = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"];

/** **صبغُ الخريطة بلغة الهوية** — الأرضُ والحدائقُ والطرقُ من رموز `--t2-map-*` على الحاوية (`t2 t2-map`)، **وكلُّ اسمٍ
 *  ومَعلمٍ ومبنى وحدٍّ يُخفى**. والألوانُ تُقرأ من الرموز لا تُكتب هنا: `paint` في mapbox لا يقرأ `var()`. **وبلا رموزٍ لا صبغ**
 *  — تبقى القاعدةُ الهادئةُ كما هي، ولا لونَ يُخترع. */
function calmLook(instance: mapboxgl.Map, host: HTMLElement) {
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
      if (type === "symbol" || clutter.test(id)) {
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
        // **وتهدأ الشوارعُ حين تبتعد الكاميرا** (R06 بالطريق كلِّه، كما رُسم: طرقٌ كبرى وحدَها): تحت ١٣ لا يُرسم إلا
        // `ARTERIAL_ROADS`، والباقي يظهر حتى ١٤٫٥ — والقريبُ (R05 على ١٥) كما هو
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

/** **سيارةُ الهوية** (TaxoMap): جسمٌ بالحبر بحافّةٍ بيضاء، وزجاجٌ أماميٌّ بالجمر وخلفيٌّ أخفت — 16×30. */
function t2CarMarkup(): string {
  return `<span class="t2-map-car"><i class="t2-map-car-front"></i><i class="t2-map-car-back"></i></span>`;
}
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

// زمن تنعيم الحركة: أقصر قليلاً من دورة البثّ، فتصل السيارة موضعها الجديد
// قبيل وصول التالي بدل أن تتقطع الحركة أو تتأخر عنه
const NEARBY_TWEEN_MS = 4_500;
const DRIVER_TWEEN_MS = 2_800;

/** حشوُ الإطار بالبكسل — والافتراضيُّ (`FIT_PADDING`) لورقةٍ قائمةٍ فوق شريط التبويب. */
export interface FitPadding {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

const FIT_PADDING: FitPadding = { top: 90, bottom: 320, left: 60, right: 60 };

export interface MapHandle {
  /** يعيد التوسيط على نقطة (عند الضغط على «موقعي»). */
  flyTo: (point: Coordinates, zoom?: number) => void;
  /** يضبط الإطار ليضم النقطتين معاً — و`padding` لمن يعرف ما يغطّي الخريطةَ (ورقةُ «R06» بارتفاعها). */
  fitBounds: (a: Coordinates, b: Coordinates, padding?: Partial<FitPadding>) => void;
  center: () => Coordinates | null;
}

interface MapViewProps {
  token: string | null;
  center: Coordinates;
  zoom?: number;
  drivers?: NearbyDriver[];
  pickup?: Coordinates | null;
  dropoff?: Coordinates | null;
  driverLocation?: { lat: number; lng: number; heading: number | null } | null;
  /** **مركبةُ الكبتن المُسنَد** — تصل بعد القبول وحدَه (`RideDriverSkin`).
   *
   *  **ولا تمسّ سياراتِ الكباتن القريبين**: تلك تبقى كما هي قبل القبول، فلا
   *  حقلَ ولا شكلَ يُستدلّ منه على مركبة أحد على الخريطة الحرّة (§10).
   *  و`null`/غيابٌ يرسم السيارةَ العامّة **بلا أيِّ فرقٍ مرئيّ**. */
  driverSkin?: RideDriverSkin | null;
  interactive?: boolean;
  /** خطُّ الوصل بين النقطتين. **يُطفأ في شريط التفاصيل** (القرار 38): هناك
   *  المسارُ الفعليُّ مسجَّلٌ في `ride_route_points` ولا منفذَ يقرؤه، فخطٌّ
   *  مستقيمٌ من عندنا يوهم بمسارٍ لم يقله أحد. */
  tripLine?: boolean;
  /** **مسارُ الرحلة على الطرق كما قاله Mapbox** — `[[lng, lat], …]` (البند ٨).
   *
   *  حين يصل يُرسم **متّصلاً**، وحين يغيب يبقى الخطُّ المستقيمُ **متقطّعاً**:
   *  والتقطيعُ هو ما يفرّق بينهما بلا نصّ — مستقيمٌ يقول «بينكما»، ومتّصلٌ
   *  يقول «هذا الطريق». وهو تفريقُ القرار 38 نفسِه: يمنع خطاً نرسمه نحن، لا
   *  مساراً قاله Mapbox. */
  routePoints?: number[][] | null;
  /** موضعُ الكبتن الآن — ما قبله من المسار يُقصّ (تتبّعُ التقدّم بعد البدء). */
  trimAt?: Coordinates | null;
  /** نبضةٌ حول موقع المستخدم — لونُها `--brand` فتتبع الوضعَ والسِمة. */
  showMyLocation?: Coordinates | null;
  /** نبضةٌ حول دبوس الانطلاق **أثناء البحث عن كبتن** — تتوقف عند القبول. */
  searching?: boolean;
  onMoveEnd?: (center: Coordinates) => void;
  className?: string;
  /** **ما يغطّي أسفلَ الخريطة بالبكسل** — ورقةُ «R06» الملتصقة. **شعارُ Mapbox ونسبتُه شرطُ الرخصة** فيرتفعان فوقها
   *  ولا يُرسمان عليها. وبلا قيمةٍ لا يُكتب على الحاوية شيء. */
  controlsInset?: number;
}

interface TweenedMarker {
  marker: mapboxgl.Marker;
  from: Coordinates;
  to: Coordinates;
  /** الاتجاهُ يُنعَّم كالموضع — **وإلا دارت الأيقونةُ قفزةً** مع كل بثّ. */
  headingFrom: number;
  headingTo: number;
  startedAt: number;
  duration: number;
  element: HTMLElement;
  /** **أتدور العلامةُ مع الاتجاه؟** — العلويّةُ المرسومةُ تدور، والرندرُ
   *  الواقعيُّ ثابت (`map_rotates` في الصفّ، لا استنتاجاً من الندرة). */
  rotates: boolean;
}

/** **سيارةٌ من فوق، بألوان النظام** (قرارُ المالك 2026-08-22).
 *
 * **العلّة**: كان المرسومُ سهماً مثلثاً بـ`#facc15` — قيمةٌ نجت من كنس 12-أ،
 * حين حُذف الأصفرُ من اللوحة (§1.1 لا لونَ علامةٍ فيها). فبقيت في ملفٍّ واحدٍ
 * قيمةٌ لا يعرفها أحد، **ولا حارسَ يراها**: صنفٌ مكتوبٌ بيد لا يمرّ بالسلّم.
 *
 * **واللونُ `--tx`** لأنه **ينقلب مع السمة**: داكنٌ على خريطةٍ فاتحة، فاتحٌ على
 * داكنة — فلا يذوب في البلاط في إحداهما. ولون ثابتٌ مهما كان جميلاً يختفي في
 * سمةٍ واحدةٍ من اثنتين.
 *
 * **وبلا اتجاهٍ تُرسم كما تُرسم بالاتجاه** — نفسُ الشكل عند صفر، **ولا شكلَ
 * ثانٍ**: شكلٌ يخصّ من لا اتجاهَ له يجعل **الغيابَ مرئياً**، فيصير علامةً على
 * كبتنٍ لا يبثّ اتجاهه. وهو **مبدأُ عطب الإعفاء نفسُه** (`test_photo_leak.py`):
 * **التمييزُ المرئيُّ وشايةٌ حتى حين يبدو تحسيناً.**
 */
function carElement(t2 = false): HTMLElement {
  const element = document.createElement("div");
  element.className = "taxo-car";
  // **القياسُ لا التقدير**: 30×30 مقيسٌ على عرض 390 بكسل — التفصيل في التقرير.
  // **وفي نهار TAXO 2.0 سيارةُ الهوية** — والغلافُ والدورانُ هما هما
  element.innerHTML = t2 ? t2CarMarkup() : `
    <svg width="30" height="30" viewBox="0 0 24 24" aria-hidden="true"
         style="filter: drop-shadow(0 1px 3px rgb(0 0 0 / 0.45))">
      <g fill="var(--tx)" stroke="var(--inv)" stroke-width="0.7">
        <rect x="4.2" y="1.6" width="2.1" height="4.4" rx="0.9"/>
        <rect x="17.7" y="1.6" width="2.1" height="4.4" rx="0.9"/>
        <rect x="4.2" y="18" width="2.1" height="4.4" rx="0.9"/>
        <rect x="17.7" y="18" width="2.1" height="4.4" rx="0.9"/>
        <path d="M12 1.2c-2.4 0-4.1 1.1-4.6 3.2l-.7 3.3c-.3 1.5-.4 3-.4 4.3
                 0 2.5.2 5 .6 7.4.2 1.4 2.1 2.4 5.1 2.4s4.9-1 5.1-2.4c.4-2.4
                 .6-4.9.6-7.4 0-1.3-.1-2.8-.4-4.3l-.7-3.3C16.1 2.3 14.4 1.2 12 1.2Z"/>
      </g>
      <path d="M8.6 6.6c.5-1.1 1.7-1.7 3.4-1.7s2.9.6 3.4 1.7l.5 1.6c-1.2-.5-2.5-.7-3.9-.7
               s-2.7.2-3.9.7Z" fill="var(--inv)" opacity="0.85"/>
    </svg>`;
  // **الدورانُ يعيش على ابنٍ داخليّ** (وقع مقيساً في تطبيق الكبتن 2026-08-27):
  // mapbox تكتب `transform: translate(...)` على العنصر الذي تُسلَّمه، وترتيبُ
  // CSS هو `translate → rotate → scale → transform` — أي أن `transform` يُطبَّق
  // أوّلاً **ثم يُدار ناتجُه**. فدورانُ الرأس يُدير إزاحةَ mapbox نفسَها
  // فتهبط السيارةُ في غير موضعها. **وهي قاعدةُ `pulseElement` أدناه بعينها.**
  const inner = document.createElement("div");
  inner.className = "taxo-car-rot";
  // **مقاسُ المحتوى**: mapbox تزيح بـ`translate(-50%,-50%)` من مقاس العنصر،
  // فغلافٌ يمتدّ إلى عرض الخريطة يقذف العلامةَ بنصف ذلك العرض
  inner.style.display = "block";
  inner.style.width = "max-content";
  inner.replaceChildren(...element.childNodes);
  element.appendChild(inner);
  element.style.width = "max-content";
  element.style.willChange = "transform";
  return element;
}

/** **الطبقةُ التي تدور** — ولا تُدار القشرةُ التي تملكها mapbox. */
function headingLayer(element: HTMLElement): HTMLElement {
  return element.querySelector<HTMLElement>(".taxo-car-rot") ?? element;
}

/** علامةُ الكبتن المُسنَد — **السيارةُ العامّة، أو مركبتُه إن كانت له**.
 *
 * **والسيارةُ العامّةُ تُرسم أولاً دائماً**، والرسمةُ تحلّ محلَّها **عند
 * وصولها لا قبله**: علامةٌ فارغةٌ تنتظر صورةً على شبكةٍ بطيئة **تُرى فرقاً
 * بين كبتنٍ وكبتن** — وصورةٌ لا تصل أبداً (٤٠٤، عقدٌ محذوف، شبكةٌ ساقطة)
 * تترك الراكبَ بلا سيارةٍ على الخريطة. **فالسقوطُ إلى العامّة لا يُرى**،
 * وهو الشكلُ الثالثَ عشر مطبَّقاً: الغيابُ لا يُميَّز عن الحضور.
 */
function driverElement(skin: RideDriverSkin | null | undefined, t2 = false): HTMLElement {
  const element = carElement(t2);
  if (!skin) return element;

  const generic = element.querySelector(t2 ? ".t2-map-car" : "svg");
  const size = skinSizePx(skin);
  const image = document.createElement("img");
  // **وصفٌ فارغٌ بقصد**: اسمُ المركبة مكتوبٌ في بطاقة الكبتن، وقارئُ الشاشة
  // لا يحتاج أن يسمعه مرةً ثانيةً من علامةٍ على خريطة
  image.alt = "";
  image.width = size;
  image.height = size;
  image.style.display = "none";
  image.style.objectFit = "contain";
  image.style.filter = "drop-shadow(0 1px 3px rgb(0 0 0 / 0.45))";
  image.addEventListener(
    "load",
    () => {
      image.style.display = "block";
      if (generic instanceof SVGElement || generic instanceof HTMLElement) generic.style.display = "none";
    },
    { once: true },
  );
  image.src = skinImageUrl(skin.image_url);
  headingLayer(element).appendChild(image);
  return element;
}

/** حلقةُ نبضٍ — `taxo-pulse` في `index.css` (CSS خالص، §8.2). */
function pulseElement(label: string): HTMLElement {
  const element = document.createElement("div");
  element.className = "taxo-pulse";
  element.setAttribute("aria-label", label);
  // **الطبقةُ الداخلية هي ما يُنسَّق**: mapbox يضيف `mapboxgl-marker` (وفيها
  // `position:absolute`) إلى العنصر الذي نسلّمه، فالكتابةُ على `className`
  // تُسقط العلامةَ خارج الخريطة (`CLAUDE.md`)
  const core = document.createElement("div");
  core.className = "taxo-pulse-core";
  element.appendChild(core);
  return element;
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

/** **«أنت هنا» بلغة الهوية** — نقطةُ الجمر بحافّةٍ بيضاء في هالتها (TaxoMap)، **ساكنةٌ كما رُسمت**. */
function t2MeElement(label: string): HTMLElement {
  const element = document.createElement("div");
  element.setAttribute("aria-label", label);
  element.innerHTML = `<span class="t2-map-me"><i class="t2-map-me-dot"></i></span>`;
  return element;
}

/** **رادارُ البحث** (R07): ثلاثُ حلقاتٍ بالجمر تتّسع من الانطلاق بفارق ٠٫٩ ثانية (`txring` في اللوحة)، **ونقطةُ الجمر بهالتها في
 *  مركزها**. ومع «تقليل الحركة» تقف الحلقاتُ على ثلاثة أطوارٍ كما رُسمت (`t2.css`). */
function t2RadarElement(label: string): HTMLElement {
  const element = document.createElement("div");
  element.setAttribute("aria-label", label);
  element.innerHTML = `<span class="t2-map-radar"><i></i><i></i><i></i></span><span class="t2-map-me"><i class="t2-map-me-dot"></i></span>`;
  element.style.width = "max-content";
  return element;
}

/** **الانطلاقُ دائرةٌ بالحبر، والوجهةُ مربّعٌ بالجمر** — «لغة الخريطة» في الهوية، بحافّةٍ بيضاء. */
function t2PinElement(kind: "from" | "to", label: string): HTMLElement {
  const element = document.createElement("div");
  element.setAttribute("aria-label", label);
  element.innerHTML = `<span class="t2-map-pin ${kind}"></span>`;
  return element;
}

function pinElement(color: string, label: string): HTMLElement {
  const element = document.createElement("div");
  element.innerHTML = `
    <svg width="30" height="40" viewBox="0 0 24 32" aria-label="${label}"
         style="filter: drop-shadow(0 3px 4px rgb(0 0 0 / 0.35))">
      <path d="M12 0C5.9 0 1 4.9 1 11c0 8 11 21 11 21s11-13 11-21c0-6.1-4.9-11-11-11z"
            fill="${color}"/>
      <circle cx="12" cy="11" r="4.2" fill="white"/>
    </svg>`;
  return element;
}

function lerp(from: number, to: number, ratio: number) {
  return from + (to - from) * ratio;
}

/** تنعيمُ زاويةٍ **بأقصر قوس**: من 350° إلى 10° عشرون درجةً لا ثلاثُمئةٍ وأربعون
 *  — وبغيره تلفّ السيارةُ حول نفسها كاملةً عند كل عبورٍ للشمال. */
function lerpAngle(from: number, to: number, ratio: number) {
  const delta = ((to - from + 540) % 360) - 180;
  return from + delta * ratio;
}

export const MapView = forwardRef<MapHandle, MapViewProps>(function MapView(
  {
    token,
    center,
    zoom = 14,
    drivers,
    pickup,
    dropoff,
    tripLine = true,
    routePoints = null,
    trimAt = null,
    showMyLocation = null,
    searching = false,
    driverLocation,
    driverSkin = null,
    interactive = true,
    onMoveEnd,
    className,
    controlsInset = 0,
  },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  // يُرفع كلما صار الستايل جاهزاً — أولَ تحميلٍ وبعد كل تبديلٍ ليلي/نهاري.
  // `setStyle` يمسح الطبقات والمصادر المضافة يدوياً، فخط الرحلة يُعاد رسمه
  // على هذه الإشارة؛ والعلامات (`Marker`) تعيش خارج الستايل فتبقى.
  const [styleVersion, setStyleVersion] = useState(0);
  const carMarkers = useRef(new Map<string, TweenedMarker>());
  const driverMarker = useRef<TweenedMarker | null>(null);
  /** معرّفُ المركبة المرسومة الآن — تبدُّلُه يعيد بناءَ العلامة. */
  const drawnSkin = useRef<string | null>(null);
  const pickupMarker = useRef<mapboxgl.Marker | null>(null);
  const myLocationMarker = useRef<mapboxgl.Marker | null>(null);
  const searchPulse = useRef<mapboxgl.Marker | null>(null);
  const dropoffMarker = useRef<mapboxgl.Marker | null>(null);
  const frame = useRef<number | null>(null);
  const moveEnd = useRef(onMoveEnd);
  const { dark } = useTheme();
  // **لغةُ TAXO 2.0 في المظهرين** — العلاماتُ والدبابيسُ والخطّ؛ والمظهرُ يُقرأ في معالجِ `style.load` المسجَّل مرّةً واحدة
  const darkRef = useRef(dark);
  darkRef.current = dark;
  const t2 = true;

  moveEnd.current = onMoveEnd;

  // ------------------------------------------------------------ الإنشاء
  useEffect(() => {
    if (!token || !container.current || map.current) return;

    mapboxgl.accessToken = token;
    const instance = new mapboxgl.Map({
      container: container.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      language: MAP_LANGUAGE,
      center: [center.lng, center.lat],
      zoom,
      attributionControl: true,
      interactive,
      // **الإيماءاتُ الكاملةُ صراحةً** (البند ١٧-١) — انظر تعليقَ تطبيق الكبتن:
      // قيمتُها افتراضُ المكتبة اليوم، وكتابتُها تمنع ترقيةً تُسقط إيماءةً بصمت.
      // **و`interactive: false` يعلوها كلَّها** فتبقى الخرائطُ الساكنة ساكنة
      dragRotate: true,
      pitchWithRotate: true,
      touchZoomRotate: true,
      touchPitch: true,
      doubleClickZoom: true,
      maxPitch: 60,
      // لغةُ الخريطة عربية حيث تتوفر التسميات
      locale: {},
    });

    instance.on("style.load", () => {
      instance.resize();
      // **الصبغُ قبل الإشارة** — فطبقاتُ الرحلة تُضاف فوق خريطةٍ مصبوغة
      if (container.current) calmLook(instance, container.current);
      setStyleVersion((version) => version + 1);
    });
    instance.on("moveend", () => {
      const point = instance.getCenter();
      moveEnd.current?.({ lat: point.lat, lng: point.lng });
    });

    map.current = instance;
    // **في التطوير وحدَه**: اللوحةُ على حاويتها، فيُقرأ ما رُسم (الطبقاتُ وألوانُها) من المتصفّح لا ظنّاً
    if (import.meta.env.DEV && container.current) {
      (container.current as HTMLDivElement & { __map?: mapboxgl.Map }).__map = instance;
    }

    // **الحاويةُ تتبدّل فتتبدّل معها اللوحة** (2026-08-30): البطاقةُ تتوسّع
    // إلى ملء الشاشة، **و`mapbox-gl` يقيس مقاسَه مرّةً عند البناء** — فبلا
    // هذا المراقب تبقى اللوحةُ ١٧٠ بكسل داخل حاويةٍ ملءَ الشاشة.
    //
    // **وموضعُه هنا لا في البطاقة**: من يملك اللوحةَ هو من يعيد قياسَها.
    const watcher = new ResizeObserver(() => instance.resize());
    if (container.current) watcher.observe(container.current);

    return () => {
      watcher.disconnect();
      instance.remove();
      map.current = null;
      carMarkers.current.clear();
      driverMarker.current = null;
      pickupMarker.current = null;
      dropoffMarker.current = null;
    };
    // مرةً واحدة: التوكن لا يتبدل داخل الجلسة، وبقية التغييرات تُطبَّق أدناه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // تبديل الستايل مع الوضع الليلي
  //
  // **لا عند البناء**: الستايلُ مضبوطٌ في المُنشئ، **ونداءٌ ثانٍ بالعنوان نفسِه يُطبَّق فرقاً** — يقارن الستايلَ الحيَّ بنسخةٍ
  // نظيفةٍ فيمحو صبغَ `calmLook` **بلا `style.load` يعيده** (قِيس ٢٠٢٦-١٠-٠٤: خلفيةُ Mapbox الأصلية وأسماءٌ ظاهرة بعد الصبغ).
  // **وعند التبديل تحميلٌ كاملٌ لا فرق** (`diff: false`) — فيقع `style.load` ويُصبغ النهارُ من جديد.
  const styleApplied = useRef(false);
  useEffect(() => {
    if (!styleApplied.current) {
      styleApplied.current = true;
      return;
    }
    // أنواعُ mapbox تُلزم حقلَي الخطّ المحلّي في الخيارات — والمكتبةُ تقبل `diff` وحدَه
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT, {
      diff: false,
    } as Parameters<mapboxgl.Map["setStyle"]>[1]);
  }, [dark]);

  // **والعلاماتُ تُبنى من جديدٍ مع المظهر**: سيارةُ الليل ونبضتُه بألوان §1.1، وسيارةُ النهار ودبابيسُه بلغة الهوية — والعلامةُ
  // لا تُعاد صياغتُها في مكانها. فتُرفع كلُّها هنا، **وكلُّ أثرٍ أدناه يعيد رسمَ ما يخصّه** (المظهرُ في تبعيّاته)
  const firstTheme = useRef(true);
  useEffect(() => {
    if (firstTheme.current) {
      firstTheme.current = false;
      return;
    }
    for (const entry of carMarkers.current.values()) entry.marker.remove();
    carMarkers.current.clear();
    driverMarker.current?.marker.remove();
    driverMarker.current = null;
    drawnSkin.current = null;
    for (const slot of [pickupMarker, dropoffMarker, myLocationMarker, searchPulse]) {
      slot.current?.remove();
      slot.current = null;
    }
  }, [dark]);

  // ------------------------------------------------- حلقة التنعيم الواحدة
  //
  // **تعمل عند الحاجة وحدها ثم تتوقف.** كانت `requestAnimationFrame` تُجدَّد بلا
  // شرطٍ ما دامت الشاشةُ مفتوحة — ستون إطاراً في الثانية على خريطةٍ ساكنةٍ لا
  // تتحرك فيها سيارة. وتطبيقُ الكبتن يبقى مفتوحاً ساعاتٍ في السيارة، فهذه
  // الحلقةُ وحدها كانت تستهلك بطاريتَه بلا أن ترسم شيئاً.
  //
  // فالآن: تبدأ حين يبدأ انتقالٌ، وتتوقف حين ينتهي آخرُه.
  const ensureLoop = useCallback(() => {
    if (frame.current !== null) return;

    const step = () => {
      const now = performance.now();
      let moving = false;

      const advance = (entry: TweenedMarker) => {
        const ratio = Math.min(1, (now - entry.startedAt) / entry.duration);
        if (ratio < 1) moving = true;
        // تسارعٌ ثم تباطؤ: حركةُ سيارةٍ لا انتقالُ نقطة
        const eased = ratio < 0.5 ? 2 * ratio * ratio : 1 - (-2 * ratio + 2) ** 2 / 2;
        entry.marker.setLngLat([
          lerp(entry.from.lng, entry.to.lng, eased),
          lerp(entry.from.lat, entry.to.lat, eased),
        ]);
        // **ما لا يدور لا يُكتب له تحويل**: كتابةُ صفرِ درجةٍ على رندرٍ
        // واقعيٍّ لا تضرّ اليوم، لكنّها تجعل «لا يدور» شرطاً في مكانٍ واحدٍ
        // ينساه الموضعُ الثاني — والشرطُ هنا حيث تُكتب الزاوية
        if (entry.rotates) {
          headingLayer(entry.element).style.rotate = `${lerpAngle(
            entry.headingFrom,
            entry.headingTo,
            eased,
          )}deg`;
        }
      };

      for (const entry of carMarkers.current.values()) advance(entry);
      if (driverMarker.current) advance(driverMarker.current);

      frame.current = moving ? requestAnimationFrame(step) : null;
    };

    frame.current = requestAnimationFrame(step);
  }, []);

  useEffect(
    () => () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    },
    [],
  );

  // -------------------------------------------------- سيارات الكباتن القريبين
  useEffect(() => {
    const instance = map.current;
    if (!instance || drivers === undefined) return;

    const seen = new Set<string>();
    for (const driver of drivers) {
      seen.add(driver.ref);
      const point = { lat: driver.lat, lng: driver.lng };
      const existing = carMarkers.current.get(driver.ref);

      if (existing) {
        // الانتقال يبدأ من **الموضع المعروض الآن** لا من الهدف السابق: بغيره
        // تقفز سيارةٌ وصلت متأخرةً إلى الوراء ثم تعود
        const shown = existing.marker.getLngLat();
        existing.from = { lat: shown.lat, lng: shown.lng };
        existing.to = point;
        existing.startedAt = performance.now();
        existing.headingFrom = existing.headingTo;
        existing.headingTo = driver.heading ?? existing.headingTo;
        ensureLoop();
        continue;
      }

      // **مركبتُه المنشورةُ تُرسم هنا كما تُرسم بعد القبول** (قرارُ المالك
      // 2026-08-22): **البانِي واحدٌ للموضعين** — فلا يفترق شكلُ سيارةٍ قبل
      // القبول عن شكلها بعده، ولا يُبنى سقوطٌ إلى العامّة مرتين.
      //
      // **والنادرةُ لا تصل هنا أصلاً**: الخلفيةُ ترسل البديلَ المنشورَ لمن
      // لا مركبةَ ظاهرةً له، فكلُّ من على الخريطة يحمل شيئاً — والغيابُ لا
      // يُميَّز عن الحضور.
      const element = driverElement(driver.skin, t2);
      // **والدورانُ من الصفّ لا يُخمَّن** — `map_rotates`: العلويّةُ
      // المرسومةُ تدور، والرندرُ الواقعيُّ ثابت. وهو نفسُ سطر العلامة
      // المُسنَدة، فلا قاعدتان لشيءٍ واحد.
      const rotates = driver.skin ? driver.skin.rotates : true;
      // **على الطبقة الداخلية لا القشرة** (`headingLayer`) — وكانت تُكتب على القشرة التي تملكها mapbox فتدور معها
      // إزاحتُها: سيارةٌ باتجاه ٦٠° رُسمت على بُعد ٣٣٠ بكسلاً من موضعها (قِيس ٢٠٢٦-١٠-٠٤، والحلقةُ وحدَها صُحّحت في ٠٨-٢٨)
      if (rotates) headingLayer(element).style.rotate = `${driver.heading ?? 0}deg`;
      const marker = new mapboxgl.Marker({
        element,
        rotationAlignment: rotates ? "map" : "viewport",
      })
        .setLngLat([point.lng, point.lat])
        .addTo(instance);
      carMarkers.current.set(driver.ref, {
        marker,
        element,
        from: point,
        to: point,
        headingFrom: driver.heading ?? 0,
        headingTo: driver.heading ?? 0,
        startedAt: performance.now(),
        duration: NEARBY_TWEEN_MS,
        rotates,
      });
    }

    for (const [ref, entry] of carMarkers.current) {
      if (!seen.has(ref)) {
        entry.marker.remove();
        carMarkers.current.delete(ref);
      }
    }
  }, [drivers, ensureLoop, t2]);

  // ------------------------------------------------- موقع الكبتن المُسنَد
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (!driverLocation) {
      driverMarker.current?.marker.remove();
      driverMarker.current = null;
      drawnSkin.current = null;
      return;
    }

    // **تبدُّلُ المركبة يعيد بناءَ العلامة لا يعدّلها**: الرسمةُ والدوران
    // وطريقةُ المحاذاة تُقرَّر لحظةَ الإنشاء، **فمركبةٌ تصل بعد أن رُسمت
    // السيارةُ العامّة تبقى غيرَ ظاهرةٍ إلى نهاية الرحلة** — وهي الحالُ
    // العاديّة: الموقعُ يصل قبل تفاصيل الرحلة أو معها
    const skinId = driverSkin?.skin_id ?? null;
    if (driverMarker.current && drawnSkin.current !== skinId) {
      driverMarker.current.marker.remove();
      driverMarker.current = null;
    }
    drawnSkin.current = skinId;

    const point = { lat: driverLocation.lat, lng: driverLocation.lng };
    if (driverMarker.current) {
      const shown = driverMarker.current.marker.getLngLat();
      driverMarker.current.from = { lat: shown.lat, lng: shown.lng };
      driverMarker.current.to = point;
      driverMarker.current.startedAt = performance.now();
      driverMarker.current.headingFrom = driverMarker.current.headingTo;
      driverMarker.current.headingTo =
        driverLocation.heading ?? driverMarker.current.headingTo;
      ensureLoop();
      return;
    }

    // **الدورانُ يُقرأ من الصفّ لا يُخمَّن**: `map_rotates` يقول أعلويّةٌ
    // مرسومةٌ هي أم رندرٌ واقعيّ. والعلويّةُ تدور مع الخريطة
    // (`rotationAlignment: "map"`)، والواقعيُّ **يبقى قائماً أمام القارئ**
    // (`"viewport"`) — فلا يستلقي على جنبه حين يلفّ الراكبُ الخريطة
    const rotates = driverSkin ? driverSkin.rotates : true;
    const element = driverElement(driverSkin, t2);
    // على الطبقة الداخلية كالعلامات القريبة أعلاه — فالقشرةُ لـmapbox وحدَها
    if (rotates) headingLayer(element).style.rotate = `${driverLocation.heading ?? 0}deg`;
    driverMarker.current = {
      marker: new mapboxgl.Marker({
        element,
        rotationAlignment: rotates ? "map" : "viewport",
      })
        .setLngLat([point.lng, point.lat])
        .addTo(instance),
      element,
      from: point,
      to: point,
      headingFrom: driverLocation.heading ?? 0,
      headingTo: driverLocation.heading ?? 0,
      startedAt: performance.now(),
      duration: DRIVER_TWEEN_MS,
      rotates,
    };
  }, [driverLocation, driverSkin, ensureLoop, t2]);

  // ------------------------------------------------ نبضةُ الموقع والبحث
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (!showMyLocation) {
      myLocationMarker.current?.remove();
      myLocationMarker.current = null;
      return;
    }
    if (!myLocationMarker.current) {
      myLocationMarker.current = new mapboxgl.Marker({
        element: t2 ? t2MeElement("موقعي") : pulseElement("موقعي"),
      })
        .setLngLat([showMyLocation.lng, showMyLocation.lat])
        .addTo(instance);
      return;
    }
    myLocationMarker.current.setLngLat([showMyLocation.lng, showMyLocation.lat]);
  }, [showMyLocation, t2]);

  // نبضةٌ حول دبوس الانطلاق ما دام البحثُ جارياً — **وتتوقف عند القبول**:
  // نبضٌ يبقى بعد أن يُسنَد الكبتن يقول «ما زلنا نبحث» وقد وُجد
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (!searching || !pickup) {
      searchPulse.current?.remove();
      searchPulse.current = null;
      return;
    }
    if (!searchPulse.current) {
      searchPulse.current = new mapboxgl.Marker({
        // **ونهارُ TAXO 2.0 رادارُ اللوحة** (R07): ثلاثُ حلقاتٍ واسعةٍ بالجمر ونقطةُ الانطلاق في مركزها — والليلُ نبضتُه كما كانت
        element: t2 ? t2RadarElement("جارٍ البحث عن كبتن") : pulseElement("جارٍ البحث عن كبتن"),
      })
        .setLngLat([pickup.lng, pickup.lat])
        .addTo(instance);
      return;
    }
    searchPulse.current.setLngLat([pickup.lng, pickup.lat]);
  }, [searching, pickup, t2]);

  // ----------------------------------------------------- الدبابيس والخط
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    const place = (
      slot: React.MutableRefObject<mapboxgl.Marker | null>,
      point: Coordinates | null | undefined,
      color: string,
      label: string,
      kind: "from" | "to",
    ) => {
      if (!point) {
        slot.current?.remove();
        slot.current = null;
        return;
      }
      if (slot.current) {
        slot.current.setLngLat([point.lng, point.lat]);
        return;
      }
      // **في نهار TAXO 2.0 دائرةٌ ومربّعٌ يقعان على النقطة نفسِها** (مركزُهما لا طرفُ دبوس)، **والليلُ دبوسُه كما كان**
      slot.current = new mapboxgl.Marker(
        t2
          ? { element: t2PinElement(kind, label), anchor: "center" }
          : { element: pinElement(color, label), anchor: "bottom" },
      )
        .setLngLat([point.lng, point.lat])
        .addTo(instance);
    };

    // **وفي بحث TAXO 2.0 يقف الرادارُ وحدَه على الانطلاق** (R07) — نقطتُه في مركزه، فدائرةُ الحبر تحتها نقطتان لشيءٍ واحد
    place(pickupMarker, t2 && searching ? null : pickup, "var(--ok)", "نقطة الانطلاق", "from");
    place(dropoffMarker, dropoff, "var(--dng)", "الوجهة", "to");
  }, [pickup, dropoff, t2, searching]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || styleVersion === 0) return;

    const id = "taxo-trip-line";
    // **المسارُ الحقيقيُّ يسبق المستقيم**، وما مضى منه يُقصّ عند موضع الكبتن
    const drawn = routePoints && routePoints.length >= 2
      ? trimRoute(routePoints, trimAt)
      : null;
    // **ولا خطَّ مستقيماً أثناء بحث TAXO 2.0** كما رُسم (R07): الرادارُ وحدَه يقول «نبحث»
    const straight =
      tripLine && pickup && dropoff && !(t2 && searching)
        ? [
            [pickup.lng, pickup.lat],
            [dropoff.lng, dropoff.lat],
          ]
        : null;
    const coordinates = drawn ?? straight;
    const line = coordinates
      ? {
          type: "Feature" as const,
          properties: {},
          geometry: { type: "LineString" as const, coordinates },
        }
      : null;

    const source = instance.getSource(id) as mapboxgl.GeoJSONSource | undefined;
    if (!line) {
      source?.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    if (source) {
      source.setData(line);
      instance.setPaintProperty(id, "line-dasharray", drawn ? [1, 0] : [1.5, 1.5]);
      return;
    }

    instance.addSource(id, { type: "geojson", data: line });
    // **نهارُ TAXO 2.0: خطُّ الجمر فوق ظلٍّ خافت** (TaxoMap) — والتقطيعُ حيث لا مسارَ حقيقيّاً كما كان: خطٌّ مستقيمٌ بين نقطتين
    // ليس طريقاً، **ورسمُه متّصلاً كما رسمته اللوحةُ يقول «هذا هو الطريق» وليس هو**
    if (container.current) {
      const css = getComputedStyle(container.current);
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
        instance.setPaintProperty(id, "line-dasharray", drawn ? [1, 0] : [1.5, 1.5]);
        return;
      }
    }
    instance.addLayer({
      id,
      type: "line",
      source: id,
      layout: { "line-cap": "round" },
      paint: {
        // **من لوحة §1.1 لا من اللوحة المحذوفة**: كان `#facc15` — أصفرُ اللوحة
        // التي أُسقطت في 12-أ. و`paint` في mapbox لا يقرأ متغيّرات CSS، فالقيمةُ
        // تُختار من الوضع كما يُختار ستايلُ الخريطة نفسُه أعلاه
        "line-color": cssColor("--tx", dark ? "#e6edf3" : "#171b20"),
        "line-width": 4,
        "line-opacity": 0.85,
      },
    });
    instance.setPaintProperty(
      id,
      "line-dasharray",
      // متقطّعٌ عمداً حيث لا مسار: خطٌّ مستقيم بين نقطتين ليس مسار الطريق،
      // والتقطيعُ يقول ذلك بلا نصّ. والمتّصلُ يقول «هذا هو الطريق»
      drawn ? [1, 0] : [1.5, 1.5],
    );
  }, [pickup, dropoff, tripLine, routePoints, trimAt, dark, styleVersion, t2, searching]);

  // ------------------------------------------------------------ التحكّم
  useImperativeHandle(
    ref,
    (): MapHandle => ({
      // **`easeTo` لا `flyTo`**: الثانيةُ تُبعد الكاميرا ثم تقرّبها (قوسُ طيران)
      // فتُقرأ قفزةً على مسافةٍ قصيرة — وأكثرُ نداءاتنا قصيرة
      flyTo: (point, level) =>
        map.current?.easeTo({
          center: [point.lng, point.lat],
          zoom: level ?? map.current.getZoom(),
          duration: 700,
          easing: (t) => 1 - (1 - t) ** 3,
        }),
      fitBounds: (a, b, padding) =>
        map.current?.fitBounds(
          [
            [Math.min(a.lng, b.lng), Math.min(a.lat, b.lat)],
            [Math.max(a.lng, b.lng), Math.max(a.lat, b.lat)],
          ],
          { padding: { ...FIT_PADDING, ...padding }, duration: 700 },
        ),
      center: () => {
        const point = map.current?.getCenter();
        return point ? { lat: point.lat, lng: point.lng } : null;
      },
    }),
    [],
  );

  // **غيابُ توكن iOS يُسمّى ولا يُرسم فراغاً** (SPEC §58) — وغيرُ iOS كما كان
  const missing = useMapboxMissing();
  if (!token) {
    return missing ? (
      <div
        role="alert"
        className={cn(
          "flex h-full w-full items-center justify-center bg-bg px-24 text-center text-13 text-muted",
          className,
        )}
      >
        {missing}
      </div>
    ) : (
      <div
        className={cn("map-placeholder h-full w-full bg-bg", className)}
        aria-label="الخريطة غير متاحة"
      />
    );
  }

  // **الحاويةُ تحمل رموزَ الهوية نهاراً** (`t2 t2-map`): منها تُقرأ ألوانُ الصبغ والخطّ، وبها تُرسم السيارةُ والدبابيسُ بأصناف CSS
  return (
    <div
      ref={container}
      className={cn("h-full w-full", t2 && "t2 t2-map", className)}
      style={controlsInset > 0 ? ({ "--t2-map-inset": `${controlsInset}px` } as CSSProperties) : undefined}
    />
  );
});
