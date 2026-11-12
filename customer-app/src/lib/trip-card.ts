/** **«الدفع بالبطاقة» للرحلة** (قرارُ المالك ٢٠٢٦-١١-١٣) — شحنٌ بقيمة الرحلة عبر Whop ثمّ دفعُها من المحفظة.
 *
 * **ما يُحفظ**: معرّفُ الرحلة التي ينتظر دفعُها هذا الشحن — في `localStorage` لأن صفحةَ Whop تُفتح خارج التطبيق. **ولا مبلغَ يُحفظ**:
 * الدفعُ من المحفظة يأخذ ما بقي على الرحلة من الخادم. **وإن أُلغيت الرحلةُ بقي المبلغُ في المحفظة** — لا شيءَ يضيع.
 */

const KEY = "taxo.cardTrip";

export function saveCardTrip(rideId: string): void {
  try {
    localStorage.setItem(KEY, rideId);
  } catch {
    /* تخزينٌ ممنوع — يبقى المبلغُ في المحفظة ويُدفع يدويّاً */
  }
}

export function takeCardTrip(): string | null {
  try {
    const rideId = localStorage.getItem(KEY);
    localStorage.removeItem(KEY);
    return rideId;
  } catch {
    return null;
  }
}

export function peekCardTrip(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
