/** أصولُ الموقع — **تُولَّد من الأصول الحقيقية، ولا تُرسم واحدةٌ منها**.
 *
 * ثلاثةُ أعمال:
 *   ١) الخطوطُ TTF → woff2 — **الحجمُ وحدَه يتغيّر، لا الحروف** (وما وصل
 *      woff2 يُنسخ). والقائمةُ في `fonts.mjs`.
 *   ٢) الصورُ PNG → WebP — **والشعارُ يبقى شعارَه**، تحويلُ ترميزٍ لا رسم.
 *      **واللقطاتُ الحقيقيّة** قصّاً وتصغيراً بـAVIF وWebP من بيانها (`screens/shots.json`).
 *   ٣) بطاقةُ المشاركة 1200×630 — **صورةٌ مودَعةٌ بهويّة TAXO 2.0 تُضغط وتُنسخ**.
 *      **ولا شعارَ يُولَّد ولا واجهةَ تُرسم.**
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

import { FONTS } from "./fonts.mjs";

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
//
// **القائمةُ من `fonts.mjs`** — وهي نفسُها التي يطابقها `check:site` بما
// تطلبه الصفحات، فلا خطَّ يُطلب ولا يُولَّد. **والمصدرُ TTF يُضغط، أو WOFF2
// يُنسخ كما هو** (خطٌّ وصل مضغوطاً لا يُضغط ثانيةً).
const missingFonts = [];
for (const name of FONTS) {
  const ttf = join(SF, `${name}.ttf`);
  const ready = join(SF, `${name}.woff2`);
  const woff2 = join(F, `${name}.woff2`);
  if (existsSync(ttf)) {
    const before = readFileSync(ttf);
    const after = Buffer.from(ttf2woff2(before));
    writeFileSync(woff2, after);
    console.log(
      `  خط ${name}: ${before.length} → ${after.length} بايت ` +
        `(−${Math.round((1 - after.length / before.length) * 100)}٪)`,
    );
    made++;
  } else if (existsSync(ready)) {
    writeFileSync(woff2, readFileSync(ready));
    console.log(`  خط ${name}: نُسخ كما هو (${readFileSync(ready).length} بايت)`);
    made++;
  } else {
    missingFonts.push(name);
  }
}
if (missingFonts.length) {
  // **يُسمّى ولا يُبتلع** — و`check:site` بعده يُسقط البناءَ على الغياب نفسِه
  console.log(
    `\n  ⚠ خطوطٌ بلا مصدرٍ في assets-src/fonts/: ${missingFonts.join(" · ")}\n` +
      "     يُوضع `<الاسم>.ttf` أو `<الاسم>.woff2` — **ولا يُجلب خطٌّ من طرفٍ ثالثٍ وقتَ العرض**.\n",
  );
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
// صور، **ونسخُها لازمٌ لأن `public/` مخرَجٌ لا يُودَع**. و`identity-tile.svg`
// بلاطةُ خلفية الهوية (§٦٩) تُستعمل قناعاً فتأخذ لونَها من الرمز.
for (const name of ["car.svg", "logo.svg", "identity-tile.svg"]) {
  const src = join(SA, name);
  if (!existsSync(src)) continue;
  writeFileSync(join(A, name), readFileSync(src));
  console.log(`  ${name}: نُسخ كما هو (${readFileSync(src).length} بايت)`);
  made++;
}

/* ── ٢-ب) اللقطات ─────────────────────────────────────────────────────── */
//
// **مُلتقَطةٌ من التطبيقين وهما يعملان** (`tools/capture-screens/capture.mjs`،
// بشروطه الثلاثة) — **ولا واجهةَ تُرسم**. وتُحوَّل إلى WebP كبقيّة الصور.
//
// **ولا تُشحن إلا لقطةٌ تطلبها الصفحة**: الأداةُ تلتقط ما تستطيع، **والصفحةُ
// لها خاناتٌ بأسمائها** — فلقطةٌ بلا خانةٍ **حمولةٌ لا يراها أحد**، وهي
// «حقلٌ يُحسب ولا يقرؤه أحد» في ثوب صورة. **وتُذكر بالاسم لا تُبتلع صمتاً**،
// وإلا صار الفائضُ عُرفاً.
//
// ## والموقعُ الجديد (§٦٩) — `shots.json` بيانُ اللقطات وعروضِها
//
// **كلُّ لقطةٍ ملفٌّ واحدٌ كما التُقط**، والبيانُ يقول من أين جاء ومتى (`captures`)، وما يُنتظر بعدُ (`awaited`)، وما يُشحن منه
// (`renders`): **قصٌّ بإحداثياتٍ مكتوبة** — فلقطةُ الكبتن الكاملةُ فيها تقييمُ «1.00» من بيانات التجربة، **ولا يُشحن منها إلا
// ما دون ذلك الصفّ** — **وتصغيرٌ إلى ضِعف ما يُعرض** بـAVIF وWebP. ولا بكسلَ يُرسم ولا يُعدَّل.
//
// **ولا يُشحن عرضٌ لا تطلبه الصفحة** — يُقرأ `data-shot` و`data-shot-dark` منها، فعرضٌ مصدرُه لقطةٌ لا موضعَ لها **حمولةٌ لا
// يراها أحد**، ويُذكر بالاسم.
const SITE = join(SRC, "..");
const SS = join(SRC, "screens");
const PS = join(PUB, "screens");
if (existsSync(SS)) {
  mkdirSync(PS, { recursive: true });
  const page = readFileSync(join(SITE, "index.html"), "utf8");
  const wanted = new Set([...page.matchAll(/data-shot(?:-dark)?="([a-z0-9-]+)"/g)].map((m) => m[1]));
  const manifest = JSON.parse(readFileSync(join(SS, "shots.json"), "utf8"));
  const skipped = [];
  for (const [name, spec] of Object.entries(manifest.renders ?? {})) {
    if (!wanted.has(spec.from)) {
      skipped.push(name);
      continue;
    }
    const from = join(SS, `${spec.from}.png`);
    if (!existsSync(from)) {
      // **يُسمّى ولا يُبتلع** — و`check:shots` بعده يُسقط البناءَ على الغياب نفسِه
      console.log(`  ⚠ عرضُ ${name} بلا مصدر: assets-src/screens/${spec.from}.png`);
      continue;
    }
    const before = readFileSync(from).length;
    const sizes = [];
    for (const width of spec.widths) {
      let img = sharp(from);
      if (spec.crop) {
        const [left, top, w, h] = spec.crop;
        img = img.extract({ left, top, width: w, height: h });
      }
      img = img.resize({ width, withoutEnlargement: true });
      const webp = join(PS, `${name}-${width}.webp`);
      const avif = join(PS, `${name}-${width}.avif`);
      await img.clone().webp({ quality: 80, effort: 6 }).toFile(webp);
      await img.clone().avif({ quality: 52, effort: 5 }).toFile(avif);
      sizes.push(`${width}: ${readFileSync(avif).length}/${readFileSync(webp).length}`);
      made += 2;
    }
    console.log(`  لقطة ${name} ← ${spec.from}${spec.crop ? ` (قصّ ${spec.crop.join(",")})` : ""}: ${before} → avif/webp ${sizes.join(" · ")} بايت`);
  }
  if (skipped.length) {
    console.log(`  … عروضٌ مصدرُها بلا موضعٍ في الصفحة (لا تُشحن): ${skipped.join(" · ")}`);
  }
  const listed = new Set([...Object.keys(manifest.captures ?? {}), ...Object.keys(manifest.awaited ?? {})]);
  const stale = readdirSync(SS)
    .filter((f) => f.endsWith(".png"))
    .map((f) => f.replace(/\.png$/, ""))
    .filter((n) => !listed.has(n));
  if (stale.length) {
    // **لقطاتُ الهوية السابقة** — باقيةٌ في الشجرة ولا تُشحن: لا موضعَ لها في صفحة TAXO 2.0
    console.log(`  … لقطاتٌ ليست في shots.json (لا تُشحن): ${stale.join(" · ")}`);
  }
}

/* ── ٣) بطاقةُ المشاركة ────────────────────────────────────────────────── */
//
// **1200×630 بهويّة TAXO 2.0** (§٦٩) — مرسومةٌ من `assets-src/assets/og-card.html` بخطّي العائلة ولقطةِ رئيسة الراكب الحقيقيّة،
// وتُودَع صورةً (`og-card.png`) لأن الخادمَ الذي يبني الموقعَ لا يملك متصفّحاً ولا خطَّيْ العائلة. **وهنا تُضغط وتُنسخ لا تُرسم.**
//
// **وكانت تُركَّب هنا بنصٍّ يقول «صفر عمولة على الكبتن المشترِك»** على لون الهوية السابقة — وعدٌ بنسبةٍ في صورةٍ تُعرض كلَّما
// شورك الرابط، **ولم يقرأها `check:commission-text` لأنها نصٌّ داخل سكربت بناء**. فالنصُّ الآن من اللوحات وحدَها، بلا رقم.
const og = join(A, "og.png");
const ogSrc = join(SA, "og-card.png");
if (existsSync(ogSrc)) {
  await sharp(ogSrc).resize({ width: 1200, height: 630, fit: "cover" }).png({ compressionLevel: 9, palette: true, quality: 90 }).toFile(og);
  console.log(`  og.png: ${readFileSync(ogSrc).length} → ${readFileSync(og).length} بايت (1200×630)`);
  made++;
} else {
  console.log("\n  ⚠ ناقص: assets-src/assets/og-card.png — **بطاقةُ المشاركة لا تُرسم هنا بنصٍّ مخبوز**.\n");
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
