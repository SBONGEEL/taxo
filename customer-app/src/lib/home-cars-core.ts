/** **رئيسيّةُ الراكب الجديدة — المنطقُ الخالص** (SPEC §١١١، `design/OWNER-2026-11-21-HOME-REDESIGN.md`) — بلا React ولا CSS،
 *  فيُختبر في `tests/home-cars.test.ts`. */
import type { VehicleCategory } from "@/api/types";

/** خالصة: الفئاتُ المعروضة — بترتيب الدولة، **وخدمةُ النساء لمن عُرضت عليها وحدَها**. */
export function shownCategories(categories: readonly VehicleCategory[], womenAvailable: boolean): VehicleCategory[] {
  return categories.filter((key) => womenAvailable || !String(key).includes("women"));
}

export interface ChipPlace {
  id: string;
  name: string;
  lat: number;
  lng: number;
}

export interface QuickChip {
  kind: "home" | "work" | "airport" | "last";
  /** ما يُكتب على الشريحة: «المنزل» و«العمل» و«المطار»، **والوجهةُ الأخيرةُ باسمها كما وصل**. */
  label: string;
  place: ChipPlace;
}

/** خالصة: **أماكنُ حقيقيّةٌ وحدَها** — المنزلُ والعملُ من أماكنه المحفوظة (`icon`)، والمطارُ الذي حسبه `nearestAirport` من مطارات السوق،
 *  والوجهةُ الأخيرةُ من رحلاته. **وما لا وجودَ له لا شريحةَ له** — لا «أضف منزلك» يُخترع مكاناً، والمكانُ الواحدُ لا يُكرَّر بشريحتين
 *  (وجهتُه الأخيرةُ منزلُه ⇐ «المنزل» وحدَها). */
export function quickChips(input: {
  home: ChipPlace | null;
  work: ChipPlace | null;
  airport: ChipPlace | null;
  last: ChipPlace | null;
  labels: { home: string; work: string; airport: string };
}): QuickChip[] {
  const out: QuickChip[] = [];
  const near = (a: ChipPlace, b: ChipPlace) => Math.abs(a.lat - b.lat) < 0.0005 && Math.abs(a.lng - b.lng) < 0.0005;
  const push = (kind: QuickChip["kind"], label: string, place: ChipPlace | null) => {
    if (!place || !label.trim()) return;
    if (out.some((chip) => chip.place.id === place.id || near(chip.place, place))) return;
    out.push({ kind, label, place });
  };
  push("home", input.labels.home, input.home);
  push("work", input.labels.work, input.work);
  push("airport", input.labels.airport, input.airport);
  push("last", input.last?.name ?? "", input.last);
  return out;
}

/** خالصة: **أيُّ بطاقةٍ في الدوّار ظاهرة** من موضع التمرير — وفي واجهةٍ من اليمين يكون `scrollLeft` سالباً في Chromium وWebKit
 *  (والصفرُ أوّلُ البطاقات)، فتُقرأ قيمتُه المطلقة. والنتيجةُ محصورةٌ في عدد البطاقات. */
export function carouselIndex(scrollLeft: number, step: number, count: number): number {
  if (count <= 0 || step <= 0) return 0;
  const index = Math.round(Math.abs(scrollLeft) / step);
  return Math.min(count - 1, Math.max(0, index));
}

/** خالصة: **شبكةُ الخدمات بلا فراغ** — عمودان، والبطاقتان الكبيرتان («رحلة» و«طرد») أوّلُ صفّ، **وما بعدهما إن كان فرداً امتدّ آخرُه
 *  على العمودين** فلا تبقى خانةٌ فارغة (لقطةُ المالك: بطاقتان يميناً وفراغٌ يساراً). */
export function spansLast(count: number): boolean {
  return count % 2 === 1;
}
