// node render-skins.mjs <manifest.json> <outdir> — رسومُ متجر المركبات (العاديّة والمميّزة) بلون كلِّ مركبة
import { createRequire } from "module";
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [manifestPath, outDir] = process.argv.slice(2);
const rows = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
fs.mkdirSync(outDir, { recursive: true });
const SHELL = { sedan: "economy", hatch: "hatchback", suv: "suv", van: "van", coupe: "coupe", pickup: "pickup" };
const server = http.createServer((req, res) => {
  const f = path.join(HERE, decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "") || "index.html");
  if (!f.startsWith(HERE) || !fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": f.endsWith(".js") ? "text/javascript" : "text/html" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("PAGEERR", e.message));
await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
await page.waitForFunction(() => window.TAXO_READY === true && typeof window.finish === "function");
const save = (name, d) => fs.writeFileSync(path.join(outDir, name), Buffer.from(d.split(",")[1], "base64"));
for (const row of rows) {
  if (!["common", "premium"].includes(row.rarity)) { console.log("skip", row.key, row.rarity); continue; }
  const key = SHELL[row.shell];
  if (!key) throw new Error("shell " + row.shell);
  const bodyColor = parseInt(row.body.slice(1), 16);
  const raw = await page.evaluate((o) => window.TAXO_CARS.shoot(o), { key, view: "three-quarter", theme: "day", bodyColor, width: 1600, height: 1000 });
  const st = await page.evaluate(([u]) => window.finish(u, { aspect: 1.6, pad: 0.04, sizes: [640], quality: 0.88 }), [raw]);
  save(`${row.key}-store.webp`, st[640]);
  const rawTop = await page.evaluate((o) => window.TAXO_CARS.shoot(o), { key, view: "top", theme: "day", bodyColor, width: 800, height: 800 });
  const mp = await page.evaluate(([u]) => window.finish(u, { aspect: 1, pad: 0.04, sizes: [256], quality: 0.9 }), [rawTop]);
  save(`${row.key}-map.webp`, mp[256]);
  console.log(row.key, row.rarity, key);
}
await browser.close();
server.close();
