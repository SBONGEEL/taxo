/** تفصيلُ الأجرة كما جمّدته الخلفية (R10، SPEC §٦٢-د/٦ و`design/APPROVALS-62.md` §١) — **يُرسم ولا يُحسب**.
 *
 * **مجموعُ الأسطر هو الأجرةُ نفسُها حرفاً** (الخلفيةُ تكتبها من الحساب الذي يصنع السعر، §١٤)، فالواجهةُ لا تجمع ولا تضرب:
 * المبلغُ يُرسم كما وصل، **والكمّيةُ لتسمية السطر وحدها** (الكيلومترات والدقائق وعددُ المحطات). **ورحلةٌ أقدمُ من التجميد
 * بلا أسطر** — فلا يُرسم لها تفصيلٌ ولا يُخترع.
 */

import type { FareLine, Ride } from "@/api/types";
import { digits, formatDistance, formatDuration, formatMoney } from "@/lib/utils"; import { tr } from "@/lib/i18n";

/** اسمُ السطر بصنفه — **ما رُسم في التصميم المُقَرّ** حرفاً. */
function fareLineLabel(line: FareLine): string {
  switch (line.kind) {
    case "base":
      return tr("الأجرة الأساسية");
    case "distance":
      return line.quantity ? tr("المسافة · {0}", { 0: formatDistance(line.quantity) }) : tr("المسافة");
    case "time":
      return line.quantity ? tr("الوقت · {0}", { 0: formatDuration(line.quantity) }) : tr("الوقت");
    case "stops":
      return line.quantity ? tr("رسم المحطات ({0})", { 0: digits(Math.round(Number(line.quantity))) }) : tr("رسم المحطات");
    case "minimum":
      return tr("تكملة الحدّ الأدنى");
    case "waiting":
      return tr("رسم الانتظار عند المحطات");
    case "pause":
      return tr("رسم الوقفات أثناء الرحلة");
    // **رسمُ المطار** (§٦٣-ج/٢) — لا لوحةَ له بعد؛ اسمُه كما يقوله الراكبُ للكبتن
    case "airport_fee":
      return tr("رسم المطار");
    // **رسمُ الطرد** (§٦٣-ج/٤) — كرسم المطار: للكبتن، داخلَ الأجرة سطراً مستقلاً
    case "parcel_fee":
      return tr("رسم الطرد");
    // **بالساعة** (§٦٣-ج/٥) — المحجوزُ بعدد ساعاته، **وما زاد عليه سطرٌ لكلٍّ بكمّيته**: الكيلومتراتُ فوق المشمولة والدقائقُ فوق
    // الساعات، كلٌّ بالتعرفة العاديّة. والكمّيةُ للتسمية وحدَها — المبلغُ كما جمّدته الخلفية
    case "hourly":
      return line.quantity ? tr("الساعات المحجوزة ({0})", { 0: digits(Math.round(Number(line.quantity))) }) : tr("الساعات المحجوزة");
    case "hourly_extra_km":
      return line.quantity ? tr("مسافةٌ زائدة · {0}", { 0: formatDistance(line.quantity) }) : tr("مسافةٌ زائدة");
    case "hourly_extra_time":
      return line.quantity ? tr("وقتٌ زائد · {0} د", { 0: digits(Math.round(Number(line.quantity))) }) : tr("وقتٌ زائد");
    // **المشوارُ الثابت** (§٦٣-ج/٦) — سطرٌ واحدٌ لا تفصيلَ طريق: السعرُ جُمِّد يومَ الاشتراك ولا يتبع الطريقَ ولا الذروة
    case "commute":
      return tr("سعرُ المشوار المجمَّد");
    // **التقريب** (§٧٠-ج/٤) — فرقُ تقريب ما على الراكب إلى وحدة سوقه، **كتبته الخلفيةُ سطراً** فتُجمع السطورُ إلى الأجرة حرفاً.
    // **وقد يكون سالباً** (قُرِّب للأدنى) — و`formatMoney` يرسم علامتَه كما وصلت، ولا يُحسب هنا شيء
    case "rounding":
      return tr("تقريب");
    // **ولايةُ الانطلاق الوعرة** (SPEC §٧٤-أ/٥) — زيادتُها سطرٌ بذاته، كما رآه الراكبُ قبل الطلب
    case "rugged":
      return tr("تسعيرة المناطق الوعرة");
  }
}

/** **سطورُ التفصيل جاهزةً للرسم** — `null` لرحلةٍ بلا تفصيلٍ مجمَّد (فتبقى الشاشةُ على سطورها السابقة). */
export function fareLineRows(ride: Ride): { label: string; value: string }[] | null {
  if (ride.fare_lines.length === 0) return null;
  return ride.fare_lines.map((line) => ({ label: fareLineLabel(line), value: formatMoney(line.amount, ride.currency) }));
}

/** **سطرُ «تقريب» وحدَه** (SPEC §٧٠-ج/٤) — لشاشةٍ تفصّل الأجرةَ بسطورٍ مختارةٍ لا بالتفصيل كلِّه (شاشةُ الدفع: المحطاتُ والانتظارُ
 *  والوقفات). **باسمه من بيته هنا** ومبلغِه كما كتبته الخلفية، و`null` حين لا سطر: سوقٌ مطفأ، أو فرقٌ صفريّ، أو رحلةٌ لم تنتهِ. */
export function roundingRow(ride: Ride): { label: string; value: string } | null {
  const line = ride.fare_lines.find((entry) => entry.kind === "rounding");
  return line ? { label: fareLineLabel(line), value: formatMoney(line.amount, ride.currency) } : null;
}
