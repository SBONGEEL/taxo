/** **قائمةُ البحث عن الأماكن** (أمرُ المالك ٢٠٢٦-١١-١٦ الثالث، SPEC §١٠٤) — ما يُحسب للعرض وحدَه: تظليلُ الحروف المكتوبة بمطابقةٍ
 *  عربيّةٍ متسامحة، والمسافةُ، وأيقونةُ الصنف، وما يحفظه الجهازُ **لكلِّ مستخدمٍ وحدَه** (آخرُ ما اختاره، وما أخفاه من «الأخيرة»).
 *
 *  **ولا يمسّ نقطةً ولا مساراً**: النقطةُ المختارةُ هي إحداثيّاتُ النتيجة كما وصلت، والأجرةُ تُحسب في الخلفيّة كما كانت.
 *  وخالٍ من React ومن DOM فيُختبر بـ`node --test` (`tests/place-search.test.ts`).
 */

/** **مفتاحُ القائمة الجديدة** لكلِّ دولة — مطفأٌ حتى يشعله المالكُ من اللوحة */
export const SEARCH_V2_FLAG = "places_search_v2";

/** المهلةُ بين آخر حرفٍ والسؤال (§١٠٤/٤) — قصيرةٌ: الخادمُ يجيب في ١٠٠–٣٠٠ م.ث، والطلبُ الأقدمُ يُلغى */
export const SEARCH_DEBOUNCE_MS = 150;
/** **من الحرف الثاني** (§١٠٤/٤) */
export const MIN_QUERY = 2;

const DIACRITICS = /[ً-ٰٟـ]/;
const FOLD: Record<string, string> = {
  "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
  "é": "e", "è": "e", "ê": "e", "ë": "e", "à": "a", "â": "a", "ä": "a", "î": "i", "ï": "i", "ô": "o", "ö": "o", "ù": "u",
  "û": "u", "ü": "u", "ç": "c",
};

/** **حرفٌ مطويٌّ لكلِّ حرفٍ أصليّ** — مع موضعه في الأصل، فيُظلَّل الأصلُ لا المطويّ. الحركاتُ والتطويلُ تسقط، والمسافاتُ المتتاليةُ واحدة */
function folded(text: string): { chars: string; at: number[] } {
  let chars = "";
  const at: number[] = [];
  for (let i = 0; i < text.length; i += 1) {
    const raw = text[i];
    if (DIACRITICS.test(raw)) continue;
    const lower = raw.toLowerCase();
    const ch = FOLD[lower] ?? lower;
    if (/\s/.test(ch)) {
      if (chars.endsWith(" ") || chars.length === 0) continue;
      chars += " ";
    } else {
      chars += ch;
    }
    at.push(i);
  }
  return { chars, at };
}

/** **النصُّ مطويّاً** — أ/إ/آ ← ا، ة ← ه، ى ← ي، بلا حركات، وحروفٌ لاتينيّةٌ صغيرةٌ بلا علامات (Algér ← alger) */
export function foldText(text: string): string {
  return folded(text).chars.trim();
}

/** **أين تقع الحروفُ المكتوبةُ في الاسم** (§١٠٤/١١) — `[بداية، نهاية)` في الاسم الأصليّ، أو `null`. وبلا «ال» إن لم تُوجد بها:
 *  «الداخلية» تُظلَّل في «دوار الداخلية»، و«مكة» في «المكة مول» لا يجدها حرفاً فتُجرَّب «مكة» */
export function highlightRange(name: string, query: string): [number, number] | null {
  const target = folded(name);
  const tries = [foldText(query)];
  const bare = tries[0].replace(/(^|\s)ال(?=\S)/g, "$1").trim();
  if (bare && bare !== tries[0]) tries.push(bare);
  for (const needle of tries) {
    if (needle.length < MIN_QUERY) continue;
    const index = target.chars.indexOf(needle);
    if (index >= 0) {
      const start = target.at[index];
      const end = target.at[index + needle.length - 1] + 1;
      return [start, end];
    }
  }
  return null;
}

/** **المسافةُ بجانب النتيجة** (§١٠٤/١١) — بالأرقام اللاتينيّة: «850 م» تحت الكيلومتر، و«3.2 كم» فوقه، و«120 كم» بلا كسرٍ فوق المئة */
export function distanceLabel(meters: number | null | undefined): string | null {
  if (meters === null || meters === undefined || !Number.isFinite(meters) || meters < 0) return null;
  if (meters < 1000) return `${Math.max(10, Math.round(meters / 10) * 10)} م`;
  const km = meters / 1000;
  return km >= 100 ? `${Math.round(km)} كم` : `${km.toFixed(1)} كم`;
}

/** **أيقونةُ الصنف** — من `category` في جواب البحث؛ وصنفٌ لا تعرفه هذه القائمةُ أيقونةٌ عامّة لا فراغ */
const CATEGORY_ICON: Record<string, string> = {
  airport: "flight_takeoff", mall: "shopping_bag", hospital: "local_hospital", university: "school", school: "school",
  mosque: "mosque", restaurant: "restaurant", hotel: "hotel", pharmacy: "local_pharmacy", bank: "account_balance",
  fuel: "local_gas_station", park: "park", roundabout: "roundabout_right", street: "route", city: "location_city",
  district: "apartment", saved: "star", recent: "schedule", place: "location_on",
  // أصنافُ أماكن المالك (`MapPlaceCategory`) في «أماكن مشهورة قريبة»
  market: "storefront", shop: "storefront", clinic: "local_hospital", landmark: "tour", government: "account_balance",
  station: "directions_bus", neighborhood: "apartment", church: "location_on", other: "location_on",
};

export function categoryIcon(category: string | null | undefined): string {
  return (category && CATEGORY_ICON[category]) || "location_on";
}

/** **السؤالُ الأحدثُ وحدَه يُعرض** (§١٠٤/٤ و١٧) — جوابٌ أقدمُ يصل بعد أحدثَ منه يُرمى، ولو لم يُلغَ طلبُه (شبكةٌ بطيئة) */
export function latestOnly() {
  let current = 0;
  return {
    next(): number {
      current += 1;
      return current;
    },
    isCurrent(ticket: number): boolean {
      return ticket === current;
    },
  };
}

export interface StoredPick {
  name: string;
  address: string;
  lat: number;
  lng: number;
  category?: string | null;
}

/** **ما يحفظه الجهازُ لكلِّ مستخدمٍ وحدَه** (§١٠٤ الشروط) — المفتاحُ يحمل معرّفَ المستخدم، فحسابٌ آخرُ على الهاتف نفسِه لا يرى شيئاً منه */
export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const RECENT_PICKS = 6;
const pickKey = (userId: string) => `taxo:search:picks:${userId}`;
const hiddenKey = (userId: string) => `taxo:search:hidden:${userId}`;

function readList<T>(store: KeyValueStore | null, key: string): T[] {
  if (!store) return [];
  try {
    const value = JSON.parse(store.getItem(key) ?? "[]");
    return Array.isArray(value) ? (value as T[]) : [];
  } catch {
    return [];
  }
}

function writeList(store: KeyValueStore | null, key: string, list: unknown[]): void {
  if (!store) return;
  try {
    store.setItem(key, JSON.stringify(list));
  } catch {
    // تخزينٌ ممتلئٌ أو ممنوع — القائمةُ تعمل بلا «الأخيرة»
  }
}

/** نقطتان في ~٥٥ متراً مكانٌ واحد */
export function samePoint(a: { lat: number; lng: number }, b: { lat: number; lng: number }): boolean {
  return Math.abs(a.lat - b.lat) < 0.0005 && Math.abs(a.lng - b.lng) < 0.0005;
}

export function recentPicks(store: KeyValueStore | null, userId: string | null | undefined): StoredPick[] {
  return userId ? readList<StoredPick>(store, pickKey(userId)).slice(0, RECENT_PICKS) : [];
}

/** **يُحفظ ما اختاره من البحث** أوّلاً، والمكرَّرُ يصعد ولا يتكرّر */
export function rememberPick(store: KeyValueStore | null, userId: string | null | undefined, pick: StoredPick): void {
  if (!userId) return;
  const rest = recentPicks(store, userId).filter((item) => !samePoint(item, pick));
  writeList(store, pickKey(userId), [pick, ...rest].slice(0, RECENT_PICKS));
  // اختيارُه من جديدٍ يعيده إلى القائمة إن كان أخفاه
  writeList(store, hiddenKey(userId), hiddenRecents(store, userId).filter((key) => key !== pointKey(pick)));
}

export function pointKey(point: { lat: number; lng: number }): string {
  return `${point.lat.toFixed(4)},${point.lng.toFixed(4)}`;
}

export function hiddenRecents(store: KeyValueStore | null, userId: string | null | undefined): string[] {
  return userId ? readList<string>(store, hiddenKey(userId)) : [];
}

/** **«✕» على صفٍّ من «الأخيرة»** — يُخفى من القائمة عند هذا المستخدم وحدَه، **ولا تُمسّ رحلةٌ ولا سجلّ** */
export function forgetRecent(store: KeyValueStore | null, userId: string | null | undefined, point: { lat: number; lng: number }): void {
  if (!userId) return;
  writeList(store, pickKey(userId), recentPicks(store, userId).filter((item) => !samePoint(item, point)));
  const hidden = hiddenRecents(store, userId);
  const key = pointKey(point);
  if (!hidden.includes(key)) writeList(store, hiddenKey(userId), [...hidden, key].slice(-200));
}

/** **جهازُ المتصفّح إن وُجد** — وفي نافذةٍ خاصّةٍ أو بيئةٍ بلا تخزين: `null`، والقائمةُ تعمل بلا «الأخيرة» */
export function browserStore(): KeyValueStore | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}
