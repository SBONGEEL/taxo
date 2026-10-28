/** **«اشحن مبلغ الرحلة الآن»** (SPEC §٨٨/١، أمرُ المالك ٢٠٢٦-١٠-٢٨) — الطلبُ الذي ينتظر شحنَه، محفوظاً على الجهاز حتى مهلة سعره.
 *
 * **ما يُحفظ**: حمولةُ الطلب كما كانت ستُرسل، ومعرّفُ السعر المثبَّت، ونهايةُ مهلته، والأجرةُ المعروضةُ للمقارنة وحدَها. **ولا مبلغَ
 * يُرسل من هنا**: الخلفيةُ تأخذ السعرَ المحفوظ بالمعرّف إن طابقت التفاصيلُ، وإلا سعّرت من جديد.
 *
 * **في `localStorage` لا الذاكرة**: صفحةُ الوسيط تُفتح خارج التطبيق، والنظامُ قد يُغلقه — فيعود الطلبُ حين يعود. **وما انقضت مهلتُه
 * يُنسى عند قراءته.**
 */

import type { requestRide } from "@/api/endpoints";

export type RideRequestPayload = Parameters<typeof requestRide>[0];

export interface PendingRide {
  payload: RideRequestPayload;
  quoteId: string;
  /** نهايةُ مهلة السعر — ISO */
  until: string;
  /** الأجرةُ المعروضة — للمقارنة بالرصيد وحدَها */
  fare: string;
}

const KEY = "taxo.rideTopup";

export function savePendingRide(pending: PendingRide): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(pending));
  } catch {
    /* تخزينٌ ممنوع — يبقى الشحنُ ويُطلب يدويّاً */
  }
}

export function clearPendingRide(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* لا شيء */
  }
}

/** **الطلبُ المنتظر إن بقيت مهلتُه** — وما انقضت يُمحى. */
export function readPendingRide(now: number = Date.now()): PendingRide | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as PendingRide;
    if (!parsed.quoteId || !parsed.until || Date.parse(parsed.until) <= now) {
      clearPendingRide();
      return null;
    }
    return parsed;
  } catch {
    clearPendingRide();
    return null;
  }
}
