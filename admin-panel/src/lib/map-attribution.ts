/** **نسبةُ الخريطة زرُّ ⓘ مطويٌّ أبداً — لا ينفتح إلا بنقرة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّة ١؛ SPEC §١٠٥/٤).
 *
 * **العطبُ المقيس** (لقطةُ المالك): بطاقةُ الخريطة في رئيسيّة الراكب — «© OpenFreeMap, OpenMapTiles Data from OpenStreetMap» تنفتح وحدَها
 * وتغطّي نصفَ البطاقة. **وعلّتُها في المكتبة**: `AttributionControl` المضغوطُ يضيف `-compact-show` بنفسه في `_updateCompact`
 * (عند البناء، وعند كلِّ `resize`، وبعد تبدّل النمط) — والطيُّ القديمُ بمؤقّتِ ٥ ث كان يلاحقه، فيُرى نصفَ ثانيةٍ ويبقى مفتوحاً حين
 * يسبق التغيّرُ المؤقّت.
 *
 * **فهنا حارسٌ لا مؤقّت**: `MutationObserver` على صندوق النسبة — **كلُّ فتحٍ لم تسبقه نقرةٌ على ⓘ يُطوى في الإطار نفسِه**، أيّاً كان
 * سببه (أوّلُ تحميل، تغيّرُ الحجم أو ملءُ الشاشة، تبدّلُ المظهر، العودةُ من الخلفيّة). **ونقرةُ ⓘ وحدَها تفتحها**، وتُطوى بالنقرة
 * التالية (سلوكُ المكتبة) أو بعد `ATTRIBUTION_OPEN_MS`.
 *
 * **والرخصةُ محفوظة** (إرشاداتُ OSMF، قِيست ٢٠٢٦-١١-١٨): الطيُّ جائزٌ ما بقي ⓘ أو صفحةُ «حول» تدلّ على الرخصة، **والنسبةُ عند بدء
 * التطبيق «لا يلزم أن تُعرض كلَّ مرّة»** — فالنسبةُ تُرى في شاشة البدء (`© OpenStreetMap`)، وكاملةً في «حول التطبيق / التراخيص»
 * (`lib/map-credits.ts`)، وخلف ⓘ على كلِّ خريطة.
 *
 * يعمل على المحرّكين (`maplibre-gl` · `mapbox-gl`): الأصنافُ نفسُها بلاحقتين. **ونسخٌ متطابقةٌ بايتاً** في التطبيقين واللوحة.
 */

/** كم تبقى مفتوحةً بعد نقرة ⓘ قبل أن تُطوى وحدَها */
export const ATTRIBUTION_OPEN_MS = 6000;
/** نافذةُ «فتحٌ بنقرة» — ما بين نقرة ⓘ وإضافة المكتبة صنفَ الظهور (المكتبةُ تضيفه في معالج النقرة نفسِه) */
const TAP_WINDOW_MS = 800;

interface AttributionHost {
  getContainer(): HTMLElement;
}
interface Engine {
  addControl(control: unknown, position: string): unknown;
}

type AttributionControlClass = new (options: { compact: boolean; customAttribution?: string }) => unknown;

const BOX = ".maplibregl-ctrl-attrib, .mapboxgl-ctrl-attrib";
const BUTTON = ".maplibregl-ctrl-attrib-button, .mapboxgl-ctrl-attrib-button";
const SHOW = ["maplibregl-compact-show", "mapboxgl-compact-show"];

/** **أمفتوحةٌ؟** — صنفُ الظهور في الوضع المضغوط (والاختبارُ يقرأ هذا نفسَه) */
export function attributionOpen(box: Element): boolean {
  return SHOW.some((name) => box.classList.contains(name));
}

/** **يطوي النسبةَ** — صنفُ الظهور وسمةُ `open` معاً */
export function foldAttribution(root: ParentNode): void {
  const box = root.querySelector<HTMLElement>(BOX);
  if (!box) return;
  box.classList.remove(...SHOW);
  box.removeAttribute("open");
}

/** **يضيف النسبةَ مضغوطةً، ويحرسها مطويّةً إلا بنقرة** — ويعيد دالّةَ تنظيفٍ تُنادى مع إزالة الخريطة */
export function foldedAttribution(map: AttributionHost, Control: AttributionControlClass, customAttribution?: string): () => void {
  const engine = map as unknown as Engine;
  engine.addControl(new Control({ compact: true, customAttribution }), "bottom-right");
  const root = map.getContainer();
  let tappedAt = -Infinity;
  let timer = 0;
  let observed: Element | null = null;

  const guard = () => {
    const box = root.querySelector(BOX);
    if (!box) return;
    if (!attributionOpen(box)) {
      window.clearTimeout(timer);
      return;
    }
    if (performance.now() - tappedAt > TAP_WINDOW_MS) {
      // **فتحٌ بلا نقرة** — من المكتبة أو من أيِّ شيء: يُطوى في الإطار نفسِه
      foldAttribution(root);
      return;
    }
    window.clearTimeout(timer);
    timer = window.setTimeout(() => foldAttribution(root), ATTRIBUTION_OPEN_MS);
  };

  const observer = new MutationObserver(guard);
  const watch = () => {
    const box = root.querySelector(BOX);
    if (box && box !== observed) {
      observer.disconnect();
      observer.observe(box, { attributes: true, attributeFilter: ["class", "open"] });
      observed = box;
    }
    guard();
  };
  watch();
  // الصندوقُ قد يُبنى بعد `addControl` بإطار، وقد يُعاد بناؤه — فيُراقَب الجذرُ لظهوره
  const rootObserver = new MutationObserver(watch);
  rootObserver.observe(root, { childList: true, subtree: true });

  // **النقرةُ تُسجَّل قبل معالج المكتبة** (طورُ الالتقاط) — فيعرف الحارسُ أن الفتحَ جاء منها
  const onTap = (event: Event) => {
    if ((event.target as HTMLElement | null)?.closest(BUTTON)) tappedAt = performance.now();
  };
  root.addEventListener("click", onTap, true);
  // **العودةُ من الخلفيّة** — لا شيءَ يُفتح، وما فُتح قبلها يُطوى
  const onVisible = () => {
    if (document.visibilityState === "visible") foldAttribution(root);
  };
  document.addEventListener("visibilitychange", onVisible);

  return () => {
    window.clearTimeout(timer);
    observer.disconnect();
    rootObserver.disconnect();
    root.removeEventListener("click", onTap, true);
    document.removeEventListener("visibilitychange", onVisible);
  };
}
