/** **وضعُ الإنترنت الضعيف لأفعال الرحلة** (SPEC §١٠٣ B/24، خلف `weak_network_retry`) — «وصلت» و«ابدأ» و«أنهِ» تُعاد حين تعود الشبكة.
 *
 * **ولا يُطبَّق فعلٌ مرّتين**: الانتقالُ نفسُه حارسُ نفسِه في الخادم (قفلُ الصفّ ثمّ فحصُ `الحال ← الهدف`)، فالإعادةُ بعد ردٍّ ضاع تلقى ٤٠٩ —
 * **وهنا يُقرأ الحالُ الحقيقيُّ من الخادم**: بلغ الهدفَ ⇐ نجحت الأولى وضاع ردُّها، وإلا فالخطأُ كما هو. **والمالُ لا يمرّ هنا**: الدفعُ
 * والشراءُ بمفاتيحَ تُعاد هي هي (`newIdempotencyKey`). **ومطفأً يبقى كلُّ شيءٍ كما اليوم**: الخطأُ يُقال فوراً والكبتنُ يعيد الضغط.
 */
import { ApiError } from "@/api/client";
import { getRide } from "@/api/endpoints";
import type { Ride } from "@/api/types";

const WAIT_MS = 120_000;

/** تُحلّ عند عودة الشبكة أو بعد `ms` — أيُّهما أسبق. */
function waitOnline(ms: number): Promise<void> {
  return new Promise((resolve) => {
    const done = () => {
      window.removeEventListener("online", done);
      window.clearTimeout(timer);
      resolve();
    };
    const timer = window.setTimeout(done, ms);
    window.addEventListener("online", done);
  });
}

export async function untilSent(
  send: () => Promise<Ride>,
  options: { enabled: boolean; rideId: string; reached: (ride: Ride) => boolean; onWaiting: (waiting: boolean) => void },
): Promise<Ride> {
  const deadline = Date.now() + WAIT_MS;
  let attempt = 0;
  try {
    for (;;) {
      attempt += 1;
      try {
        return await send();
      } catch (caught) {
        if (!options.enabled || !(caught instanceof ApiError)) throw caught;
        // **٤٠٩ على إعادة**: لعلّ الأولى بلغت وضاع ردُّها — الحكمُ للخادم لا للظنّ
        if (caught.status === 409 && attempt > 1) {
          const now = await getRide(options.rideId);
          if (options.reached(now)) return now;
          throw caught;
        }
        if (caught.status !== 0 || Date.now() > deadline) throw caught;
        options.onWaiting(true);
        await waitOnline(5_000);
      }
    }
  } finally {
    options.onWaiting(false);
  }
}
