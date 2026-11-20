/** **صورةُ الملفّ — المنطقُ الخالص** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-هـ) — منسوخٌ بايتاً في التطبيقين (`check:permissions-plugin`).
 *
 *  القصُّ الدائريّ: الصورةُ تملأ مربّعاً (`cover`) ويُحرَّك موضعُها ويُكبَّر، **ولا يخرج المربّعُ عن الصورة أبداً** (`clampCrop`) —
 *  فلا تظهر حافّةٌ فارغةٌ في الدائرة. والناتجُ مربّعٌ ٥١٢ يرسمه `canvas` — **وإعادةُ الرسم تُسقط EXIF كلَّه** (والموقعُ معه).
 *  والحرفُ البديلُ في دائرةٍ **لونُها من الاسم** — الاسمُ نفسُه يأخذ اللونَ نفسَه في كلِّ مرّة، نهاراً وليلاً. */

export const OUTPUT_EDGE = 512;
export const MAX_ZOOM = 4;

export interface Crop {
  /** التكبيرُ فوق `cover` — ١ = الصورةُ تملأ المربّعَ بأقصر ضلعيها */
  zoom: number;
  /** إزاحةُ مركز الصورة عن مركز المربّع، بكسراتٍ من ضلع المربّع */
  x: number;
  y: number;
}

export const INITIAL_CROP: Crop = { zoom: 1, x: 0, y: 0 };

/** حجمُ الصورة المرسومة في مربّعٍ ضلعُه ١ — `cover` ثمّ التكبير */
export function drawnSize(width: number, height: number, zoom: number): { w: number; h: number } {
  const cover = 1 / Math.min(width, height);
  return { w: width * cover * zoom, h: height * cover * zoom };
}

/** **لا حافّةَ فارغة**: الإزاحةُ محصورةٌ بما يزيد من الصورة على المربّع في كلِّ اتّجاه */
export function clampCrop(crop: Crop, width: number, height: number): Crop {
  const zoom = Math.min(MAX_ZOOM, Math.max(1, crop.zoom));
  const { w, h } = drawnSize(width, height, zoom);
  const limitX = Math.max(0, (w - 1) / 2);
  const limitY = Math.max(0, (h - 1) / 2);
  return {
    zoom,
    x: Math.min(limitX, Math.max(-limitX, crop.x)),
    y: Math.min(limitY, Math.max(-limitY, crop.y)),
  };
}

/** مستطيلُ المصدر (بكسلاتُ الصورة الأصليّة) الذي يملأ المربّعَ الناتج */
export function sourceRect(width: number, height: number, crop: Crop): { sx: number; sy: number; size: number } {
  const safe = clampCrop(crop, width, height);
  const { w } = drawnSize(width, height, safe.zoom);
  const pxPerUnit = width / w;
  const size = pxPerUnit;
  const centerX = width / 2 - safe.x * pxPerUnit;
  const centerY = height / 2 - safe.y * pxPerUnit;
  return { sx: centerX - size / 2, sy: centerY - size / 2, size };
}

const PALETTE = ["#1F2A37", "#2B2F45", "#332A3E", "#1E3538", "#3A2E26", "#27332A"] as const;

/** **لونُ دائرة الحرف من الاسم** — ثابتٌ لصاحبه */
export function letterColour(name: string): string {
  let hash = 0;
  for (const char of name.trim()) hash = (hash * 31 + (char.codePointAt(0) ?? 0)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function initialOf(name: string): string {
  const first = [...name.trim()][0];
  return first ?? "؟";
}
