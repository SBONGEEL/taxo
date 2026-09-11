/** الرسمُ المميّز 1024×500 لتطبيق الكبتن — **يُولَّد من الشعار لا يُرسم بيد**.
 *
 * **أخو `feature-graphic.mjs` لا نسخةٌ منه**: الوسمُ واحدٌ حرفاً (نفسُ
 * `WORDMARK`)، **والفرقُ قلبُ اللون وشريطُ `DRIVER`** — وهي بعينها قاعدةُ
 * أيقونة الكبتن (قرارُ المالك 2026-08-14): «نفسُ الكلمة ونفسُ الوزن ونفسُ
 * المواضع، والفرقُ قلبُ اللون وكلمةُ الشريط». فيُعرف التطبيقان من عائلةٍ
 * واحدة، ويُميَّز أحدهما عن الآخر من مسافةٍ بلا قراءة.
 *
 * **ولا لونَ ثالثٌ يدخل**: `--bg` و`--tx` من §1.1 وحدَهما، ولا الورديُّ
 * المحجوزُ للسِمة النسائية.
 *
 * **والحدُّ الآمن كما هو**: Play يقصّ الرسمَ في أماكنَ ويُظهره كاملاً في
 * أخرى، **ولا يضمن ظهورَ الأطراف** — فكلُّ ما يُقرأ يقع في الوسط بهامشٍ واسع.
 *
 * **ولا رقمَ عمولةٍ ولا وعدَ مطلق** — النصُّ وصفُ عملٍ لا عرضُ دخل.
 *
 *     node scripts/feature-graphic-driver.mjs
 *       →   assets-src/store/feature-driver-1024x500.png
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "../assets-src/store");

const INK = "#14181d";
const LIGHT = "#e6edf3";
const MUTED = "#5c6672";

//: **نفسُ مسار الوسم في `feature-graphic.mjs` حرفاً** — لا رسمٌ ثانٍ يشبهه.
const WORDMARK =
  '<path d="M8 24 H52 M30 24 V72"/>' +
  '<path d="M64 72 L86 24 L108 72 M72 58 H100"/>' +
  '<path d="M120 24 L164 72 M164 24 L120 72"/>' +
  '<circle cx="198" cy="48" r="24"/>';

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="500" viewBox="0 0 1024 500">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f2f5f8"/>
      <stop offset="1" stop-color="${LIGHT}"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="500" fill="url(#bg)"/>

  <g transform="translate(282,104) scale(2)" fill="none" stroke="${INK}"
     stroke-width="8" stroke-linecap="round" stroke-linejoin="round">
    ${WORDMARK}
  </g>

  <rect x="409" y="312" width="206" height="58" rx="29" fill="${INK}"/>
  <text x="512" y="352" text-anchor="middle" fill="${LIGHT}"
        font-family="'Segoe UI','Helvetica Neue',Arial,sans-serif"
        font-size="33" font-weight="700" letter-spacing="6">DRIVER</text>

  <text x="512" y="424" text-anchor="middle" fill="${INK}"
        font-family="'Noto Sans Arabic','Segoe UI',sans-serif" font-size="32" font-weight="600"
        direction="rtl">تطبيق الكبتن — استقبل الطلبات وتابع أرباحك</text>

  <text x="512" y="464" text-anchor="middle" fill="${MUTED}"
        font-family="'Noto Sans Arabic','Segoe UI',sans-serif" font-size="21"
        direction="rtl">رحلاتك ومحفظتك ومستنداتك في مكان واحد</text>
</svg>`;

mkdirSync(OUT, { recursive: true });
const target = resolve(OUT, "feature-driver-1024x500.png");

const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toBuffer();
writeFileSync(target, png);

const meta = await sharp(png).metadata();
console.log(`  ✓ ${target}`);
console.log(`    ${meta.width}×${meta.height} · ${png.length} بايت · ${meta.format}`);
if (meta.width !== 1024 || meta.height !== 500) {
  throw new Error("  ✗ الأبعادُ ليست 1024×500 — يُوقَف.");
}
