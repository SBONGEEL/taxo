/** **أيُّ مجموعة أيقوناتٍ تُرسم؟** (SPEC §١٠٥/٣) — الجديدةُ حين يشتعل `icons_v2` لسوق المستخدم، **والقديمةُ (الخطّ) كما هي حرفاً حين يُطفأ**.
 *
 * **مخزنٌ لا سياق**: `Icon` يُستعمل في مئات المواضع ومنها ما لا يقع تحت مزوّدٍ واحد (النوافذُ العائمة)، والمخزنُ يبلغها كلَّها بلا تمرير.
 * ويضبطه في كلِّ تطبيقٍ مكوّنٌ صغيرٌ عند الجذر يقرأ المفتاح (`IconSetSwitch`).
 *
 * **والحركةُ تُطفأ وحدَها مرّتين**: «تقليلُ الحركة» من النظام (`prefers-reduced-motion` في CSS)، **والهاتفُ الضعيف** — نواتٌ ≤ ٤ أو
 * ذاكرةٌ ≤ ٢ جيجابايت ⇐ `html.t2-calm` فتُرسم الأيقونةُ ساكنة. **ولا تؤخّر لمسة**: الحركةُ CSS على `transform`/`opacity` وحدَهما،
 * والنقرُ يعمل قبلها وبدونها.
 */
import { useSyncExternalStore } from "react";

let v2 = false;
const listeners = new Set<() => void>();

function weakDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const cores = navigator.hardwareConcurrency ?? 8;
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return cores <= 4 || memory <= 2;
}

export function setIconSetV2(on: boolean): void {
  if (typeof document !== "undefined") {
    const root = document.documentElement;
    root.classList.toggle("t2-glyphs", on);
    root.classList.toggle("t2-calm", on && weakDevice());
  }
  if (on === v2) return;
  v2 = on;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useIconSetV2(): boolean {
  return useSyncExternalStore(subscribe, () => v2);
}

/** **أتتحرّك الزينة؟** — المجموعةُ الجديدة، ولا «تقليلَ حركة»، ولا هاتفاً ضعيفاً. */
export function motionAllowed(): boolean {
  if (!v2 || typeof window === "undefined") return false;
  if (document.documentElement.classList.contains("t2-calm")) return false;
  return !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** مفتاحُ المجموعة الجديدة — **مطفأٌ لكلِّ دولة** حتى يوافق المالكُ على اللوحة والتسجيل */
export const ICONS_V2_FLAG = "icons_v2";
