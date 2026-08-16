/** الوصولُ المتوقَّع — **يُحسب في الجهاز، ولا نداءَ واحدٌ لأجله** (البند ١٧-٣).
 *
 * **وحسابُ المالك هو ما يقرّر الشكل**: عند ألف رحلةٍ يومياً، اليومَ ≈ ٤ نداءاتِ
 * Directions لكل رحلة → ١٢٠ ألفاً شهرياً؛ والملاحةُ بإعادة توجيهٍ محدودة →
 * ٢٧٠ ألفاً؛ **و«وقتُ وصولٍ يُستفتى من الخادم» → ٨٧٠ ألفاً**. فليست الملاحةُ ما
 * يرفع الفاتورة بل **الاستفتاءُ المتكرّر** — وسبعةُ أضعافِ الفاتورة لرقمٍ يتبدّل
 * بالدقيقة ثمنٌ لا يُدفع.
 *
 * **فالمسافةُ من الخطِّ المخزَّن، والسرعةُ من حركة الكبتن نفسِه.** والخطُّ مجمَّدٌ
 * على الرحلة منذ القبول (البند ٨) — فهو موجودٌ في الجهاز أصلاً، ولا يُطلب.
 *
 * **ولا يُعرض رقمٌ لا يُصدَّق**: قبل أن تُقاس سرعةٌ حقيقيةٌ لا وقتَ يُقال.
 * ورقمٌ مبنيٌّ على سرعةٍ مفترضةٍ يُقرأ وعداً ثم يُخلَف، وهو أسوأُ من صمت.
 */

import type { Coordinates } from "@/api/types";

/** مترٌ لكل درجةِ عرض — تقريبٌ يكفي لمسافاتِ مدينة. */
const METERS_PER_DEGREE = 111_320;

/** أقلُّ سرعةٍ تُصدَّق (م/ث) ≈ ٧ كم/س: أبطأُ منها وقوفٌ في زحامٍ أو إشارة،
 *  وقسمةُ المسافة عليها تُنتج «ساعتان» لطريقٍ مدتُه عشرُ دقائق. */
const MIN_SPEED = 2;
/** وأعلى: ١٢٦ كم/س — قراءةٌ فوقها قفزةُ GPS لا سيارة. */
const MAX_SPEED = 35;

/** نافذةُ القياس: آخرُ ستِّ قراءاتٍ ≈ ١٨ ثانية (دورةُ البثّ ٣ث).
 *
 *  **وأقصرُ منها تجعل الرقمَ يرقص عند كل إشارة، وأطولُ تجعله لا يلحق بمنعطف.** */
const WINDOW = 6;

export function metersBetween(a: Coordinates, b: Coordinates): number {
  const scale = Math.cos((a.lat * Math.PI) / 180);
  const dx = (b.lng - a.lng) * scale;
  const dy = b.lat - a.lat;
  return Math.sqrt(dx * dx + dy * dy) * METERS_PER_DEGREE;
}

/** طولُ ما بقي من الخطّ بالأمتار — **من أقرب نقطةٍ إليه، لا من أوّله**. */
export function remainingMeters(
  points: number[][] | null,
  at: Coordinates | null,
): number | null {
  if (!points || points.length < 2 || !at) return null;

  let nearest = 0;
  let best = Infinity;
  for (let i = 0; i < points.length; i += 1) {
    const distance = metersBetween(at, { lng: points[i][0], lat: points[i][1] });
    if (distance < best) {
      best = distance;
      nearest = i;
    }
  }

  // **ومن موضعه إلى أقرب نقطةٍ يُحسب أيضاً**: كبتنٌ انحرف عن الخطِّ مئتي متر
  // ورقمٌ يتجاهلها يَعِد بوصولٍ أقربَ مما هو
  let total = best;
  for (let i = nearest; i < points.length - 1; i += 1) {
    total += metersBetween(
      { lng: points[i][0], lat: points[i][1] },
      { lng: points[i + 1][0], lat: points[i + 1][1] },
    );
  }
  return total;
}

export type Sample = { at: Coordinates; t: number };

/** سرعةٌ **مقيسةٌ من حركته** بالمتر/ثانية — أو `null` إن لم تكف القراءات.
 *
 * **والقياسُ على طرفَي النافذة لا بمتوسّط الأزواج**: متوسّطُ الأزواج يُدخل ضجيجَ
 * GPS في كل خطوة، وطرفاها يلغيان ذبذبةَ الوقوف والانطلاق داخلها.
 */
export function speedFrom(samples: Sample[]): number | null {
  if (samples.length < 2) return null;
  const window = samples.slice(-WINDOW);
  const first = window[0];
  const last = window[window.length - 1];
  const seconds = (last.t - first.t) / 1000;
  if (seconds <= 0) return null;

  const speed = metersBetween(first.at, last.at) / seconds;
  if (speed < MIN_SPEED || speed > MAX_SPEED) return null;
  return speed;
}

/** دقائقُ الوصول — أو `null` **ولا يُعرض شيءٌ حينها**. */
export function etaMinutes(
  points: number[][] | null,
  at: Coordinates | null,
  samples: Sample[],
): number | null {
  const meters = remainingMeters(points, at);
  const speed = speedFrom(samples);
  if (meters === null || speed === null) return null;
  // **ودقيقةٌ واحدةٌ حدٌّ أدنى**: «٠ دقيقة» تُقرأ عطباً لا وصولاً
  return Math.max(1, Math.round(meters / speed / 60));
}

/** كم يبعد الكبتنُ عن الخطّ بالأمتار — **مقياسُ الانحراف** (البند ١٧-٤). */
export function offRouteMeters(
  points: number[][] | null,
  at: Coordinates | null,
): number | null {
  if (!points || points.length < 2 || !at) return null;
  let best = Infinity;
  for (const point of points) {
    const distance = metersBetween(at, { lng: point[0], lat: point[1] });
    if (distance < best) best = distance;
  }
  return best;
}

/** عتبةُ الانحراف — **ثمانون متراً**: أضيقُ منها يجعل خطأَ GPS في شارعٍ ضيّق
 *  إعادةَ توجيه، وأوسعُ يترك الكبتنَ يقطع شارعاً كاملاً قبل أن يُنبَّه. */
export const OFF_ROUTE_METERS = 80;

/** **وثلاثُ قراءاتٍ متتالية** (≈٩ ثوانٍ) قبل أن يُعلَن انحراف: قفزةُ GPS واحدةٌ
 *  تُنتج نداءً مدفوعاً بلا أن ينحرف أحد، وهي أشيعُ من الانحراف نفسِه. */
export const OFF_ROUTE_STREAK = 3;
