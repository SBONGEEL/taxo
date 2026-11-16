/** **اهتزازٌ خفيفٌ احترافيّ** (SPEC §١٠٣ المرحلة A/11) — **منسوخٌ بايتاً في التطبيقين** (`check:permissions-plugin`)، خلف `haptics`.
 *
 * نقرةٌ واحدةٌ قصيرة (٨ ملّي ثانية) عند لمس الزرِّ الرئيسيّ (`.t2-btn-primary` و`[data-haptic]`) — **لا نمطَ طويلاً ولا تكرار**.
 * يستمع على `document` مرّةً، فلا يُلمس زرٌّ واحد. **وصامتٌ حيث لا `navigator.vibrate`** (سفاري، والغلافُ بلا إذن `VIBRATE`) —
 * لا يُدّعى اهتزازٌ لا يقع. ومطفأً لدولته لا مستمعَ أصلاً.
 */
import { useEffect } from "react";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";

export const HAPTIC_SELECTOR = ".t2-btn-primary, [data-haptic]";
export const HAPTIC_MS = 8;

/** خالصٌ ومختبَر: أيُّ عنصرٍ يستحقّ النقرة — الزرُّ الرئيسيُّ غيرُ المعطَّل وحدَه */
export function wantsHaptic(target: Element | null): boolean {
  const button = target?.closest?.(HAPTIC_SELECTOR) ?? null;
  if (!button) return false;
  return !(button as HTMLButtonElement).disabled && button.getAttribute("aria-disabled") !== "true";
}

export function useHaptics(country: CountryCode | undefined): void {
  const on = useFeature(country, "haptics");
  useEffect(() => {
    if (!on || typeof navigator === "undefined" || typeof navigator.vibrate !== "function") return;
    const onDown = (event: PointerEvent) => {
      if (wantsHaptic(event.target as Element | null)) navigator.vibrate(HAPTIC_MS);
    };
    document.addEventListener("pointerdown", onDown, { passive: true });
    return () => document.removeEventListener("pointerdown", onDown);
  }, [on]);
}
