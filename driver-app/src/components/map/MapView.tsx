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
 * **ولا خطَّ مسارٍ بين النقطتين**: هندسة المسار تأتي من Mapbox Directions
 * ونداؤها من الخلفية حصراً (القسم 2/14)، وما يصل الواجهة مسافةٌ ومدةٌ وسعر.
 * وخطٌّ نرسمه من عندنا يوهم بمسارٍ لم يقله أحد — نفس قرار تطبيق الراكب.
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

import type { Coordinates } from "@/api/types";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

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
    });
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
  return <div ref={host} className={cn("h-full w-full", className)} />;
}
