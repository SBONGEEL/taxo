/** أصولُ الموقع — **تُولَّد من الأصول الحقيقية، ولا تُرسم واحدةٌ منها**.
 *
 * ثلاثةُ أعمال:
 *   ١) الخطوطُ TTF → woff2 — **الحجمُ وحدَه يتغيّر، لا الحروف**.
 *   ٢) الصورُ PNG → WebP — **والشعارُ يبقى شعارَه**، تحويلُ ترميزٍ لا رسم.
 *   ٣) بطاقةُ المشاركة 1200×630 — **تركيبُ الشعار الحقيقيِّ على لون الهوية**
 *      بنصِّ التصميم نفسِه. **ولا شعارَ يُولَّد ولا واجهةَ تُرسم.**
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import ttf2woff2 from "ttf2woff2";

const HERE = dirname(fileURLToPath(import.meta.url));
//: **المُدخَلُ يُودَع ولا يُنشر، والمخرَجُ يُنشر ولا يُودَع.**
const SRC = join(HERE, "..", "assets-src");
const PUB = join(HERE, "..", "public");
const A = join(PUB, "assets");
const F = join(PUB, "fonts");
const SA = join(SRC, "assets");
const SF = join(SRC, "fonts");
mkdirSync(join(A, "cars-stock"), { recursive: true });
mkdirSync(F, { recursive: true });

let made = 0;

/* ── ١) الخطوط ─────────────────────────────────────────────────────────── */
for (const weight of ["400", "500", "700"]) {
  const ttf = join(SF, `IBMPlexSansArabic-${weight}.ttf`);
  const woff2 = join(F, `IBMPlexSansArabic-${weight}.woff2`);
  if (!existsSync(ttf)) continue;
  const before = readFileSync(ttf);
  const after = Buffer.from(ttf2woff2(before));
  writeFileSync(woff2, after);
  console.log(
    `  خط ${weight}: ${before.length} → ${after.length} بايت ` +
      `(−${Math.round((1 - after.length / before.length) * 100)}٪)`,
  );
  made++;
}

/* ── ٢) الصور ──────────────────────────────────────────────────────────── */
for (const name of [
  "logo", "logo-ink", "logo-pink", "favicon", "icon-192",
  // **مركباتُ الشريط**: خارجَ الشاشة وتُحمَّل كسولاً، **وحجمُها هو الذي يُقاس**
  "cars-stock/A-00", "cars-stock/A-12", "cars-stock/A-24",
  "cars-stock/B-00", "cars-stock/C-00", "cars-stock/D-00", "cars-stock/E-00",
]) {
  const png = join(SA, `${name}.png`);
  if (!existsSync(png)) continue;
  const webp = join(A, `${name}.webp`);
  const before = readFileSync(png).length;
  await sharp(png).webp({ quality: 90, effort: 6 }).toFile(webp);
  const after = readFileSync(webp).length;
  console.log(
    `  ${name}: ${before} → ${after} بايت (−${Math.round((1 - after / before) * 100)}٪)`,
  );
  made++;
}

/* ── ٣) بطاقةُ المشاركة ────────────────────────────────────────────────── */
//
// **1200×630 بلون الـHero وشعارِ الموقع الحقيقيّ** — والنصُّ من `النصوص.md`.
// **ولا يُرسم شيءٌ لم يوجد**: خلفيةٌ بلونٍ مصرَّحٍ وشعارٌ قائمٌ ونصٌّ مكتوب.
const og = join(A, "og.png");
const logo = join(SA, "logo.png");
if (existsSync(logo)) {
  const svg = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
       <rect width="1200" height="630" fill="#14181d"/>
       <rect x="0" y="0" width="1200" height="6" fill="#3fb970"/>
       <text x="1100" y="330" text-anchor="end" fill="#e6edf3"
             font-family="IBM Plex Sans Arabic, Segoe UI, sans-serif"
             font-size="52" font-weight="700" direction="rtl">تاكسي بالتطبيق للراكب والكبتن</text>
       <text x="1100" y="400" text-anchor="end" fill="#8b949e"
             font-family="IBM Plex Sans Arabic, Segoe UI, sans-serif"
             font-size="30" direction="rtl">صفر عمولة على الكبتن المشترِك · خدمة نسائية · محفظة ودفع</text>
       <text x="1100" y="560" text-anchor="end" fill="#8b949e"
             font-family="IBM Plex Sans Arabic, Segoe UI, sans-serif" font-size="26">taxo.tajora.ly</text>
     </svg>`,
  );
  const mark = await sharp(logo).resize({ width: 260 }).toBuffer();
  await sharp(svg)
    .composite([{ input: mark, top: 120, left: 840 }])
    .png()
    .toFile(og);
  console.log(`  og.png: ${readFileSync(og).length} بايت (1200×630)`);
  made++;
}

/* ── ٤) شارةُ Google Play — **لا تُرسم، وتُطلب** ────────────────────────── */
const badge = join(A, "google-play-badge.png");
if (!existsSync(badge)) {
  console.log(
    "\n  ⚠ ناقص: assets/google-play-badge.png — **الشارةُ الرسميةُ من ملفّ Google**.\n" +
      "     ولا تُرسم بديلاً (شرطُ المالك ١٠): زرٌّ يحاكيها مخالفةُ علامةٍ تجارية.\n" +
      "     وحالُ `play` تعرض شارةً معطَّلةً حتى يصل الملفّ — **لا زرَّ كاذب**.",
  );
}

console.log(`\n✓ ${made} أصلاً وُلّد من أصولٍ حقيقية.`);
