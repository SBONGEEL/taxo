#!/usr/bin/env node
/**
 * **حزمةُ اللقطات** — `node tools/screens/prepare-dist.mjs <app>` يبني `<app>/dist-screens` من الشيفرة نفسِها:
 *
 *   · `VITE_API_BASE_URL=http://127.0.0.1:8787` — خادمُ اللقطات (`server.mjs`) لا الإنتاجُ ولا التطوير؛
 *   · `harness.js` أوّلَ `<head>` — يضغط ويكتب بأوامرَ من الخادم.
 *
 * **ويتخطّى حرّاسَ البناء بقصدٍ مكتوب**: `check:dist` يرفض العنوانَ المحلّيَّ في حزمة — وهذه الحزمةُ **لا تُشحن أبداً**: لا تدخل
 * متجراً ولا غلافاً منشوراً، وتعيش في وظيفة `screens` ثمّ تُرمى. فيُبنى بـ`vite build` وحدَه، والحرّاسُ يحرسون الحزمَ المشحونة
 * في وظيفة `web` من التشغيل نفسِه.
 */
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const app = process.argv[2];
if (!["customer-app", "driver-app"].includes(app)) {
  console.error("الاستعمال: node tools/screens/prepare-dist.mjs <customer-app|driver-app>");
  process.exit(2);
}
const dir = join(root, app);
const out = join(dir, "dist-screens");
execFileSync(process.platform === "win32" ? "npx.cmd" : "npx", ["vite", "build", "--outDir", "dist-screens", "--emptyOutDir"], {
  cwd: dir,
  stdio: "inherit",
  env: { ...process.env, VITE_API_BASE_URL: "http://127.0.0.1:8787", TAXO_CHANNEL: "test" },
});
copyFileSync(join(root, "tools", "screens", "harness.js"), join(out, "__harness.js"));
const index = join(out, "index.html");
const html = readFileSync(index, "utf8");
if (!html.includes("<head>")) throw new Error("لا <head> في index.html");
writeFileSync(index, html.replace("<head>", '<head><script src="/__harness.js"></script>'));
// **صفحةُ قياس ملحق العربيّة** (أمرُ المالك ٢٠٢٦-١١-١٨) — MapLibre من حزمة التطبيق المثبَّتة نفسِها، والملحقُ من `/vendor/` كما في `lib/map-rtl.ts`
const rtl = join(out, "__rtl");
mkdirSync(rtl, { recursive: true });
copyFileSync(join(root, "tools", "screens", "rtl-test.html"), join(rtl, "index.html"));
for (const f of ["maplibre-gl.js", "maplibre-gl.css"]) copyFileSync(join(dir, "node_modules", "maplibre-gl", "dist", f), join(rtl, f));
console.log(`✓ ${app}/dist-screens — يخاطب 127.0.0.1:8787، والمُشغِّلُ محقون`);
