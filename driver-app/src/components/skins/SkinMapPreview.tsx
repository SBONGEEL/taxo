/** **معاينةٌ حيّةٌ على خريطةٍ مصغّرة — كما سيراها الراكب** (2026-08-22).
 *
 * **ولمَ خريطةٌ حقيقيةٌ لا مربّعٌ ملوّن**: ما يُشترى هنا **علامةٌ على خريطة**،
 * ومقاسُها ٣٤ بكسلاً فوق شارعٍ رماديّ — لا رسمةٌ بعرض الشاشة. فمن يشتري
 * بالرسمة الكبيرة وحدَها يشتري شيئاً لن يراه أحدٌ بهذا الحجم قط.
 *
 * **وواحدةٌ لا شبكةٌ منها**: هذه تُبنى في **ورقة المنتج** — بطاقةٌ واحدةٌ
 * مفتوحةٌ في كلِّ لحظة. وخريطةٌ في كلِّ بطاقةٍ من عشرين تفتح عشرين محرّكَ
 * رسمٍ في هاتفٍ يعمل ساعاتٍ في سيارة، وهو ما تمنعه قاعدةُ «CSS لا حلقةُ رسم».
 *
 * **وبلا توكن: الشريطُ المائل** — نفسُ نائبِ `MapView` بحرفه، فلا شاشةَ
 * بيضاء ولا رسالةُ عطبٍ في ورقة بيع.
 *
 * **ولا تفاعلَ فيها** (`interactive: false`): معاينةٌ تُقرأ لا خريطةٌ تُقاد،
 * وإصبعٌ يسحبها داخل ورقةٍ يمنع الورقةَ من التمرير.
 */

import mapboxgl from "mapbox-gl";

// **تشكيلُ العربية قبل إنشاء الخريطة** — وحدةٌ ذاتُ أثرٍ جانبيٍّ تُقيَّم
// عند الاستيراد، فتسبق كلَّ `new mapboxgl.Map` في هذا الملف.
import "@/lib/map-rtl";
import { useEffect, useRef } from "react";

import type { VehicleSkin } from "@/api/types";
import { useMapboxToken } from "@/lib/config";
import { applyMarkerHeading, selfMarkerElement } from "@/lib/skin-marker";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const STYLE_LIGHT = "mapbox://styles/mapbox/streets-v12";
const STYLE_DARK = "mapbox://styles/mapbox/dark-v11";

/** وسطُ عمّان — **موضعُ معاينةٍ لا موضعُ أحد**: المعاينةُ تُفتح قبل أن يُبثّ
 *  موقعٌ أحياناً، وانتظارُ إشارةٍ يجعل ورقةَ البيع فارغةً بلا سبب. */
const PREVIEW_CENTER: [number, number] = [35.9106, 31.9539];

/** **زاويةٌ غيرُ صفريةٍ بقصد**: ٤٢° تُظهر أن المرسومةَ تدور وأن الواقعيّة
 *  ثابتة — وصفرٌ يجعل الحالين متطابقتين في المعاينة ثم يفترقان بعد الشراء. */
const PREVIEW_HEADING = 42;

export function SkinMapPreview({
  skin,
  className,
}: {
  skin: VehicleSkin;
  className?: string;
}) {
  const token = useMapboxToken();
  const { dark } = useTheme();
  const host = useRef<HTMLDivElement | null>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const marker = useRef<mapboxgl.Marker | null>(null);

  useEffect(() => {
    if (!token || !host.current || map.current) return;
    mapboxgl.accessToken = token;
    map.current = new mapboxgl.Map({
      container: host.current,
      style: dark ? STYLE_DARK : STYLE_LIGHT,
      center: PREVIEW_CENTER,
      zoom: 16,
      interactive: false,
      attributionControl: false,
    });
    return () => {
      marker.current?.remove();
      marker.current = null;
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    map.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    marker.current?.remove();
    const element = selfMarkerElement({ skin, subscribed: true });
    applyMarkerHeading(element, PREVIEW_HEADING, skin.map_rotates);
    marker.current = new mapboxgl.Marker({ element, rotationAlignment: "map" })
      .setLngLat(PREVIEW_CENTER)
      .addTo(instance);
  }, [skin]);

  if (!token) {
    return (
      <div
        className={cn(
          "relative flex items-center justify-center overflow-hidden rounded-14 border border-line bg-stripe",
          className,
        )}
      >
        <SkinOnly skin={skin} />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-14 border border-line",
        className,
      )}
    >
      <div ref={host} className="h-full w-full" />
    </div>
  );
}

/** بلا خريطةٍ تُرسم العلامةُ وحدَها **بمقاسها الحقيقيّ** — فالمقاسُ هو
 *  المقصودُ من المعاينة، لا الشارعُ تحتها. */
function SkinOnly({ skin }: { skin: VehicleSkin }) {
  const host = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const element = selfMarkerElement({ skin, subscribed: true });
    applyMarkerHeading(element, PREVIEW_HEADING, skin.map_rotates);
    node.replaceChildren(element);
  }, [skin]);
  return <div ref={host} />;
}
