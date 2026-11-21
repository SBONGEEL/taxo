/** **سياراتُ الرئيسيّة — المنطقُ الخالص** (SPEC §١١١) — بلا React ولا CSS، فيُختبر في `tests/home-cars.test.ts`. */
import type { VehicleCategory } from "@/api/types";

/** خالصة: **سحبةٌ عموديّةٌ تطوي أو تبسط** — `fold` لأسفلَ بعد ٣٦ بكسل، `open` لأعلى، وإلا لا شيء (لمسةٌ عاديّة). */
export function swipeIntent(dy: number, dx: number): "fold" | "open" | null {
  if (Math.abs(dy) < 36 || Math.abs(dy) < Math.abs(dx) * 1.4) return null;
  return dy > 0 ? "fold" : "open";
}

/** خالصة: الفئاتُ المعروضة — بترتيب الدولة، **وخدمةُ النساء لمن عُرضت عليها وحدَها**. */
export function shownCategories(categories: readonly VehicleCategory[], womenAvailable: boolean): VehicleCategory[] {
  return categories.filter((key) => womenAvailable || !String(key).includes("women"));
}
