/** **«الأكثرُ استعمالاً أوّلاً»** في خدمات الرئيسيّة (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-د).
 *
 *  **العددُ من هذا الهاتف وحدَه** — كم مرّةً فتح الكبتنُ كلَّ بلاطة؛ لا يُرسل إلى أحد ولا يُخمَّن. **والتعادلُ بترتيب اللوحة** (والصفرُ
 *  للجميع أوّلَ يوم = ترتيبُ اللوحة حرفاً). **والتخزينُ قد يغيب** (نافذةٌ خاصّة، بياناتٌ ممسوحة) فيُقرأ صفراً ولا يسقط شيء. */
import type { ServiceTile } from "@/api/types";

const STORE_KEY = "taxo.service-usage.v1";

export type UsageCounts = Readonly<Record<string, number>>;

/** عددُ بلاطات الرئيسية — **صفّان من ثلاث** كما رُسمت C04. */
export const HOME_TILES = 6;

/** **بلاطةٌ تُفتح** — مشتعلةٌ ولها مقصد؛ و«قريباً» (مفتاحُ السوق مطفأٌ لدولته، `services/storefront.py`) لا تُفتح.
 *  **مرآةُ `tileOpenable` في `components/home/ServiceTiles.tsx`** — تلك منسوخةٌ بايتاً بين التطبيقين (`check:storefront-card`) فلا
 *  تستورد من بيتٍ في أحدهما؛ وهذه تُختبر بلا متصفّح. **والقاعدةُ سطرٌ واحد**: إن تغيّرت هناك تتغيّر هنا. */
export function tileOpenable(tile: Pick<ServiceTile, "status" | "destination">): boolean {
  return tile.status === "active" && tile.destination !== null;
}

/** **ستُّ الرئيسية** (§١٠٩-د): ما يُفتح وحدَه — **وما أُطفئ لدولته لا يظهر** — والأكثرُ استعمالاً أوّلاً، ثمّ ترتيبُ اللوحة. */
export function homeTiles<T extends Pick<ServiceTile, "id" | "status" | "destination">>(tiles: readonly T[], counts: UsageCounts): T[] {
  return byUsage(tiles.filter(tileOpenable), counts).slice(0, HOME_TILES);
}

/** **الترتيبُ الخالص** — يُختبر بلا متصفّح */
export function byUsage<T extends Pick<ServiceTile, "id">>(tiles: readonly T[], counts: UsageCounts): T[] {
  return tiles
    .map((tile, index) => ({ tile, index, uses: counts[tile.id] ?? 0 }))
    .sort((a, b) => b.uses - a.uses || a.index - b.index)
    .map((row) => row.tile);
}

export function readUsage(): UsageCounts {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    if (!parsed || typeof parsed !== "object") return {};
    const out: Record<string, number> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "number" && Number.isFinite(value) && value > 0) out[key] = value;
    }
    return out;
  } catch {
    return {};
  }
}

export function recordUse(tileId: string): void {
  try {
    const counts = { ...readUsage() };
    counts[tileId] = (counts[tileId] ?? 0) + 1;
    localStorage.setItem(STORE_KEY, JSON.stringify(counts));
  } catch {
    // **بلا تخزين** — يبقى ترتيبُ اللوحة، ولا يسقط الفتح
  }
}
