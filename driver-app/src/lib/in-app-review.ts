/** **تقييمُ المتجر داخل التطبيق** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٦، SPEC §٩٧/٦) — Play In-App Review.
 *
 * **بعد الرحلة المكتملة الثالثة، في لحظةٍ هادئة** (حين يتوقّف الكبتنُ عن الاستقبال — لا فوق عرضٍ قادم)، **ومرّةً كلَّ ١٢٠ يوماً على الأكثر**.
 * **وبلا سؤالٍ قبله** (سياسةُ Google): لا «هل أعجبك التطبيق؟» ولا زرٌّ يَعِد بالنافذة — والمتجرُ وحدَه يقرّر أيُظهرها.
 * **وغلافٌ أقدمُ بلا الملحق لا يُسأل** (`isPluginAvailable`)، والمتصفّحُ كذلك. والعدُّ على الجهاز وحدَه.
 */

import { Capacitor, registerPlugin } from "@capacitor/core";

const plugin = registerPlugin<{ request(): Promise<void> }>("InAppReview");
const RIDES_KEY = "taxo.review.rides";
const ASKED_KEY = "taxo.review.asked";
const MIN_RIDES = 3;
const EVERY_MS = 120 * 86_400_000;

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // تخزينٌ محجوب — لا تقييمَ يُطلب، ولا شيءَ ينكسر
  }
}

function rides(): string[] {
  return (read(RIDES_KEY) ?? "").split(",").filter(Boolean);
}

/** **رحلةٌ اكتملت** — تُعدّ مرّةً لكلِّ رحلة. */
export function noteCompletedRide(rideId: string): void {
  const seen = rides();
  if (seen.includes(rideId)) return;
  write(RIDES_KEY, [...seen, rideId].slice(-10).join(","));
}

/** **اللحظةُ الهادئة** — يُطلب التقييمُ إن بلغ العددُ ومضت المدّة، بعد ثانيةٍ ونصفٍ لا فوراً. */
export function maybeAskForReview(): void {
  if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "android") return;
  if (!Capacitor.isPluginAvailable("InAppReview")) return;
  if (rides().length < MIN_RIDES) return;
  const last = Number(read(ASKED_KEY) ?? "0");
  if (last && Date.now() - last < EVERY_MS) return;
  write(ASKED_KEY, String(Date.now()));
  window.setTimeout(() => void plugin.request().catch(() => undefined), 1500);
}
