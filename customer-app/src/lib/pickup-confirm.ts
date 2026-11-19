/** **نقطةُ الانطلاق = موقعُ الراكب الحاليّ، بتأكيدٍ لطيف** (أمرُ المالك ٢٠٢٦-١١-١٩، `design/OWNER-2026-11-19-RIDE-TEST-PICKUP.md` الثاني).
 *
 *  **المنطقُ الخالص** — ما يقوله سطرُ الانطلاق في رأس ورقة الطلب، ومتى يُحدَّث الموقعُ عند العودة، ومتى يُلصَق الدبّوسُ بالطريق.
 *  بلا React ولا متصفّح، فيُختبر بـ`node --test` (`tests/pickup-confirm.test.ts`). **ولا نافذةَ في شيءٍ منه**: كلُّه سطرٌ في الورقة.
 */

export interface Point {
  lat: number;
  lng: number;
}

/** **من أين جاء دبّوسُ الانطلاق**: من GPS آليّاً، أم وضعه الراكبُ بيده (دبّوس، بحث، محفوظ، أخير، اقتراح) */
export type PickupSource = "gps" | "manual";

/** حالُ الموقع على الجهاز — `denied` يشمل GPS المطفأ وغيابَ الواجهة كلَّها */
export type LocationState = "unknown" | "granted" | "denied";

/** **فوق هذا تقريبيّ** (نصُّ الأمر: «أكثر من 50 م مثلاً») */
export const WEAK_ACCURACY_M = 50;
/** **أبعدُ ما يُلصَق إليه الدبّوسُ بالطريق** — أبعدُ منه ليس «داخل مبنى» بل مكانٌ آخر، فلا يُنقل الراكبُ إليه صامتاً */
export const SNAP_MAX_M = 60;
/** **أقلُّ من هذا لا يُعدّ نقلاً** — ويوقف الحلقة: المسارُ الجديدُ يبدأ من النقطة نفسِها تقريباً */
export const SNAP_MIN_M = 3;
/** **حركةٌ تستحقّ تحديثَ الانطلاق عند العودة من الخلفيّة** — دونها ارتعاشُ GPS لا انتقال */
export const RESUME_MOVE_M = 25;

/** مسافةٌ بالأمتار بين نقطتين (هافرساين) */
export function metersBetween(a: Point, b: Point): number {
  const r = 6_371_000;
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(h)));
}

export type PickupLineKind = "current" | "approx" | "manual";

export interface PickupLine {
  kind: PickupLineKind;
  /** السطرُ كما يُقرأ — بلا إحداثيّاتٍ أبداً */
  text: string;
  /** **يُبرَز مرّةً** (وهجٌ قصير) — الحاليُّ والتقريبيُّ وحدَهما: ما اختاره الراكبُ بيده لا يُنبَّه عليه */
  pulse: boolean;
  /** **التقريبيُّ يدعو إلى ضبط الدبّوس** — زرُّه «اضبط الدبّوس» بدل «تغيير» */
  adjust: boolean;
}

/** اسمُ المكان كما يُرسم — **والإحداثيّاتُ لا تُرسم أبداً**: بلا اسمٍ يُقال «موقعك الحالي» وحدَه */
export function placeName(address: string | null | undefined): string | null {
  const text = (address ?? "").trim();
  if (!text) return null;
  // «31.95, 35.91» وما شابهه ليس اسماً
  if (/^-?\d+(\.\d+)?\s*[,،]\s*-?\d+(\.\d+)?$/.test(text)) return null;
  return text;
}

/**
 * **سطرُ الانطلاق في رأس ورقة الطلب.** يظهر في الورقة وحدَها — والورقةُ لا تُفتح إلا بعد اختيار الوجهة، فلا شيءَ يسأل عن الانطلاق قبلها.
 *
 * `tr` يُمرَّر من الشاشة (بيتُ الترجمة)، والقوالبُ هنا بنصّها العربيّ.
 */
export function pickupLine(
  input: { source: PickupSource; accuracy_m: number | null; address: string | null | undefined },
  tr: (text: string, values?: Record<string, string>) => string,
): PickupLine {
  const name = placeName(input.address);
  if (input.source === "manual") {
    return {
      kind: "manual",
      text: name ? tr("الانطلاق من: {name}", { name }) : tr("الانطلاق من النقطة المحددة"),
      pulse: false,
      adjust: false,
    };
  }
  if (input.accuracy_m !== null && input.accuracy_m > WEAK_ACCURACY_M) {
    return { kind: "approx", text: tr("موقعك تقريبي، تأكد من نقطة الانطلاق"), pulse: true, adjust: true };
  }
  return {
    kind: "current",
    text: name ? tr("الانطلاق من موقعك الحالي: {name}", { name }) : tr("الانطلاق من موقعك الحالي"),
    pulse: true,
    adjust: false,
  };
}

/** **أيُحدَّث الانطلاقُ عند العودة من الخلفيّة؟** — نعم ما دام من GPS ولا رحلةَ جارية؛ **وما غيّره الراكبُ بيده لا يُمسّ** */
export function refreshOnResume(source: PickupSource, tracking: boolean): boolean {
  return source === "gps" && !tracking;
}

/** **أيُنقل الانطلاقُ إلى الموقع الجديد؟** — حين ابتعد فعلاً، لا لارتعاش GPS */
export function movedEnough(previous: Point | null, next: Point): boolean {
  return previous === null || metersBetween(previous, next) >= RESUME_MOVE_M;
}

/**
 * **الدبّوسُ على أقرب نقطةٍ من الطريق تقف عندها سيّارة، لا داخل مبنى.** ونقطةُ الطريق هي **أوّلُ نقطةٍ في المسار** الذي حسبه محرّكُ
 * التوجيه للتقدير — المحرّكُ يُلصق البدايةَ بأقرب طريقٍ قابلٍ للقيادة، فهي النقطةُ التي سيقف عندها الكبتنُ فعلاً.
 *
 * يعيد النقطةَ الجديدة أو `null` (لا نقل): ما وضعه الراكبُ بيده لا يُنقل، وأقلُّ من `SNAP_MIN_M` ليس نقلاً، وأبعدُ من `SNAP_MAX_M` مكانٌ آخر.
 * و`route` بترتيب GeoJSON: `[lng, lat]`.
 */
export function snapToRoad(source: PickupSource, pickup: Point, route: readonly (readonly number[])[] | null): Point | null {
  if (source !== "gps" || !route || route.length < 2) return null;
  const [lng, lat] = route[0];
  if (typeof lat !== "number" || typeof lng !== "number") return null;
  const start = { lat, lng };
  const distance = metersBetween(pickup, start);
  if (distance < SNAP_MIN_M || distance > SNAP_MAX_M) return null;
  return start;
}
