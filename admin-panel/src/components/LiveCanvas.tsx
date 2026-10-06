/** لوحُ الخريطة الحيّة — **أوّلُ ثلاثةِ ملفّاتٍ في اللوحة تعرف `mapbox-gl`**.
 *
 * **وكان مكتوباً هنا «الملفُّ الوحيد»، فبلي ولم يُصحَّح** (قِيس 2026-09-03):
 * `SkinMapPreview` يستورده منذ دفعة المتجر، و`RouteCanvas` منذ البند ٦. وثلاثتُها
 * تشترك في `lib/map-rtl` وحدَه — **وهو الوحيد الذي يجب أن يبقى واحداً**، لأن
 * `setRTLTextPlugin` عامٌّ على الوحدة ويرمي إن نُودي مرّتين.
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
 *
 * **وبلغة «TaxoMap»** (A03): الأرضُ والطرقُ من رموز الهوية (`lib/taxo-map`)، **والكبتنُ سيارةُ الهوية** تدور مع اتجاه سيره —
 * جسمُها بلون حاله (متفرّغٌ بلون النصّ، وفي رحلةٍ بالنجاح، ومَن توقّف بثُّه بالتنبيه خافتاً)، **والمختارُ بهالةِ الجمر**،
 * والطلبُ المنتظرُ حلقةٌ بالتنبيه. **والحالُ والاسمُ في التلميح كما كانا**، والقائمةُ إلى الجانب تقولهما نصّاً.
 */

import mapboxgl from "mapbox-gl";
import { useEffect, useRef } from "react";

import "mapbox-gl/dist/mapbox-gl.css";

// **تشكيلُ العربية قبل إنشاء الخريطة** — للوحدة أثرٌ جانبيٌّ (تسجيلُ الملحق)
// **يقع باستيراد الاسم كما يقع بالاستيراد المجرَّد**: الوحدةُ تُقيَّم مرّةً
// عند أوّل استيرادٍ أياً كانت صيغتُه، فيسبق كلَّ `new mapboxgl.Map` هنا.
import { MAP_LANGUAGE } from "@/lib/map-rtl";

import type { LiveDriver, LivePendingRide } from "@/api/types";
import { MAP_STYLE_DARK, MAP_STYLE_LIGHT, taxoLook } from "@/lib/taxo-map";
import { useTheme } from "@/lib/theme";

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

/** يضبط شكلَ علامةٍ قائمة بدل بنائها — انظر ملاحظة «تُحدَّث ولا تُعاد» أعلاه.
 *
 * **ثلاثُ حالاتٍ لا اثنتان**: «شاحبٌ» ليس «متفرّغاً» — بثُّه توقّف ومفتاحُ حضوره على وشك الانقضاء، فيختفي من الخريطة بلا
 * أن يتحرك شيء. ومن يقرؤه متفرّغاً يبني عليه قراراً وهو غيرُ موجود. **والاتّجاهُ من بثّه** (`heading`)، وغيابُه شمالٌ لا عطب. */
function paintDriver(shell: HTMLElement, driver: LiveDriver, selected: boolean) {
  const face = shell.firstElementChild as HTMLElement;
  face.className = [
    "ad-map-car",
    driver.state === "on_ride" ? "ride" : driver.state === "stale" ? "stale" : "free",
    selected ? "on" : "",
  ].join(" ");
  face.style.transform = `rotate(${driver.heading ?? 0}deg)`;
  if (!face.firstElementChild) {
    face.innerHTML = '<i class="ad-map-car-front"></i><i class="ad-map-car-back"></i>';
  }
  // الاسمُ كاملاً في التلميح، وفي القائمة الجانبية معه الرقم واللوحة
  face.title =
    driver.state === "stale" && driver.seconds_since_update !== null
      ? `${driver.name} — آخر بثّ منذ ${driver.seconds_since_update} ثانية`
      : driver.name;
}

function pendingElement(): HTMLElement {
  const shell = markerShell();
  const face = shell.firstElementChild as HTMLElement;
  face.className = "ad-map-wait";
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
  // **الستايلُ المعروضُ الآن** — يُقارَن به قبل التبديل (تحت)
  const shown = useRef<string | null>(null);

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
      center: [center.lng, center.lat],
      zoom: 11,
      attributionControl: false,
    });
    map.current = instance;
    // **صبغُ «TaxoMap» مع كلِّ ستايلٍ يُحمَّل** — تبديلُ المظهر يمسح الصبغَ كما يمسح الطبقات
    instance.on("style.load", () => taxoLook(instance, host));
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

  // **يُبدَّل الستايلُ حين تتبدّل السمةُ لا عند التركيب** (قِيس في المرحلة الثانية): كان يُنادى بالستايل نفسِه أوّلَ مرّة، **و`setStyle`
  // بالستايل نفسِه «يُفرّق» عليه** — فيعيد ألوانَ Mapbox فوق صبغ «TaxoMap» ولا يطلق `style.load` يعيده (بقيت الخريطةُ الفاتحةُ رماديّة).
  // **و`diff: false`**: التبديلُ تحميلٌ كاملٌ يطلق `style.load`، فيعود الصبغُ (وما يُرسم عليه) مع كلِّ سمة.
  useEffect(() => {
    const instance = map.current;
    const style = dark ? MAP_STYLE_DARK : MAP_STYLE_LIGHT;
    if (!instance || shown.current === style) return;
    shown.current = style;
    // **الحقلان الآخران في نوع `SetStyleOptions` إلزاميّان خطأً** (mapbox-gl 3.28): تمريرُهما `undefined` يمحو خطَّ المحرف المحلّيّ
    // الافتراضيّ، **فالتحويلُ هنا لا قيمةٌ مخترعة**
    instance.setStyle(style, { diff: false } as Parameters<mapboxgl.Map["setStyle"]>[1]);
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
      <div className="ad-map-off">
        <p>
          عقدُ Mapbox غير مفعّل لهذه الدولة، فلا خريطة.
          <br />
          القائمةُ إلى الجانب كاملةٌ — فيها كلُّ ما ترسمه الخريطة.
        </p>
      </div>
    );
  }

  return <div ref={holder} className="ad-map" />;
}
