#!/usr/bin/env node
/**
 * **خادمُ لقطات الشاشات** (أمرُ المالك ٢٠٢٦-١١-١٧) — `node tools/screens/server.mjs <dist> [port]`
 *
 * **لا يخاطب الإنتاجَ ولا التطوير**: التطبيقُ في وضع الضيف (`demo/engine.ts`) يُجيب كلَّ نداءٍ من داخل الهاتف **إلا القراءاتِ العامّة**
 * (`/config` · `/auth/method` · `/public/*`) — وهذه وحدَها يُجيبها هذا الخادم: الإعداداتُ من لقطةٍ محفوظة (`config.JO.json`، بلا مفاتيح)،
 * وحكمُ الإصدار `open_map: true` (الخريطةُ الجديدة). **فالشاشاتُ هي الشاشاتُ الحقيقيّة** والبياناتُ بياناتُ العرض المكتوبةُ في الحزمة.
 *
 * ويخدم أيضاً:
 *   · **الحزمةَ نفسَها** على `/` — لغلاف أندرويد (يحمّل الواجهةَ من عنوانٍ كما يفعل في الحقيقة)؛
 *   · **`/__shot`** — أمرُ اللقطة التالية يقرؤه المُشغِّلُ في الصفحة (`harness.js`)، و`POST /__shot` يضعه سكربتُ CI، و`/__shot/ack` جوابُه.
 *
 * **ولا يُشحن**: الحزمةُ التي تنادي `127.0.0.1` تُبنى في وظيفة اللقطات وحدَها ولا تصل متجراً (`ios.yml › screens`).
 */
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const dist = process.argv[2];
const port = Number(process.argv[3] ?? 8787);
const config = JSON.parse(readFileSync(join(here, "config.JO.json"), "utf8"));

let command = { id: 0 };
let ack = { id: 0 };
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2", ".ttf": "font/ttf", ".mp3": "audio/mpeg", ".wav": "audio/wav" };

function send(res, status, body, type = "application/json") {
  res.writeHead(status, {
    "Content-Type": type,
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "Cache-Control": "no-store",
  });
  res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve) => {
    let raw = "";
    req.on("data", (chunk) => (raw += chunk));
    req.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        resolve({});
      }
    });
  });
}

createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const path = url.pathname;
  if (req.method === "OPTIONS") return send(res, 204, "");

  if (path === "/__shot" && req.method === "GET") return send(res, 200, command);
  if (path === "/__shot" && req.method === "POST") {
    command = { ...(await readBody(req)), id: command.id + 1 };
    return send(res, 200, command);
  }
  if (path === "/__shot/ack" && req.method === "POST") {
    ack = await readBody(req);
    console.log(`  ↩ ${ack.id} ${ack.ok ? "✓" : "✗"} ${ack.note ?? ""}`);
    return send(res, 200, {});
  }
  if (path === "/__shot/ack") return send(res, 200, ack);
  // **ملاحظاتُ صفحات القياس** (`rtl-test.html`) — سطرٌ في السجلّ يبدأ بـ`NOTE` فيُستخرج
  if (path === "/__note" && req.method === "POST") {
    console.log(`NOTE ${JSON.stringify(await readBody(req))}`);
    return send(res, 200, {});
  }

  if (path === "/api/v1/config") return send(res, 200, config);
  if (path === "/api/v1/public/app-version") {
    return send(res, 200, { state: "ok", latest_build: null, min_supported_build: null, download_url: null,
      release_notes: null, reminder_hours: null, open_map: true });
  }
  if (path === "/api/v1/auth/method") return send(res, 200, { method: "password" });
  if (path.startsWith("/api/")) {
    console.log(`  · ${req.method} ${path} → 404`);
    return send(res, 404, { detail: { code: "not_found", message: "screens-server" } });
  }

  // الحزمةُ — لغلاف أندرويد، ومسارُ تطبيقٍ بلا ملفٍّ يعود إلى index.html
  if (!dist) return send(res, 404, "no dist", "text/plain");
  let file = normalize(join(dist, decodeURIComponent(path)));
  if (!file.startsWith(normalize(dist)) || !existsSync(file) || statSync(file).isDirectory()) file = join(dist, "index.html");
  return send(res, 200, readFileSync(file), TYPES[extname(file)] ?? "application/octet-stream");
}).listen(port, "127.0.0.1", () => console.log(`✓ خادمُ اللقطات على 127.0.0.1:${port}${dist ? ` — والحزمة ${dist}` : ""}`));
