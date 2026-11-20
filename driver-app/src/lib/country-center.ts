import type { Coordinates } from "@/api/types";

/** **مركزُ خريطة الدولة حين لا موقع** — عاصمتُها، كما في تطبيق الراكب (`customer-app/src/lib/geocode.ts`) حرفاً.
 *
 * **قِيس على S21 (٢٠٢٦-١١-٢٠)**: كبتنٌ ليبيٌّ في تاجوراء يرى عمّانَ في خريطة الرئيسيّة ما دام غيرَ متّصل — موقعُ الخريطة كان يُقرأ
 * من المقبس وحدَه (لا يُفتح إلا بالاستقبال)، والمركزُ الاحتياطيُّ في `MapView` عمّانُ لكلِّ دولة. */
const CENTER: Record<string, Coordinates> = {
  JO: { lat: 31.9539, lng: 35.9106 }, // عمّان
  LY: { lat: 32.8872, lng: 13.1913 }, // طرابلس
  DZ: { lat: 36.7538, lng: 3.0588 }, // الجزائر العاصمة
};

export function countryCenter(country: string | null | undefined): Coordinates | null {
  return (country && CENTER[country]) || null;
}
