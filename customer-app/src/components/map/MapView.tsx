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
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
} from "react";

import "mapbox-gl/dist/mapbox-gl.css";

import type { Coordinates, NearbyDriver } from "@/api/types";
import { trimRoute } from "@/lib/route-line";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

// زمن تنعيم الحركة: أقصر قليلاً من دورة البثّ، فتصل السيارة موضعها الجديد
// قبيل وصول التالي بدل أن تتقطع الحركة أو تتأخر عنه
const NEARBY_TWEEN_MS = 4_500;
const DRIVER_TWEEN_MS = 2_800;

export interface MapHandle {
  /** يعيد التوسيط على نقطة (عند الضغط على «موقعي»). */
  flyTo: (point: Coordinates, zoom?: number) => void;
  /** يضبط الإطار ليضم النقطتين معاً. */
  fitBounds: (a: Coordinates, b: Coordinates) => void;
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
}

function carElement(color: string): HTMLElement {
  const element = document.createElement("div");
  element.className = "taxo-car";
  element.innerHTML = `
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none"
         style="filter: drop-shadow(0 2px 3px rgb(0 0 0 / 0.35))">
      <path d="M12 2.5 19 20.5 12 16.8 5 20.5Z" fill="${color}"
            stroke="rgba(0,0,0,0.35)" stroke-width="0.8" stroke-linejoin="round"/>
    </svg>`;
  element.style.willChange = "transform";
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
    interactive = true,
    onMoveEnd,
    className,
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
  const pickupMarker = useRef<mapboxgl.Marker | null>(null);
  const myLocationMarker = useRef<mapboxgl.Marker | null>(null);
  const searchPulse = useRef<mapboxgl.Marker | null>(null);
  const dropoffMarker = useRef<mapboxgl.Marker | null>(null);
  const frame = useRef<number | null>(null);
  const moveEnd = useRef(onMoveEnd);
  const { dark } = useTheme();

  moveEnd.current = onMoveEnd;

  // ------------------------------------------------------------ الإنشاء
  useEffect(() => {
    if (!token || !container.current || map.current) return;

    mapboxgl.accessToken = token;
    const instance = new mapboxgl.Map({
      container: container.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
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
      setStyleVersion((version) => version + 1);
    });
    instance.on("moveend", () => {
      const point = instance.getCenter();
      moveEnd.current?.({ lat: point.lat, lng: point.lng });
    });

    map.current = instance;

    return () => {
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
  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
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
        entry.element.style.rotate = `${lerpAngle(
          entry.headingFrom,
          entry.headingTo,
          eased,
        )}deg`;
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

      const element = carElement(driver.vehicle_category === "comfort" ? "#38bdf8" : "#facc15");
      element.style.rotate = `${driver.heading ?? 0}deg`;
      const marker = new mapboxgl.Marker({ element, rotationAlignment: "map" })
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
      });
    }

    for (const [ref, entry] of carMarkers.current) {
      if (!seen.has(ref)) {
        entry.marker.remove();
        carMarkers.current.delete(ref);
      }
    }
  }, [drivers, ensureLoop]);

  // ------------------------------------------------- موقع الكبتن المُسنَد
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    if (!driverLocation) {
      driverMarker.current?.marker.remove();
      driverMarker.current = null;
      return;
    }

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

    const element = carElement("#facc15");
    element.style.rotate = `${driverLocation.heading ?? 0}deg`;
    driverMarker.current = {
      marker: new mapboxgl.Marker({ element, rotationAlignment: "map" })
        .setLngLat([point.lng, point.lat])
        .addTo(instance),
      element,
      from: point,
      to: point,
      headingFrom: driverLocation.heading ?? 0,
      headingTo: driverLocation.heading ?? 0,
      startedAt: performance.now(),
      duration: DRIVER_TWEEN_MS,
    };
  }, [driverLocation, ensureLoop]);

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
        element: pulseElement("موقعي"),
      })
        .setLngLat([showMyLocation.lng, showMyLocation.lat])
        .addTo(instance);
      return;
    }
    myLocationMarker.current.setLngLat([showMyLocation.lng, showMyLocation.lat]);
  }, [showMyLocation]);

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
        element: pulseElement("جارٍ البحث عن كبتن"),
      })
        .setLngLat([pickup.lng, pickup.lat])
        .addTo(instance);
      return;
    }
    searchPulse.current.setLngLat([pickup.lng, pickup.lat]);
  }, [searching, pickup]);

  // ----------------------------------------------------- الدبابيس والخط
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    const place = (
      slot: React.MutableRefObject<mapboxgl.Marker | null>,
      point: Coordinates | null | undefined,
      color: string,
      label: string,
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
      slot.current = new mapboxgl.Marker({
        element: pinElement(color, label),
        anchor: "bottom",
      })
        .setLngLat([point.lng, point.lat])
        .addTo(instance);
    };

    place(pickupMarker, pickup, "#16a34a", "نقطة الانطلاق");
    place(dropoffMarker, dropoff, "#dc2626", "الوجهة");
  }, [pickup, dropoff]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || styleVersion === 0) return;

    const id = "taxo-trip-line";
    // **المسارُ الحقيقيُّ يسبق المستقيم**، وما مضى منه يُقصّ عند موضع الكبتن
    const drawn = routePoints && routePoints.length >= 2
      ? trimRoute(routePoints, trimAt)
      : null;
    const straight =
      tripLine && pickup && dropoff
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
    instance.addLayer({
      id,
      type: "line",
      source: id,
      layout: { "line-cap": "round" },
      paint: {
        // **من لوحة §1.1 لا من اللوحة المحذوفة**: كان `#facc15` — أصفرُ اللوحة
        // التي أُسقطت في 12-أ. و`paint` في mapbox لا يقرأ متغيّرات CSS، فالقيمةُ
        // تُختار من الوضع كما يُختار ستايلُ الخريطة نفسُه أعلاه
        "line-color": dark ? "#e6edf3" : "#171b20",
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
  }, [pickup, dropoff, tripLine, routePoints, trimAt, dark, styleVersion]);

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
      fitBounds: (a, b) =>
        map.current?.fitBounds(
          [
            [Math.min(a.lng, b.lng), Math.min(a.lat, b.lat)],
            [Math.max(a.lng, b.lng), Math.max(a.lat, b.lat)],
          ],
          { padding: { top: 90, bottom: 320, left: 60, right: 60 }, duration: 700 },
        ),
      center: () => {
        const point = map.current?.getCenter();
        return point ? { lat: point.lat, lng: point.lng } : null;
      },
    }),
    [],
  );

  if (!token) {
    return (
      <div
        className={cn("map-placeholder h-full w-full bg-bg", className)}
        aria-label="الخريطة غير متاحة"
      />
    );
  }

  return <div ref={container} className={cn("h-full w-full", className)} />;
});
