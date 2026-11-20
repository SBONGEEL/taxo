// node render.mjs [keys...] — يصوّر السيارات من المصدر الواحد (cars.js) إلى out/
import { createRequire } from "module";
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, "out");
fs.mkdirSync(OUT, { recursive: true });

const TYPES = { ".html": "text/html", ".js": "text/javascript" };
const server = http.createServer((req, res) => {
  const f = path.join(HERE, decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "") || "index.html");
  if (!f.startsWith(HERE) || !fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": TYPES[path.extname(f)] ?? "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const port = server.address().port;

const ALL = ["economy", "comfort", "vip", "hatchback", "suv", "family", "van", "city_taxi", "women"];
const args = process.argv.slice(2);
const quick = args.includes("--quick");
const keys = args.filter((a) => !a.startsWith("--"));
const list = keys.length ? keys : ALL;
const TOP_COLORS = { white: 0xf3f4f6, black: 0x16181d, silver: 0xb9bdc4, gray: 0x6b7079, red: 0xb3262b, blue: 0x2a4f8f };

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("PAGE", m.text()); });
page.on("pageerror", (e) => console.log("PAGEERR", e.message));
await page.goto(`http://127.0.0.1:${port}/index.html`);
await page.waitForFunction(() => window.TAXO_READY === true && typeof window.finish === "function");

const save = (name, dataUrl) => fs.writeFileSync(path.join(OUT, name), Buffer.from(dataUrl.split(",")[1], "base64"));

for (const key of list) {
  for (const theme of quick ? ["day"] : ["day", "night"]) {
    const t0 = Date.now();
    const raw = await page.evaluate((o) => window.TAXO_CARS.shoot(o), { key, view: "three-quarter", theme, width: quick ? 1200 : 2400, height: quick ? 750 : 1500 });
    const outs = await page.evaluate(([u]) => window.finish(u, { aspect: 1.6, pad: 0.04, sizes: [1280, 640, 320, 160] }), [raw]);
    for (const [w, d] of Object.entries(outs)) save(`${key}-34-${theme}-${w}.webp`, d);
    const png = await page.evaluate(([u]) => window.finish(u, { aspect: 1.6, pad: 0.04, sizes: [1280], type: "image/png" }), [raw]);
    save(`${key}-34-${theme}-1280.png`, png[1280]);
    console.log(key, theme, "3/4", Date.now() - t0, "ms");
  }
  if (!quick) {
    for (const [name, color] of Object.entries(TOP_COLORS)) {
      const raw = await page.evaluate((o) => window.TAXO_CARS.shoot(o), { key, view: "top", theme: "day", bodyColor: color, width: 800, height: 800 });
      const outs = await page.evaluate(([u]) => window.finish(u, { aspect: 0.5, pad: 0.06, sizes: [192, 96, 48] }), [raw]);
      for (const [w, d] of Object.entries(outs)) save(`${key}-top-${name}-${w}.webp`, d);
      const png = await page.evaluate(([u]) => window.finish(u, { aspect: 0.5, pad: 0.06, sizes: [192], type: "image/png" }), [raw]);
      save(`${key}-top-${name}-192.png`, png[192]);
    }
    console.log(key, "top ok");
  }
}
await browser.close();
server.close();
