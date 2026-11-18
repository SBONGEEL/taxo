/** **دبابيسُ أماكن الفهرس بأيقونة نوع** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني §٣/٣) — **منسوخٌ حرفاً في التطبيقين**.
 *
 * أيقوناتُ Lucide (رخصةُ ISC، في الحزمة أصلاً) تُرسم مرّةً إلى صورةٍ نقطيّة وتُسجَّل في الخريطة باسم `taxo-pin-<الفئة>`:
 * دائرةٌ بلون الهوية وحلقةٌ بلون هالة الأسماء والأيقونةُ فيها — **لا أيقوناتُ Google ولا تصميمُها**. وفئةٌ بلا أيقونةٍ تأخذ دبّوساً عامّاً.
 * **والرسمُ عبر React نفسِه** (`flushSync` في عقدةٍ منفصلة) — فلا مكتبةَ رسمٍ ثانيةٌ ولا `react-dom/server` في الحزمة.
 */
import {
  Banknote, BedDouble, Building2, Bus, Car, Church, Coffee, Construction, Fuel, GraduationCap, Hospital, Landmark, MapPin, Moon,
  OctagonX, Pill, Plane, School, ShoppingBag, ShoppingCart, Stethoscope, Store, TrainFront, TriangleAlert, Utensils, type LucideIcon,
} from "lucide-react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

/** **الفئةُ ⇐ الأيقونة** — فئاتُ `MapPlaceCategory` في الخلفية؛ والحيُّ والشارعُ اسمٌ بلا دبّوس (مساحةٌ لا نقطة). */
export const PIN_ICONS: Record<string, LucideIcon> = {
  market: Store,
  shop: ShoppingBag,
  mall: ShoppingCart,
  mosque: Moon,
  church: Church,
  hospital: Hospital,
  clinic: Stethoscope,
  school: School,
  university: GraduationCap,
  hotel: BedDouble,
  restaurant: Utensils,
  landmark: Landmark,
  government: Building2,
  station: TrainFront,
  airport: Plane,
  pickup: MapPin,
  other: MapPin,
  // **فئاتُ الطبقة المفتوحة** (أمرُ المالك ١٨/١١ السابع ٢-٤) — `lib/open-layers.ts`
  pharmacy: Pill,
  bank: Banknote,
  fuel: Fuel,
  cafe: Coffee,
  transport: Bus,
  place: MapPin,
  // **بلاغاتُ الطريق والصيانة** (٣-٣)
  works: Construction,
  closed: OctagonX,
  accident: TriangleAlert,
  jam: Car,
};

/** فئاتٌ تُرسم اسماً وحدَه — **الحيُّ مساحةٌ والشارعُ خطّ**، ودبّوسٌ عليهما يكذب في موضعه. */
export const NO_PIN = ["neighborhood", "street"];

export const PIN_PREFIX = "taxo-pin-";
const SIZE = 26;

function svgOf(Icon: LucideIcon, color: string): string {
  const host = document.createElement("div");
  const root = createRoot(host);
  flushSync(() => root.render(<Icon size={14} color={color} strokeWidth={2.2} />));
  const svg = host.innerHTML;
  root.unmount();
  return svg;
}

async function raster(svg: string, fill: string, ring: string, ratio: number): Promise<ImageData> {
  const px = Math.round(SIZE * ratio);
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = px;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no-2d");
  ctx.scale(ratio, ratio);
  ctx.beginPath();
  ctx.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 1.5, 0, Math.PI * 2);
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = ring;
  ctx.stroke();
  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  await image.decode();
  ctx.drawImage(image, (SIZE - 14) / 2, (SIZE - 14) / 2, 14, 14);
  return ctx.getImageData(0, 0, px, px);
}

type ImageHost = {
  hasImage(id: string): boolean;
  addImage(id: string, image: ImageData, options?: { pixelRatio?: number }): void;
};

/** **يسجّل أيقوناتِ الفئات الحاضرة** — ما سُجّل لا يُعاد، وفشلُ صورةٍ يترك الدائرةَ والاسمَ كما كانا (لا خطأَ يُعرض). */
export async function addPinImages(
  map: ImageHost,
  categories: Iterable<string>,
  fill: string,
  ring: string,
  iconColor: string,
  prefix: string = PIN_PREFIX,
) {
  const ratio = Math.min(3, Math.max(1, Math.round(window.devicePixelRatio || 1)));
  for (const category of new Set(categories)) {
    const id = prefix + category;
    const Icon = PIN_ICONS[category];
    if (!Icon || map.hasImage(id)) continue;
    try {
      const data = await raster(svgOf(Icon, iconColor), fill, ring, ratio);
      if (!map.hasImage(id)) map.addImage(id, data, { pixelRatio: ratio });
    } catch {
      // متصفّحٌ لا يفكّ SVG — تبقى النقطةُ والاسم
    }
  }
}
