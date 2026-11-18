/** **النصُّ الكبير والتباينُ العالي** (SPEC §١٠٣ C/40، خلف `display_accessibility`) — اختيارٌ على الجهاز لا الحساب، كالسِمة.
 *
 * - **النصُّ الكبير**: `TextZoomPlugin` يكبّر نصَّ الواجهة ١٣٠٪ (النصُّ وحدَه، لا الصورُ ولا الخريطة). **وغلافٌ أقدمُ بلا الملحق لا
 *   صفَّ له** — فلا مفتاحَ يُحفظ ولا يفعل شيئاً.
 * - **التباينُ العالي**: `html.hc` يُغمّق الرموزَ الباهتة (`--t2-muted` · `--t2-faint` · `--t2-line`) في الفاتح ويُفتّحها في الداكن.
 *
 * **ومطفأً في السوق يعود كلُّ شيءٍ كما اليوم** ولو بقي الاختيارُ محفوظاً. **نسخةُ التطبيق الآخر حرفاً.**
 */
import { useEffect, useSyncExternalStore } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { useFeature } from "@/lib/config";
import type { CountryCode } from "@/api/types";

export const DISPLAY_FLAG = "display_accessibility";
const BIG_KEY = "taxo.display.big";
const CONTRAST_KEY = "taxo.display.contrast";
const BIG_PERCENT = 130;

const zoom = registerPlugin<{ set(options: { percent: number }): Promise<void> }>("TextZoom");

export function bigTextAvailable(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("TextZoom");
}

function read(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

const listeners = new Set<() => void>();
let snapshot = { big: read(BIG_KEY), contrast: read(CONTRAST_KEY) };

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setDisplayChoice(which: "big" | "contrast", on: boolean): void {
  try {
    localStorage.setItem(which === "big" ? BIG_KEY : CONTRAST_KEY, on ? "1" : "0");
  } catch {
    // تخزينٌ محجوب — يبقى للجلسة وحدَها
  }
  snapshot = { ...snapshot, [which]: on };
  listeners.forEach((listener) => listener());
}

export function useDisplayChoices() {
  return useSyncExternalStore(subscribe, () => snapshot);
}

/** يُطبَّق في جذر التطبيق: الاختيارُ المحفوظ **ومفتاحُ السوق معاً**. */
export function useDisplayPrefs(country: CountryCode | undefined): void {
  const on = useFeature(country, DISPLAY_FLAG);
  const { big, contrast } = useDisplayChoices();
  const bigOn = on && big;
  const contrastOn = on && contrast;
  useEffect(() => {
    document.documentElement.classList.toggle("hc", contrastOn);
  }, [contrastOn]);
  useEffect(() => {
    if (!bigTextAvailable()) return;
    void zoom.set({ percent: bigOn ? BIG_PERCENT : 100 }).catch(() => undefined);
  }, [bigOn]);
}
