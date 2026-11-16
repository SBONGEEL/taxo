/** **ارتفاعا ورقة الطلب** (SPEC §١٠٥/١) — نصفُ الشاشة عند الفتح، وملؤها بالسحب. منطقٌ صرفٌ يُختبر بلا متصفّح. */

export type SheetSnap = "half" | "full";

/** **عتبةُ السحب بالبكسل** — ما دونها لمسةٌ تبدّل، وما فوقها سحبٌ يقرّر باتّجاهه */
export const SNAP_PX = 24;

/** `delta` موجبٌ للأعلى. سحبٌ للأعلى يملأ، وللأسفل يعيد النصف؛ وما دون العتبة يُبقي الحال */
export function snapAfterDrag(current: SheetSnap, delta: number): SheetSnap {
  if (delta >= SNAP_PX) return "full";
  if (delta <= -SNAP_PX) return "half";
  return current;
}
