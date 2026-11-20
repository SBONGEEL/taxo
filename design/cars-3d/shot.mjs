// node shot.mjs board1.html out.png [width] — لقطةُ صفحةٍ كاملة
import { createRequire } from "module";
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [page0, out, width = "1800"] = process.argv.slice(2);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".webp": "image/webp", ".png": "image/png", ".svg": "image/svg+xml", ".css": "text/css", ".woff2": "font/woff2", ".ttf": "font/ttf" };
const server = http.createServer((req, res) => {
  const f = path.join(HERE, decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, ""));
  if (!f.startsWith(HERE) || !fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { "content-type": TYPES[path.extname(f)] ?? "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: Number(width), height: 1000 }, deviceScaleFactor: 1 });
page.on("pageerror", (e) => console.log("PAGEERR", e.message));
await page.goto(`http://127.0.0.1:${server.address().port}/${page0}`);
await page.evaluate(() => window.BOARD_READY);
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: path.resolve(out), fullPage: true, type: out.endsWith(".jpg") ? "jpeg" : "png", quality: out.endsWith(".jpg") ? 88 : undefined });
await browser.close();
server.close();
console.log("saved", out);
