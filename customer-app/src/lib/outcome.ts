/** **خاتمةُ الرحلة بعد الدفع — قراراتٌ نقيّةٌ في بيتٍ واحد** (بلاغُ المالك ٢٠٢٦-١٠-١٦، SPEC §٧٦-س).
 *
 * **العطبُ الذي أنشأها، مقيساً على الإنتاج**: بعد دفعٍ كامل، الرجوعُ إلى الرئيسية **يعيد نافذةَ «الانتقال إلى الدفع»**، و«لاحقاً» **يُخفي شريطَ
 * التنقّل**. وعلّتان: «طُويت» كانت حالاً داخل الرئيسية **تُنسى حين تُفكّ** (الذهابُ إلى الدفع يفكّها) — والنافذةُ لا تسأل الخادمَ أدُفعت؛ والشريطُ
 * كان يُخفى **ما دامت أيُّ رحلةٍ معروضة** ولو انتهت — و«لاحقاً» يطوي النافذةَ ويُبقي الرحلةَ معروضة.
 *
 * **فالقراراتُ هنا بلا React** — تُقاس بـ`scripts/test-outcome.mjs` في البناء نفسِه:
 * - النافذةُ تُفتح **لما يقول الخادمُ الآن إنه مستحقّ** (`settlement === "due"`) وحدَه؛
 * - وما طُوي أو دُفع **يُذكر خارج الرئيسية** (`sessionStorage`) فلا يعود بعودتها؛
 * - والشريطُ يُخفى **لرحلةٍ جاريةٍ أو لورقةٍ مفتوحةٍ** وحدَهما، لا لرحلةٍ انتهت.
 */

import type { RidePayments, RideStatus } from "@/api/types";

/** حالاتُ الرحلة التي لا تعود منها — **مرآةُ `TERMINAL_STATUSES` في `lib/ride.tsx`** */
export const FINISHED_STATUSES: readonly RideStatus[] = [
  "completed",
  "cancelled_by_rider",
  "cancelled_by_driver",
  "no_driver_found",
];

/** **أبقي على الراكب شيءٌ يدفعه الآن؟** — من جواب الخادم وحدَه، لا من حالٍ في الشاشة. و`awaiting` (دفعةٌ تنتظر تأكيد الكبتن) **ليس مستحقّاً**:
 *  اختار طريقتَه، ونافذةٌ تسأله ثانيةً تفتح دفعةً ثانية. */
export function paymentStillDue(payments: Pick<RidePayments, "settlement"> | null): boolean {
  return payments?.settlement === "due";
}

export type OutcomeDecision = "wait" | "show" | "forget";

/** **ما يُفعل بخاتمة رحلةٍ معروضة**:
 * - طُويت أو دُفعت قبلُ ⇒ `forget` (تُنسى ويعود الشريط)؛
 * - أُلغيت أو لم يُوجد كبتن ⇒ `show` (خبرٌ يُقرأ مرّة ثمّ يُطوى)؛
 * - اكتملت ولم يُسأل الخادمُ بعد ⇒ `wait` (لا ومضةَ نافذةٍ ثمّ اختفاء)؛
 * - اكتملت والخادمُ يقول «مستحقّ» ⇒ `show`، وإلا ⇒ `forget`؛
 * - **وتعذّر السؤال** (`null`) ⇒ `show` — الدفعُ لا يُخفى بانقطاع شبكة، وشاشةُ الدفع نفسُها تسأل ثانيةً.
 */
export function outcomeDecision(
  status: RideStatus,
  closed: boolean,
  payments: Pick<RidePayments, "settlement"> | null | undefined,
): OutcomeDecision {
  if (closed) return "forget";
  if (status !== "completed") return "show";
  if (payments === undefined) return "wait";
  if (payments === null) return "show";
  return paymentStillDue(payments) ? "show" : "forget";
}

/** **أيُخفى شريطُ التنقّل؟** — لرحلةٍ جاريةٍ (ورقةُ التتبّع تحتلّ مكانه) أو لشاشةٍ تقول إنها تغطّيه (`lib/navCover`) **وحدَهما**.
 *  **ورحلةٌ انتهت لا تُخفيه**: ورقةُ خاتمتها تغطّيه ما دامت مفتوحةً، وتكشفه حين تُطوى. */
export function navBarHidden(
  rideStatus: RideStatus | null,
  covered: boolean,
  activeStatuses: readonly RideStatus[],
): boolean {
  return covered || (rideStatus !== null && activeStatuses.includes(rideStatus));
}

// ── ما طُوي أو دُفع — يُذكر خارج الرئيسية ──────────────────────────────────────────────────

const KEY = "taxo.outcome.closed";
/** سقفٌ لما يُذكر — رحلاتُ جلسةٍ لا سجلُّ عمر */
const MAX = 50;

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function store(): KeyValueStore | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

export function closedOutcomes(source: KeyValueStore | null = store()): string[] {
  try {
    const raw = source?.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(list) ? list.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function isOutcomeClosed(rideId: string, source: KeyValueStore | null = store()): boolean {
  return closedOutcomes(source).includes(rideId);
}

export function rememberClosedOutcome(rideId: string, source: KeyValueStore | null = store()): void {
  try {
    const next = [rideId, ...closedOutcomes(source).filter((x) => x !== rideId)].slice(0, MAX);
    source?.setItem(KEY, JSON.stringify(next));
  } catch {
    // **بلا تخزين** (نافذةٌ خاصّة) — يبقى ما طُوي في ذاكرة السياق (`lib/ride.tsx`) ما دام التطبيقُ مفتوحاً
  }
}

// ── العودةُ إلى الرئيسية بتاريخٍ نظيف ─────────────────────────────────────────────────────────

/** **نقطةُ العودة**: موضعُ الرئيسية في تاريخ الملاح لحظةَ الذهاب إلى الدفع — فـ«الرئيسية» بعد الدفع **رجوعٌ إليها** لا دفعٌ جديدٌ فوق
 *  شاشة الدفع (ذاك يُبقي الدفعَ وراءها فيعود إليه زرُّ الرجوع). */
let returnIdx: number | null = null;

export function markReturnPoint(idx: number | null): void {
  returnIdx = idx;
}

/** **كم خطوةً إلى الوراء حتى الرئيسية؟** — سالبٌ إن كانت نقطةُ العودة وراءنا، و`null` إن لم تكن (دخولٌ برابطٍ مباشر) فتُفتح الرئيسيةُ
 *  بـ`replace`. */
export function stepsBackToHome(currentIdx: number | null, markedIdx: number | null = returnIdx): number | null {
  if (currentIdx === null || markedIdx === null || markedIdx >= currentIdx) return null;
  return markedIdx - currentIdx;
}

export function clearReturnPoint(): void {
  returnIdx = null;
}
