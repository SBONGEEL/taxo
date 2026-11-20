/** **سياراتُ TAXO ثلاثيّةُ الأبعاد** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن) — نماذجُ أصيلةٌ من `design/cars-3d/` بلا طرازٍ حقيقيٍّ ولا شعار،
 *  واللمسةُ البرتقاليّةُ على السيارة نفسِها (شريطُ الضوء والخطُّ والمرايا والعجلات). **ومنسوخٌ بايتاً في التطبيقات الثلاثة.**
 *
 *  ثلاثةُ أرباعٍ لأيقونة الفئة (نهاراً وليلاً، ١٦٠/٣٢٠/٦٤٠)، ومنظرٌ علويٌّ لعلامة الخريطة. **وخدمةُ النساء بلونها**، ومتجرُ المركبات
 *  (العاديّة والمميّزة) رسومُه في الخلفيّة؛ **والنادرةُ والأسطوريّةُ يرفعها المالك ولا تُمسّ.** */

export const CAR_KEYS = ["economy", "comfort", "vip", "hatchback", "suv", "family", "van", "city_taxi", "women"] as const;
export type CarKey = (typeof CAR_KEYS)[number];

/** **الفئةُ بمفتاحها أوّلاً** (`vip` و`city_taxi` و`family` لها سيّاراتها)، **ثمّ بأيقونتها** — فئةٌ جديدةٌ يضيفها المشرفُ تأخذ سيّارةَ أيقونتها. */
const CAR_FOR_GLYPH: Readonly<Record<string, CarKey>> = {
  local_taxi: "economy",
  directions_car: "comfort",
  electric_car: "comfort",
  airport_shuttle: "van",
  directions_bus: "van",
  local_shipping: "van",
  accessible: "family",
  woman: "women",
};

export function carKey(icon: string, category?: string | null): CarKey {
  if (category && (CAR_KEYS as readonly string[]).includes(category)) return category as CarKey;
  if (category && category.includes("women")) return "women";
  return CAR_FOR_GLYPH[icon] ?? "economy";
}

const BASE = `${import.meta.env.BASE_URL}cars/`;
const WIDTHS = [160, 320, 640] as const;

export function carSrc(key: CarKey, night: boolean, width: (typeof WIDTHS)[number] = 320): string {
  return `${BASE}${key}-34-${night ? "night" : "day"}-${width}.webp`;
}

export function carSrcSet(key: CarKey, night: boolean): string {
  return WIDTHS.map((w) => `${carSrc(key, night, w)} ${w}w`).join(", ");
}

/** المنظرُ العلويُّ الأبيض — علامةُ الخريطة العامّة (والبرتقاليُّ ثابتٌ عليها). */
export function carTopSrc(key: CarKey = "economy"): string {
  return `${BASE}${key}-top-white-96.webp`;
}
