#!/usr/bin/env node
// **تباينُ النصِّ فوق الخريطة في المظهرين** (قرارُ المالك ٢٠٢٦-١١-١٦، SPEC §١٠٥/٢) — منسوخٌ في التطبيقين واللوحة.
//
// **ما يقيسه**: يحلّ رموزَ `taxo2/tokens.css` مرّتين — النهارُ (`.t2`) والليلُ (`html.dark .t2`) — ثمّ:
//   ١. **ألوانُ الخريطة نفسِها** (`--t2-map-*`، وهي ما يُبنى منه النمطُ المفتوح وصبغُ Mapbox): الاسمُ على هالته وعلى الأرض ≥ ٤٫٥،
//      والاسمُ الثانويُّ ≥ ٣، والماءُ والحدائقُ والطرقُ تُفرَّق عن الأرض (≥ ١٫١٥).
//   ٢. **كلُّ قاعدة CSS في شاشات الخريطة تحمل لونَ نصٍّ وخلفيّة**: التباينُ في المظهرين ≥ ٤٫٥ (≥ ٣ للأيقونة والنصّ الكبير/العريض).
//   ٣. **لونُ نصٍّ ثابتٌ** (`#fff` · `white` · `#000` · `black`) فوق خلفيّةٍ من الرموز — يسقط: يصير غيرَ مقروءٍ حين تتبدّل الخلفيّة.
//
// **وما لا يقيسه — ويُقال**: لا يرسم بكسلاً. قاعدةٌ لونُها في ملفٍّ وخلفيّتُها في أخرى (أو في `style=`) لا تُقرن؛ والصورُ والنصُّ
// المرسومُ داخل الخريطة بمحرّكها يُقاس من رموزه (البند ١) لا من الشاشة. **فاللقطاتُ بالمظهرين تبقى شرطاً بشريّاً.**
//
//     node scripts/check-contrast.mjs        # يخرج ١ ويسرد كلَّ قاعدةٍ ناقصة

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const TOKENS = join(ROOT, "src/taxo2/tokens.css");
const CSS_DIRS = ["src/screens/t2", "src/taxo2"].map((d) => join(ROOT, d)).filter(existsSync);
const EXTRA = ["src/index.css"].map((f) => join(ROOT, f)).filter(existsSync);

const strip = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");

function block(css, startsWith) {
  const at = css.indexOf(startsWith);
  if (at < 0) return null;
  const open = css.indexOf("{", at);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}" && --depth === 0) return css.slice(open + 1, i);
  }
  return null;
}

function decls(body) {
  const out = {};
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

const tokensCss = strip(readFileSync(TOKENS, "utf8"));
const light = decls(block(tokensCss, ".t2 {") ?? "");
const dark = { ...light, ...decls(block(tokensCss, "html.dark .t2:not(.t2-day)") ?? "") };

function resolve(value, set, depth = 0) {
  if (!value || depth > 8) return null;
  return value.replace(/var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)/g, (_, name, fallback) => resolve(set[name] ?? fallback, set, depth + 1) ?? "");
}

function parseColor(text) {
  if (!text) return null;
  const t = text.trim().toLowerCase();
  if (t === "white") return [255, 255, 255, 1];
  if (t === "black") return [0, 0, 0, 1];
  if (t === "transparent") return [0, 0, 0, 0];
  let m = t.match(/^#([0-9a-f]{3,8})$/);
  if (m) {
    const h = m[1];
    const full = h.length <= 4 ? [...h].map((c) => c + c).join("") : h;
    const n = (i) => parseInt(full.slice(i, i + 2), 16);
    return [n(0), n(2), n(4), full.length === 8 ? n(6) / 255 : 1];
  }
  m = t.match(/^rgba?\(([^)]+)\)$/);
  if (m) {
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p[3] ?? 1];
  }
  m = t.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%\s*,\s*transparent\)$/);
  if (m) {
    const c = parseColor(m[1]);
    return c ? [c[0], c[1], c[2], c[3] * Number(m[2]) / 100] : null;
  }
  return null;
}

const over = (top, under) => {
  const a = top[3];
  return [0, 1, 2].map((i) => top[i] * a + under[i] * (1 - a)).concat(1);
};
const lum = (c) => {
  const f = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

const failures = [];
const themes = [["النهار", light], ["الليل", dark]];

// ── ١. ألوانُ الخريطة نفسِها
const MAP_PAIRS = [
  ["--t2-map-label", "--t2-map-label-halo", 4.5, "اسمُ المكان على هالته"],
  ["--t2-map-label", "--t2-map-land", 4.5, "اسمُ المكان على الأرض"],
  ["--t2-map-label-minor", "--t2-map-land", 3, "الاسمُ الثانويّ على الأرض"],
  ["--t2-map-water", "--t2-map-land", 1.15, "الماءُ يُفرَّق عن الأرض"],
  ["--t2-map-park", "--t2-map-land", 1.1, "الحدائقُ تُفرَّق عن الأرض"],
  ["--t2-map-road", "--t2-map-land", 1.15, "الطرقُ تُفرَّق عن الأرض"],
  ["--t2-map-route", "--t2-map-land", 3, "خطُّ المسار على الأرض"],
  ["--t2-map-route", "--t2-map-road", 3, "خطُّ المسار على الطريق"],
];
let mapChecked = 0;
for (const [name, set] of themes) {
  const bg = parseColor(resolve(set["--t2-bg"], set)) ?? [255, 255, 255, 1];
  for (const [fg, under, min, what] of MAP_PAIRS) {
    if (!set[fg] || !set[under]) continue;
    const a = parseColor(resolve(set[fg], set));
    const b = parseColor(resolve(set[under], set));
    if (!a || !b) continue;
    mapChecked++;
    const r = ratio(over(a, over(b, bg)), over(b, bg));
    if (r < min) failures.push(`${name} · الخريطة · ${what}: ${r.toFixed(2)} < ${min} (${fg} على ${under})`);
  }
}

// ── ٢ و٣. قواعدُ CSS في شاشات الخريطة
const files = [...CSS_DIRS.flatMap((d) => readdirSync(d).filter((f) => f.endsWith(".css")).map((f) => join(d, f))), ...EXTRA];
let rulesChecked = 0;
const FIXED = /^(#fff|#ffffff|white|#000|#000000|black)$/i;
for (const file of files) {
  if (file === TOKENS) continue;
  const css = strip(readFileSync(file, "utf8"));
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selector = m[1].trim().split("\n").pop().trim();
    const body = m[2];
    const color = body.match(/(?:^|;)\s*color\s*:\s*([^;]+)/)?.[1]?.trim();
    const background = body.match(/(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)/)?.[1]?.trim();
    if (!color || !background || color === "inherit" || color === "currentColor") continue;
    const fixedOnToken = FIXED.test(color) && background.includes("var(");
    if (fixedOnToken) failures.push(`${file.replace(ROOT, "")} · ${selector}: لونُ نصٍّ ثابت (${color}) فوق خلفيّةٍ من الرموز — استعمل رمزاً (‎--t2-on-*)`);
    const size = Number(body.match(/font-size\s*:\s*([\d.]+)px/)?.[1] ?? 0);
    const weight = Number(body.match(/font-weight\s*:\s*(\d+)/)?.[1] ?? 400);
    const large = size >= 18 || (size >= 14 && weight >= 700) || /icon|mark|chev|dot/.test(selector);
    const min = large ? 3 : 4.5;
    for (const [name, set] of themes) {
      const base = parseColor(resolve(set["--t2-bg"], set));
      const bgc = parseColor(resolve(background, set));
      const fgc = parseColor(resolve(color, set));
      if (!base || !bgc || !fgc || bgc[3] === 0) continue;
      rulesChecked++;
      const under = over(bgc, base);
      const r = ratio(over(fgc, under), under);
      if (r < min) failures.push(`${name} · ${file.replace(ROOT, "")} · ${selector}: ${r.toFixed(2)} < ${min}`);
    }
  }
}

// **ترتيبُ المظهر — ما لا يراه حسابُ الرموز** (SPEC §١٠٥/٢، مقيس ٢٠٢٦-١١-١٦): الرموزُ كلُّها صحيحةٌ والخريطةُ تُبنى من رموز `html.dark`
// في أثرها هي، **فإن بُدِّل الصنفُ في `useEffect` جرى بعد أثر الخريطة** (آثارُ الأبناء قبل الآباء) فتُبنى بألوان المظهر السابق: خلفيّةٌ
// نهاريّةٌ وأسماءٌ ليليّة. وقع في تطبيق الراكب بعد «إصلاحه» — نُقل المستمعُ إلى `useLayoutEffect` وبقي التبديلُ حيث كان، **والحسابُ أخضر**.
// فيُقرأ هنا: الأثرُ الذي يبدّل `dark` على الجذر يجب أن يكون `useLayoutEffect`. **ولا يقيس الرسمَ نفسَه** — ذاك للّقطات
const THEME = join(ROOT, "src/lib/theme.tsx");
if (!existsSync(THEME)) failures.push("src/lib/theme.tsx غائب — ترتيبُ المظهر لم يُقس");
else {
  const source = readFileSync(THEME, "utf8");
  const at = source.search(/classList\.toggle\(\s*"dark"/);
  if (at < 0) failures.push("theme.tsx: لا تبديلَ لصنف `dark` على الجذر — ترتيبُ المظهر لم يُقس");
  else {
    const before = source.slice(0, at);
    const hook = [...before.matchAll(/\b(useLayoutEffect|useEffect)\s*\(/g)].pop()?.[1];
    if (hook !== "useLayoutEffect") failures.push(`theme.tsx: صنفُ \`dark\` يُبدَّل في ${hook ?? "؟"} — يجب \`useLayoutEffect\` فيسبق أثرَ الخريطة (وإلا نهاريّةٌ في الليل)`);
    else console.log("  ترتيبُ المظهر: صنفُ `dark` في useLayoutEffect ✓");
  }
}

console.log(`  تباينُ المظهرين: ${mapChecked} زوجاً من ألوان الخريطة · ${rulesChecked} قاعدةً×مظهر`);
if (mapChecked === 0) failures.push("لم يُقرأ أيُّ لونٍ للخريطة — الرموزُ غائبةٌ أو تغيّر موضعُها (لم يُقس ≠ سليم)");
if (failures.length) {
  console.error(`\n✗ ${failures.length} تباينٍ ناقص:\n  ` + failures.join("\n  "));
  process.exit(1);
}
console.log("  ✓ كلُّ نصٍّ مقروءٌ في المظهرين بالحدود أعلاه.");
