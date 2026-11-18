/** **كلُّ خريطةٍ في التطبيقين واللوحة تمرّ بحارس النسبة** (أمرُ المالك ١٨/١١ السابع، المهمّة ١-٥) — والسلوكُ نفسُه يُقاس في متصفّحٍ
 *  بـ`tools/check-attribution` (وظيفةُ CI «نسبةُ الخريطة»). هنا ما لا يراه المتصفّح: **أنّ كلَّ شاشة خريطةٍ تنادي الحارس**،
 *  وأنّ نسخَه الثلاثَ واحدة. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../../", import.meta.url).pathname;
const APPS = ["customer-app", "driver-app", "admin-panel"];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

test("كلُّ `new …Map(` بلا نسبةِ المكتبة الافتراضيّة، ومعها الحارس", () => {
  const missing: string[] = [];
  let maps = 0;
  for (const app of APPS) {
    for (const path of files(join(ROOT, app, "src"))) {
      // **الشيفرةُ لا التعليق** — `map-rtl.ts` يذكر `new mapboxgl.Map({ language })` في تعليقٍ يشرحه
      const source = readFileSync(path, "utf8")
        .split("\n")
        .filter((line) => !/^\s*(\*|\/\/|\/\*)/.test(line))
        .join("\n");
      if (!/new\s+[\w.]*\.Map\(\s*\{/.test(source)) continue;
      maps += 1;
      if (!source.includes("attributionControl: false")) missing.push(`${path}: بلا attributionControl: false`);
      if (!source.includes("foldedAttribution(")) missing.push(`${path}: بلا foldedAttribution`);
    }
  }
  assert.ok(maps >= 8, `وُجدت ${maps} خرائط فقط — أتغيّر شكلُ البناء فعمي الفحص؟`);
  assert.deepEqual(missing, []);
});

test("نسخُ الحارس الثلاثُ متطابقةٌ بايتاً", () => {
  const [first, ...rest] = APPS.map((app) => readFileSync(join(ROOT, app, "src/lib/map-attribution.ts")));
  for (const copy of rest) assert.ok(first.equals(copy), "map-attribution.ts افترق بين التطبيقات");
});
