/** خريطة Mapbox — العنصر الوحيد الذي يعرف واجهة `mapbox-gl` (SPEC القسم 2).
 *
 * ثلاث مسؤوليات في تطبيق الكبتن:
 *
 * 1. **موقعُ الكبتن نفسه** — سهمٌ يدور مع الاتجاه، وحركتُه منعَّمة بين
 *    البثّات (كل ثلاث ثوانٍ) فلا تقفز الأيقونة قفزةً كل دورة.
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

import type { Coordinates } from "@/api/types";
import { type FollowMode, labelFor, nextMode } from "@/lib/follow";
import { trimRoute } from "@/lib/route-line";
import { useTheme } from "@/lib/theme";
import { arabicDigits, cn } from "@/lib/utils";

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
  className?: string;
}

const DEFAULT_CENTER: Coordinates = { lat: 31.9539, lng: 35.9106 };

function arrowElement(): HTMLElement {
  const element = document.createElement("div");
  element.innerHTML = `
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none"
         style="filter: drop-shadow(0 2px 3px rgb(0 0 0 / 0.35))">
      <path d="M12 2.5 19 20.5 12 16.8 5 20.5Z" fill="currentColor"
            stroke="rgba(0,0,0,0.35)" stroke-width="0.8" stroke-linejoin="round"/>
    </svg>`;
  element.style.willChange = "transform";
  element.style.color = "#3fb970";
  return element;
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
  routePoints = null,
  trimAt = null,
  etaMinutes = null,
  className,
}: Props) {
  const { dark } = useTheme();
  const host = useRef<HTMLDivElement | null>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const self = useRef<mapboxgl.Marker | null>(null);
  const pins = useRef<{ pickup?: mapboxgl.Marker; dropoff?: mapboxgl.Marker }>(
    {},
  );
  const animation = useRef<number | null>(null);

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

    return () => {
      if (animation.current !== null) cancelAnimationFrame(animation.current);
      map.current?.remove();
      map.current = null;
    };
    // مرةً واحدة: تبديلُ الستايل يقع في تأثيرٍ آخر بلا إعادة بناء
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  // موقعُ الكبتن — يُنعَّم بين البثّتين بدل القفز
  useEffect(() => {
    const instance = map.current;
    if (!instance || !center) return;

    if (!self.current) {
      self.current = new mapboxgl.Marker({ element: arrowElement() })
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

  useEffect(() => {
    const element = self.current?.getElement();
    if (element) {
      element.style.transform = `${element.style.transform.replace(/ rotate\([^)]*\)/, "")} rotate(${heading ?? 0}deg)`;
    }
  }, [heading, center]);

  // دبوسا الرحلة
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    for (const [key, point, color, label] of [
      ["pickup", pickup, "#3fb970", "نقطة الانطلاق"],
      ["dropoff", dropoff, "#e5534b", "الوجهة"],
    ] as const) {
      const existing = pins.current[key];
      if (!point) {
        existing?.remove();
        pins.current[key] = undefined;
        continue;
      }
      if (existing) existing.setLngLat([point.lng, point.lat]);
      else {
        pins.current[key] = new mapboxgl.Marker({
          element: pinElement(color, label),
          anchor: "bottom",
        })
          .setLngLat([point.lng, point.lat])
          .addTo(instance);
      }
    }
  }, [pickup, dropoff]);

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
      instance.addLayer({
        id,
        type: "line",
        source: id,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          // `paint` في mapbox لا يقرأ متغيّرات CSS — فالقيمةُ تُختار من الوضع
          // كما يُختار ستايلُ الخريطة نفسُه
          "line-color": dark ? "#e6edf3" : "#171b20",
          "line-width": 5,
          "line-opacity": 0.9,
        },
      });
    };

    // **الستايلُ قد لا يكون جاهزاً**: `addLayer` قبل تحميله يرمي، وتبديلُ الوضع
    // يمسح المصادر كلَّها — فيُعاد الرسمُ على `style.load` كذلك
    if (instance.isStyleLoaded()) draw();
    else instance.once("style.load", draw);
  }, [routePoints, trimAt, dark]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !fit || !pickup || !dropoff) return;
    instance.fitBounds(
      [
        [Math.min(pickup.lng, dropoff.lng), Math.min(pickup.lat, dropoff.lat)],
        [Math.max(pickup.lng, dropoff.lng), Math.max(pickup.lat, dropoff.lat)],
      ],
      { padding: 80, duration: 600, maxZoom: 15 },
    );
  }, [fit, pickup, dropoff]);

  if (!token) {
    return (
      <div
        className={cn(
          "flex h-full w-full items-center justify-center bg-stripe font-mono text-10 tracking-map text-muted",
          className,
        )}
      >
        الخريطة غير مهيأة — راجع عقد Mapbox
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

      {/* **الوصولُ المتوقَّع** — يظهر حين يُقاس ويختفي حين لا يُقاس */}
      {etaMinutes !== null ? (
        <div className="pointer-events-none absolute start-14 top-64 z-10 rounded-full border border-line bg-surface px-12 py-7 text-12 font-bold text-ink shadow-md">
          {arabicDigits(String(etaMinutes))} دقيقة
        </div>
      ) : null}

      {/* **زرُّ التموضع ثلاثيُّ الأطوار** (البند ١٧-٢) — وموضعُه فوق الخريطة
          وتحت بطاقةِ الرحلة، فلا يزاحم قراراً (قاعدةُ «لا شيءَ يعلو قراراً»).
          **ونصُّه يقول الطورَ الحاليَّ لا الفعلَ التالي**: أيقونةٌ وحدَها تجعل
          الكبتنَ يضغط ليعرف ماذا تفعل، وهو يقود */}
      {center ? (
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
