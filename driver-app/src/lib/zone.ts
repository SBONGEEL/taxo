/** **اسمُ المنطقة الزمنيّة كما يقرؤه الكبتن** — المعرّفُ (`Asia/Amman`) نصٌّ برمجيٌّ لا يُعرض (البند ٦ من أمر المالك ٢٠٢٦-١١-٢٠،
 *  مسحُ تطبيق الكبتن حيّاً: «بتوقيت Asia/Amman»). منطقةٌ غيرُ معروفةٍ لا تُعرض أصلاً بدل أن يظهر معرّفُها. */

import { tr } from "@/lib/i18n";

const ZONE_CITY: Record<string, string> = {
  "Asia/Amman": tr("عمّان"),
  "Africa/Algiers": tr("الجزائر"),
  "Africa/Tripoli": tr("طرابلس"),
};

/** «بتوقيت عمّان. » — أو لا شيء لمنطقةٍ لا اسمَ عربيّاً لها هنا */
export function zoneNote(zone: string | null | undefined): string {
  const city = zone ? ZONE_CITY[zone] : undefined;
  return city ? tr("بتوقيت {0}. ", { 0: city }) : "";
}
