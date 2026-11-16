/** **نسبةُ الخريطة زرَّ ⓘ صغيراً** (قرارُ المالك ٢٠٢٦-١١-١٦، SPEC §١٠٥/٤) — **منسوخٌ حرفاً في التطبيقين واللوحة**.
 *
 * **والشكلُ كما تشترطه الرخصتان** (قِيستا ٢٠٢٦-١١-١٦): إرشاداتُ OSMF تمنع نسبةً **لا تُرى إلا بتفاعل**، وتجيز طيَّها **بعد خمس ثوانٍ
 * أو عند أوّل تحريكٍ للخريطة** ما بقي زرُّ ⓘ أو صفحةُ «حول» تدلّ عليها. فتُرى عند فتح الخريطة، ثمّ تُطوى بعد ٥ ث (أو بأوّل سحب —
 * سلوكُ المكتبة نفسِها في وضعها المضغوط)، **ولمسُ ⓘ يفتحها ويُطوى بلمسةٍ ثانيةٍ أو بعد ٥ ث**. والألوانُ من رموز المظهر في CSS.
 *
 * يعمل على المحرّكين (`maplibre-gl` · `mapbox-gl`): كلاهما يملك `AttributionControl({ compact })` بالأصناف نفسِها بلاحقتين.
 */

/** مدّةُ ظهور النسبة قبل طيِّها — خمسُ ثوانٍ كما في إرشادات OSMF */
export const ATTRIBUTION_FOLD_MS = 5000;

/** ما يلزم من الخريطة — والمحرّكان يختلفان في تواقيع `addControl`/`once` المثقلة، فيُنادَيان من خلال `Engine` */
interface AttributionHost {
  getContainer(): HTMLElement;
}
interface Engine {
  addControl(control: unknown, position: string): unknown;
  once(type: string, listener: () => void): unknown;
}

type AttributionControlClass = new (options: { compact: boolean; customAttribution?: string }) => unknown;

const BOX = ".maplibregl-ctrl-attrib, .mapboxgl-ctrl-attrib";
const BUTTON = ".maplibregl-ctrl-attrib-button, .mapboxgl-ctrl-attrib-button";

/** **يطوي النسبةَ** — صنفُ «الظهور» وسمةُ `open` معاً، كما تطويها المكتبةُ عند السحب */
export function foldAttribution(root: ParentNode): void {
  const box = root.querySelector<HTMLElement>(BOX);
  if (!box) return;
  box.classList.remove("maplibregl-compact-show", "mapboxgl-compact-show");
  box.removeAttribute("open");
}

/** **يضيف النسبةَ مضغوطةً ويطويها في موعدها** — ويعيد دالّةَ تنظيفٍ تُنادى مع إزالة الخريطة */
export function foldedAttribution(map: AttributionHost, Control: AttributionControlClass, customAttribution?: string): () => void {
  const engine = map as unknown as Engine;
  engine.addControl(new Control({ compact: true, customAttribution }), "bottom-right");
  const root = map.getContainer();
  let timer = 0;
  const later = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => foldAttribution(root), ATTRIBUTION_FOLD_MS);
  };
  engine.once("load", later);
  // **لمسُ ⓘ يفتحها، وتُطوى وحدَها بعد خمس ثوانٍ** — واللمسةُ الثانيةُ تطويها بسلوك المكتبة نفسِه
  const onClick = (event: Event) => {
    if ((event.target as HTMLElement | null)?.closest(BUTTON)) later();
  };
  root.addEventListener("click", onClick);
  return () => {
    window.clearTimeout(timer);
    root.removeEventListener("click", onClick);
  };
}
