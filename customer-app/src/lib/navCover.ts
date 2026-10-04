/** **شاشةٌ تغطّي شريطَ التبويب وهي ليست مساراً** — أطوارُ الطلب في الرئيسية (TAXO 2.0 «R06»).
 *
 * `App.tsx::NavBar` يقرّر الشريطَ **بالمسار** (`showsNav` · `T2_COVERING`)، وأطوارُ الطلب **حالٌ داخل `/`** لا مسار:
 * الدبوسُ وورقةُ التأكيد كلاهما على `/`. **فالشاشةُ تقول ما تغطّيه وهي مركّبة، وتنزعه حين تُفكّ** — فلا يبقى الشريطُ
 * مخفيّاً بعد أن تغادر، ولا يحتاج `NavBar` أن يعرف أطوارَ الرئيسية.
 */

import { useEffect, useSyncExternalStore } from "react";

let covers = 0;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function bump(delta: number) {
  covers += delta;
  for (const listener of listeners) listener();
}

/** أيغطّي شيءٌ الشريطَ الآن؟ */
export function useNavCovered(): boolean {
  return useSyncExternalStore(subscribe, () => covers > 0);
}

/** **تغطيةٌ ما دام الشرطُ قائماً والمكوّنُ مركّباً** — عدّادٌ لا علَم، فغطاءان لا يكشف أحدُهما ما يغطّيه الآخر. */
export function useCoverNav(active: boolean) {
  useEffect(() => {
    if (!active) return;
    bump(1);
    return () => bump(-1);
  }, [active]);
}
