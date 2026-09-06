/** الرسمُ المميّز 1024×500 لمتجر Play — **يُولَّد من الشعار لا يُرسم بيد**.
 *
 * **ولمَ مُولَّدٌ لا ملفُّ صورةٍ يُودَع**: الشعارُ يتغيّر فيتغيّر الرسمُ معه،
 * **وصورةٌ مُودَعةٌ تبلى بصمت** — وهي عائلةُ «نسختان لشيءٍ واحد» بحرفها.
 *
 * **والحدُّ الآمن**: Play يقصّ الرسمَ في أماكنَ ويُظهره كاملاً في أخرى،
 * **ولا يضمن ظهورَ الأطراف** — فكلُّ ما يُقرأ يقع في الوسط بهامشٍ واسع.
 *
 * **ولا رقمَ عمولةٍ ولا وعدَ مطلق** (قاعدةُ المالك تسري خارج التطبيق كما تسري
 * داخله): النصُّ وصفُ خدمةٍ لا عرضُ سعر.
 *
 *     node scripts/feature-graphic.mjs   →   assets-src/store/feature-1024x500.png
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "../assets-src/store");

const INK = "#0d1014";
const CREAM = "#ddd8cf";
const MUTED = "#8b949e";

//: **مسارُ الوسم من `logo.svg` حرفاً** — لا رسمٌ ثانٍ يشبهه.
const WORDMARK =
  '<path d="M8 24 H52 M30 24 V72"/>' +
  '<path d="M64 72 L86 24 L108 72 M72 58 H100"/>' +
  '<path d="M120 24 L164 72 M164 24 L120 72"/>' +
  '<circle cx="198" cy="48" r="24"/>';

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="500" viewBox="0 0 1024 500">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#14181d"/>
      <stop offset="1" stop-color="${INK}"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="500" fill="url(#bg)"/>

  <!-- الوسمُ في الوسط، مُكبَّرٌ من 230×96 إلى 460×192 -->
  <g transform="translate(282,132) scale(2)" fill="none" stroke="${CREAM}"
     stroke-width="8" stroke-linecap="round" stroke-linejoin="round">
    ${WORDMARK}
  </g>

  <text x="512" y="392" text-anchor="middle" fill="${CREAM}"
        font-family="'Noto Sans Arabic','Segoe UI',sans-serif" font-size="34" font-weight="600"
        direction="rtl">تاكسي بالتطبيق — للراكب والكبتن</text>

  <text x="512" y="436" text-anchor="middle" fill="${MUTED}"
        font-family="'Noto Sans Arabic','Segoe UI',sans-serif" font-size="22"
        direction="rtl">اطلب رحلتك، وتابع سيارتك على الخريطة حتى تصل</text>
</svg>`;

mkdirSync(OUT, { recursive: true });
const target = resolve(OUT, "feature-1024x500.png");

const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toBuffer();
writeFileSync(target, png);

const meta = await sharp(png).metadata();
console.log(`  ✓ ${target}`);
console.log(`    ${meta.width}×${meta.height} · ${png.length} بايت · ${meta.format}`);
if (meta.width !== 1024 || meta.height !== 500) {
  throw new Error("  ✗ الأبعادُ ليست 1024×500 — يُوقَف.");
}
