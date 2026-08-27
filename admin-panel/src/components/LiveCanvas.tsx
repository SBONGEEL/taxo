/** لوحُ الخريطة الحيّة — الملفُّ الوحيد في اللوحة الذي يعرف `mapbox-gl`.
 *
 * وهو **ليس** نسخةً من `MapView` في تطبيق الراكب رغم تشابه نصف عمله: ذاك يرسم
 * سياراتٍ مجهَّلةً ودبوسَي رحلةٍ واحدة، وهذا يرسم أشخاصاً بأسمائهم وطلباتٍ بلا
 * أصحاب. توحيدُهما في مكوّنٍ واحدٍ بخصائص اختيارية يجعل تسريبَ اسمٍ إلى شاشة
 * الراكب خاصيةً منسيةً بدل أن يكون مستحيلاً.
 *
 * **والعلامة تُحدَّث ولا تُعاد**: بناءُ العلامات من جديد عند كل استعلامٍ يعيد
 * ضبط تقريب الخريطة وتحريكها من تحت يد المشرف كل بضع ثوانٍ. فالعلاماتُ مفهرسةٌ
 * بالمعرّف، تُنقل إن بقيت وتُحذف إن غابت.
 *
 * **ولا تنعيمَ للحركة هنا** خلافاً لتطبيق الراكب: التنعيم يخدم راكباً يتابع
 * سيارةً واحدة قادمةً إليه؛ والمشرف يسأل «أين هم الآن»، وسيارةٌ تتحرك ببطءٍ
 * نحو موضعٍ قديمٍ تجيبه بموضعٍ لم يكن صحيحاً حين نظر.
 *
 * وبلا توكن (عقد Mapbox غير مفعّل) تبقى القائمة الجانبية كاملةً وتظهر مكان
 * الخريطة لوحةٌ تقول السبب — فالمعلومة كلُّها في القائمة، والخريطةُ عرضٌ لها.
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// **يقع باستيراد الاسم كما يقع بالاستيراد المجرَّد**: الوحدةُ تُقيَّم مرّةً
// عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import type { LiveDriver, LivePendingRide } from "@/api/types";
import { useTheme } from "@/lib/theme";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

interface Props {
  token: string | null;
  center: { lat: number; lng: number };
  drivers: LiveDriver[];
  pendingRides: LivePendingRide[];
  selected: string | null;
  onSelect: (driverId: string | null) => void;
}

/** غلافُ العلامة **يملكه mapbox**، والشكلُ في ابنٍ داخله.
 *
 * لأن `Marker` يضيف صنفَه الخاص (`mapboxgl-marker`) إلى العنصر الممرَّر وفيه
 * `position:absolute` — فكتابةُ `className` عليه تمسحه، فتسقط العلامة إلى
 * تدفق الصفحة وتختفي من الخريطة بلا خطأٍ في الطرفية. وهو ما وقع.
 */
function markerShell(): HTMLElement {
  const shell = document.createElement("div");
  shell.appendChild(document.createElement("span"));
  return shell;
}

/** يضبط شكلَ علامةٍ قائمة بدل بنائها — انظر ملاحظة «تُحدَّث ولا تُعاد» أعلاه. */
function paintDriver(shell: HTMLElement, driver: LiveDriver, selected: boolean) {
  const face = shell.firstElementChild as HTMLElement;
  face.className = [
    "flex size-26 cursor-pointer items-center justify-center rounded-full",
    "border-2 text-11 font-bold",
    // تُقرأ على خريطةٍ داكنةٍ وفاتحة معاً: قرصٌ ممتلئ بلونٍ نقيض لا قرصٌ
    // بلون السطح — علامةٌ رماديةٌ على أسفلت رمادي ليست علامة
    // **ثلاثُ حالاتٍ لا اثنتان**: «شاحبٌ» ليس «متفرّغاً» — بثُّه توقّف
    // ومفتاحُ حضوره على وشك الانقضاء، فيختفي من الخريطة بلا أن يتحرك شيء.
    // ومن يقرؤه متفرّغاً يبني عليه قراراً وهو غيرُ موجود
    driver.state === "on_ride"
      ? "border-ok bg-ok text-accent-ink"
      : driver.state === "stale"
        ? "border-warn bg-bg text-warn opacity-60"
        : "border-bg bg-ink text-bg",
    selected ? "outline outline-2 outline-accent" : "",
  ].join(" ");
  face.textContent = driver.name.trim().charAt(0) || "؟";
  // الاسمُ كاملاً في التلميح، وفي القائمة الجانبية معه الرقم واللوحة
  face.title =
    driver.state === "stale" && driver.seconds_since_update !== null
      ? `${driver.name} — آخر بثّ منذ ${driver.seconds_since_update} ثانية`
      : driver.name;
}

function pendingElement(): HTMLElement {
  const shell = markerShell();
  const face = shell.firstElementChild as HTMLElement;
  face.className = "block size-14 rounded-full border-2 border-warn bg-bg";
  face.title = "طلبٌ بانتظار سائق";
  return shell;
}

export function LiveCanvas({
  token,
  center,
  drivers,
  pendingRides,
  selected,
  onSelect,
}: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const driverMarkers = useRef(new Map<string, mapboxgl.Marker>());
  const rideMarkers = useRef(new Map<string, mapboxgl.Marker>());
  const { dark } = useTheme();

  useEffect(() => {
    if (!token || !holder.current || map.current) return;
    mapboxgl.accessToken = token;
    map.current = new mapboxgl.Map({
      container: holder.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      language: MAP_LANGUAGE,
      center: [center.lng, center.lat],
      zoom: 11,
      attributionControl: false,
    });
    return () => {
      map.current?.remove();
      map.current = null;
      driverMarkers.current.clear();
      rideMarkers.current.clear();
    };
    // التوكن والمركز الأولّيان وحدهما ينشئان الخريطة — وإلا أُعيد بناؤها
    // كلما تحرّك المشرف
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    const seen = new Set<string>();
    for (const driver of drivers) {
      seen.add(driver.driver_id);
      const marker = driverMarkers.current.get(driver.driver_id);
      if (marker) {
        marker.setLngLat([driver.lng, driver.lat]);
        paintDriver(marker.getElement(), driver, selected === driver.driver_id);
        continue;
      }
      const element = markerShell();
      element.addEventListener("click", () => onSelect(driver.driver_id));
      paintDriver(element, driver, selected === driver.driver_id);
      driverMarkers.current.set(
        driver.driver_id,
        // **الموضع قبل `addTo`**: الإضافة ترسم فوراً وتقرأ إحداثياتِ العلامة،
        // فعلامةٌ بلا موضعٍ تُسقط الشاشة كلَّها — وهو ما وقع فعلاً
        new mapboxgl.Marker({ element })
          .setLngLat([driver.lng, driver.lat])
          .addTo(instance),
      );
    }
    for (const [id, marker] of driverMarkers.current) {
      if (!seen.has(id)) {
        marker.remove();
        driverMarkers.current.delete(id);
      }
    }
  }, [drivers, selected, onSelect]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;

    const seen = new Set<string>();
    for (const ride of pendingRides) {
      seen.add(ride.ride_id);
      const existing = rideMarkers.current.get(ride.ride_id);
      if (existing) {
        existing.setLngLat([ride.lng, ride.lat]);
        continue;
      }
      rideMarkers.current.set(
        ride.ride_id,
        new mapboxgl.Marker({ element: pendingElement() })
          .setLngLat([ride.lng, ride.lat])
          .addTo(instance),
      );
    }
    for (const [id, marker] of rideMarkers.current) {
      if (!seen.has(id)) {
        marker.remove();
        rideMarkers.current.delete(id);
      }
    }
  }, [pendingRides]);

  // التوسيطُ على من اختاره المشرف يقع **مرةً عند الاختيار** لا عند كل استعلام:
  // خريطةٌ تعيد التوسيط كل خمس ثوانٍ تنتزع التحكم من يده وهو ينظر
  const flownTo = useRef<string | null>(null);
  useEffect(() => {
    if (selected === flownTo.current) return;
    flownTo.current = selected;
    const driver = drivers.find((row) => row.driver_id === selected);
    if (driver) {
      map.current?.flyTo({ center: [driver.lng, driver.lat], zoom: 14 });
    }
  }, [selected, drivers]);

  if (!token) {
    return (
      <div className="flex h-full items-center justify-center rounded-16 border border-line bg-surface-2 p-24 text-center">
        <p className="text-12.5 leading-relaxed text-muted">
          عقدُ Mapbox غير مفعّل لهذه الدولة، فلا خريطة.
          <br />
          القائمةُ إلى الجانب كاملةٌ — فيها كلُّ ما ترسمه الخريطة.
        </p>
      </div>
    );
  }

  return <div ref={holder} className="h-full w-full rounded-16" />;
}
