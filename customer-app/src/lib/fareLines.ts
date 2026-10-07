/** تفصيلُ الأجرة كما جمّدته الخلفية (R10، SPEC §٦٢-د/٦ و`design/APPROVALS-62.md` §١) — **يُرسم ولا يُحسب**.
 *
 * **مجموعُ الأسطر هو الأجرةُ نفسُها حرفاً** (الخلفيةُ تكتبها من الحساب الذي يصنع السعر، §١٤)، فالواجهةُ لا تجمع ولا تضرب:
 * المبلغُ يُرسم كما وصل، **والكمّيةُ لتسمية السطر وحدها** (الكيلومترات والدقائق وعددُ المحطات). **ورحلةٌ أقدمُ من التجميد
 * بلا أسطر** — فلا يُرسم لها تفصيلٌ ولا يُخترع.
 */

import type { FareLine, Ride } from "@/api/types";
import { digits, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

/** اسمُ السطر بصنفه — **ما رُسم في التصميم المُقَرّ** حرفاً. */
function fareLineLabel(line: FareLine): string {
  switch (line.kind) {
    case "base":
      return "الأجرة الأساسية";
    case "distance":
      return line.quantity ? `المسافة · ${formatDistance(line.quantity)}` : "المسافة";
    case "time":
      return line.quantity ? `الوقت · ${formatDuration(line.quantity)}` : "الوقت";
    case "stops":
      return line.quantity ? `رسم المحطات (${digits(Math.round(Number(line.quantity)))})` : "رسم المحطات";
    case "minimum":
      return "تكملة الحدّ الأدنى";
    case "waiting":
      return "رسم الانتظار عند المحطات";
    case "pause":
      return "رسم الوقفات أثناء الرحلة";
    // **رسمُ المطار** (§٦٣-ج/٢) — لا لوحةَ له بعد؛ اسمُه كما يقوله الراكبُ للكبتن
    case "airport_fee":
      return "رسم المطار";
    // **رسمُ الطرد** (§٦٣-ج/٤) — كرسم المطار: للكبتن، داخلَ الأجرة سطراً مستقلاً
    case "parcel_fee":
      return "رسم الطرد";
  }
}

/** **سطورُ التفصيل جاهزةً للرسم** — `null` لرحلةٍ بلا تفصيلٍ مجمَّد (فتبقى الشاشةُ على سطورها السابقة). */
export function fareLineRows(ride: Ride): { label: string; value: string }[] | null {
  if (ride.fare_lines.length === 0) return null;
  return ride.fare_lines.map((line) => ({ label: fareLineLabel(line), value: formatMoney(line.amount, ride.currency) }));
}
