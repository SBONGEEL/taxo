/** أصولُ الموقع — **تُولَّد من الأصول الحقيقية، ولا تُرسم واحدةٌ منها**.
 *
 * ثلاثةُ أعمال:
 *   ١) الخطوطُ TTF → woff2 — **الحجمُ وحدَه يتغيّر، لا الحروف**.
 *   ٢) الصورُ PNG → WebP — **والشعارُ يبقى شعارَه**، تحويلُ ترميزٍ لا رسم.
 *   ٣) بطاقةُ المشاركة 1200×630 — **تركيبُ الشعار الحقيقيِّ على لون الهوية**
 *      بنصِّ التصميم نفسِه. **ولا شعارَ يُولَّد ولا واجهةَ تُرسم.**
 */

import {
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
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
// **والعرضُ يُصغَّر إلى ما يُعرض فعلاً** (قِيس ٢٠٢٦-٠٩-٠٥): كان الشعارُ
// يُشحن بعرض ١٢٣٣ بكسلاً **ويُرسم بـ١٠٤** — ٤٤ ك.ب، **وصار أكبرَ عنصرٍ مرسومٍ
// في الصفحة (LCP)**. **وصورةٌ أكبرُ من موضعها ليست جودةً، هي انتظار.**
// والعرضُ ثلاثةُ أضعاف الرسم ليبقى حادّاً على شاشةٍ بـDPR 3.
const WIDTH = {
  logo: 360,
  "logo-ink": 360,
  "logo-pink": 360,
  "icon-192": 192,
  "cars-stock/A-00": 300, "cars-stock/A-12": 300, "cars-stock/A-24": 300,
  "cars-stock/B-00": 300, "cars-stock/C-00": 300, "cars-stock/D-00": 300,
  "cars-stock/E-00": 300,
};

for (const name of Object.keys(WIDTH)) {
  const png = join(SA, `${name}.png`);
  if (!existsSync(png)) continue;
  const webp = join(A, `${name}.webp`);
  const before = readFileSync(png).length;
  await sharp(png).resize({ width: WIDTH[name], withoutEnlargement: true })
    .webp({ quality: 88, effort: 6 }).toFile(webp);
  const after = readFileSync(webp).length;
  console.log(
    `  ${name}: ${before} → ${after} بايت (−${Math.round((1 - after / before) * 100)}٪)`,
  );
  made++;
}

// **والأيقونةُ تبقى PNG لكن بحجمٍ معقول**: كانت ١٤٠ ك.ب لأنها الأصلُ ٥١٢
// بلا ضغط — **وأثقلُ موردٍ في الصفحة كان أيقونةَ تبويب**.
{
  const src = join(SA, "favicon.png");
  const out = join(A, "favicon.png");
  if (existsSync(src)) {
    const before = readFileSync(src).length;
    await sharp(src).resize({ width: 180 }).png({ compressionLevel: 9, palette: true }).toFile(out);
    const after = readFileSync(out).length;
    console.log(`  favicon: ${before} → ${after} بايت (−${Math.round((1 - after / before) * 100)}٪)`);
    made++;
  }
}

// **وما لا يُحوَّل يُنسخ كما هو** — `car.svg` و`logo.svg` أصولٌ متجهةٌ لا
// صور، **ونسخُها لازمٌ لأن `public/` مخرَجٌ لا يُودَع**.
for (const name of ["car.svg", "logo.svg"]) {
  const src = join(SA, name);
  if (!existsSync(src)) continue;
  writeFileSync(join(A, name), readFileSync(src));
  console.log(`  ${name}: نُسخ كما هو (${readFileSync(src).length} بايت)`);
  made++;
}

/* ── ٢-ب) اللقطات ─────────────────────────────────────────────────────── */
//
// **مُلتقَطةٌ من التطبيقين وهما يعملان** (`scripts/capture.mjs` في مجلَّد
// الجلسة) — **ولا واجهةَ تُرسم**. وتُحوَّل إلى WebP كبقيّة الصور.
const SS = join(SRC, "screens");
const PS = join(PUB, "screens");
if (existsSync(SS)) {
  mkdirSync(PS, { recursive: true });
  for (const file of readdirSync(SS).filter((f) => f.endsWith(".png"))) {
    const from = join(SS, file);
    const to = join(PS, file.replace(/\.png$/, ".webp"));
    const before = readFileSync(from).length;
    await sharp(from).webp({ quality: 82, effort: 6 }).toFile(to);
    console.log(
      `  لقطة ${file.replace(/\.png$/, "")}: ${before} → ${readFileSync(to).length} بايت`,
    );
    made++;
  }
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

/* ── ٤) شارةُ Google Play — **الملفُّ الرسميُّ كما هو** ─────────────────── */
//
// **ولا يُمسّ ولا يُقصّ ولا يُعاد تلوينُه** (شرطُ المالك ١٠، وشروطُ علامة
// Google): يُنسخ بحجمه ومساحته الآمنة، **ولا زرَّ مرسومٌ يحاكيه**.
//
// **ولا يُحوَّل إلى WebP**: تحويلُ ملفِّ علامةٍ تجاريةٍ **مسٌّ له**، وحجمُه
// ١٥٫٨ ك.ب لا يستحقّ ذلك. **والقاعدةُ أوضحُ من المكسب.**
const badgeSrc = join(SA, "google-play-badge.png");
const badge = join(A, "google-play-badge.png");
if (existsSync(badgeSrc)) {
  writeFileSync(badge, readFileSync(badgeSrc));
  console.log(
    `  google-play-badge: ${readFileSync(badge).length} بايت — الملفُّ الرسميُّ كما هو`,
  );
  made++;
}
if (!existsSync(badge)) {
  console.log(
    "\n  ⚠ ناقص: assets/google-play-badge.png — **الشارةُ الرسميةُ من ملفّ Google**.\n" +
      "     ولا تُرسم بديلاً (شرطُ المالك ١٠): زرٌّ يحاكيها مخالفةُ علامةٍ تجارية.\n" +
      "     وحالُ `play` تعرض شارةً معطَّلةً حتى يصل الملفّ — **لا زرَّ كاذب**.",
  );
}

console.log(`\n✓ ${made} أصلاً وُلّد من أصولٍ حقيقية.`);
