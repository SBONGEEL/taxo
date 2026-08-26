/** **حارسُ ملحق العربية على الخريطة** — يقيس أن المنشورَ هو المثبَّت.
 *
 * الملحقُ يُخدَم من `public/vendor/` لا من CDN ولا باستيرادٍ من الحزمة:
 * **`exports` في `@mapbox/mapbox-gl-rtl-text` سلسلةٌ واحدة** (`./src/index.js`)،
 * فاستيرادُ `dist/…?url` **يمرّ في خادم التطوير ويسقط في البناء** — وقع مقيساً
 * 2026-08-26: `Package subpath 'undefined' is not defined by "exports"`.
 *
 * **ونسخةٌ تُنسخ باليد تتخلّف عن حزمتها بلا صوت** — فهذا الحارسُ يقارن
 * بايتاً ببايت، ويصلح الفرقَ بنفسه بدل أن يشتكي منه.
 */
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = resolve(root, "node_modules/@mapbox/mapbox-gl-rtl-text/dist/mapbox-gl-rtl-text.js");
const dst = resolve(root, "public/vendor/mapbox-gl-rtl-text.js");

if (!existsSync(src)) {
  console.error("✗ check:rtl · الملحقُ غيرُ مثبَّت — `npm install` أوّلاً.");
  console.error(`  المنتظَر: ${src}`);
  process.exit(1);
}

const sum = (p) => createHash("sha256").update(readFileSync(p)).digest("hex").slice(0, 12);
const before = existsSync(dst) ? sum(dst) : null;
const want = sum(src);

if (before !== want) {
  mkdirSync(dirname(dst), { recursive: true });
  copyFileSync(src, dst);
  console.log(`✓ check:rtl · نُسخ الملحقُ من الحزمة (${before ?? "غائب"} → ${want})`);
} else {
  console.log(`✓ check:rtl · المنشورُ هو المثبَّت (${want})`);
}
