/** **اقتراحُ الوجهة — الحسابُ الخالص** (SPEC §١٠٣ C/35) — بلا React ولا تخزين، فيُقاس وحدَه.
 *
 * **يُحسب في الهاتف من وجهات الراكب نفسِه** ولا يُرسل منها شيء: وجهةٌ تكرّرت **مرّتين فأكثر** في نافذة ٩٠ دقيقةً حول ساعة الآن
 * (من أيّ يوم)، **والأكثرُ تكراراً ثمّ الأحدث**؛ ولا تُقترح وجهةٌ هو عندها الآن.
 */

export interface DestinationVisit {
  lat: number;
  lng: number;
  address: string;
  /** ميلّي ثانية — لحظةُ الطلب. */
  at: number;
}

export interface DestinationSuggestion {
  lat: number;
  lng: number;
  address: string;
  count: number;
}

/** سقفُ السجلّ في الهاتف — أقدمُه يسقط. */
export const MAX_VISITS = 60;
const WINDOW_MINUTES = 90;
const SAME_PLACE_METERS = 150;
const ALREADY_THERE_METERS = 300;
const MIN_REPEATS = 2;

export function metersApart(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** دقيقةُ اليوم بالتوقيت المحلّيّ للهاتف. */
function minuteOfDay(at: number): number {
  const date = new Date(at);
  return date.getHours() * 60 + date.getMinutes();
}

/** المسافةُ بين دقيقتين على دائرة اليوم — ١١:٣٠ مساءً و١٢:١٠ صباحاً متجاورتان. */
function minutesApart(a: number, b: number): number {
  const gap = Math.abs(a - b) % 1440;
  return Math.min(gap, 1440 - gap);
}

export function appendVisit(history: DestinationVisit[], visit: DestinationVisit): DestinationVisit[] {
  return [...history, visit].slice(-MAX_VISITS);
}

export function suggestDestination(
  history: DestinationVisit[],
  now: number,
  here: { lat: number; lng: number } | null,
): DestinationSuggestion | null {
  const nowMinute = minuteOfDay(now);
  const inWindow = history.filter((visit) => minutesApart(minuteOfDay(visit.at), nowMinute) <= WINDOW_MINUTES);
  const clusters: { head: DestinationVisit; count: number; last: number }[] = [];
  for (const visit of inWindow) {
    const found = clusters.find((cluster) => metersApart(cluster.head, visit) <= SAME_PLACE_METERS);
    if (found) {
      found.count += 1;
      if (visit.at > found.last) {
        found.last = visit.at;
        found.head = visit;
      }
    } else {
      clusters.push({ head: visit, count: 1, last: visit.at });
    }
  }
  const best = clusters
    .filter((cluster) => cluster.count >= MIN_REPEATS)
    .filter((cluster) => !here || metersApart(here, cluster.head) > ALREADY_THERE_METERS)
    .sort((a, b) => b.count - a.count || b.last - a.last)[0];
  if (!best) return null;
  return { lat: best.head.lat, lng: best.head.lng, address: best.head.address, count: best.count };
}
