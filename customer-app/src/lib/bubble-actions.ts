/** **أفعالُ فقاعة الراكب وودجته** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — تصل من الطرف الأصليّ وتُسلَّم **للشاشة التي تملك الفعل**:
 * الإلغاءُ لورقة الإلغاء نفسِها (بقاعدتها ورسمها)، والمشاركةُ لزرّها، وتعديلُ الوجهة لبابه بتأكيد السعر، والطوارئُ لورقتها.
 * **ولا فعلَ يطلب رحلة**: «البيت» و«العمل» والأخيرةُ تفتح ورقةَ الطلب للتأكيد.
 *
 * والفعلُ قد يصل قبل أن تُرسم شاشتُه (إقلاعٌ بارد) — فيُحفظ **ثوانيَ معدودة** ثم يسقط، كي لا يُنفَّذ إلغاءٌ قديمٌ بعد دقائق.
 */
import { useEffect, useRef } from "react";

export const BUBBLE_ACTIONS = [
  "cancel_ride",
  "share_ride",
  "edit_destination",
  "emergency",
  "where_to",
  "recent_0",
  "recent_1",
  "recent_2",
] as const;
export type BubbleAction = (typeof BUBBLE_ACTIONS)[number];

const KEEP_MS = 8_000;
let pending: { action: BubbleAction; at: number } | null = null;
const listeners = new Map<BubbleAction, Set<() => void>>();

/** خالص: فعلٌ معروفٌ أو `null`. */
export function bubbleAction(raw: string | null | undefined): BubbleAction | null {
  return (BUBBLE_ACTIONS as readonly string[]).includes(raw ?? "") ? (raw as BubbleAction) : null;
}

export function fireBubbleAction(action: BubbleAction, now = Date.now()): void {
  const set = listeners.get(action);
  if (set && set.size > 0) {
    set.forEach((run) => run());
    pending = null;
    return;
  }
  pending = { action, at: now };
}

/** يسلّم الفعلَ لمن يملكه — **والمعلّقُ حديثاً يُسلَّم لحظةَ الرسم**. */
export function useBubbleAction(action: BubbleAction, handler: () => void, enabled = true): void {
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const run = () => latest.current();
    const set = listeners.get(action) ?? new Set();
    set.add(run);
    listeners.set(action, set);
    if (pending && pending.action === action) {
      const fresh = Date.now() - pending.at <= KEEP_MS;
      pending = null;
      if (fresh) run();
    }
    return () => void set.delete(run);
  }, [action, enabled]);
}
