/** **مكالمةُ الرحلة عند نظام أندرويد — الحسابُ الخالص** (SPEC §١٠٣ B/27) — بلا React ولا إضافة، فيُقاس وحدَه.
 *
 * من طورٍ إلى طور: ما يُقال للنظام. **مرّةً لكلِّ مكالمة** (`started`)، والصادرةُ تُعلَن عند «يرنّ» لا قبله — قبلها قد يسقط إذنُ
 * الميكروفون أو تنبيهُ التسجيل، فلا تظهر في السيّارة مكالمةٌ لم تبدأ. */

export type BridgeStep =
  | { kind: "outgoing" }
  | { kind: "incoming" }
  | { kind: "active" }
  | { kind: "end"; reason: "missed" | "error" | "local" }
  | null;

const OVER = new Set(["broken", "unanswered", "tripover", "hungup"]);

export function bridgeStep(started: boolean, prev: string | null, next: string | null, outgoing: boolean): BridgeStep {
  if (!started) {
    if (next === "dialing" && outgoing) return { kind: "outgoing" };
    if (next === "incoming" && !outgoing) return { kind: "incoming" };
    return null;
  }
  if (next === null || OVER.has(next)) {
    return { kind: "end", reason: next === "unanswered" ? "missed" : next === "broken" ? "error" : "local" };
  }
  if (next === "talking" && prev !== "talking") return { kind: "active" };
  return null;
}
