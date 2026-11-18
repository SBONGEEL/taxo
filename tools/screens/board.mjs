#!/usr/bin/env node
/**
 * **لوحةُ المقارنة** — `node tools/screens/board.mjs <app> <dir> <light|dark>` يكتب `<dir>/board-<app>-<mode>.html`.
 *
 * صفٌّ لكلِّ شاشة: **أندرويد · iPhone الكبير · iPhone الصغير** — كلُّها لقطاتٌ حقيقيّةٌ من المحاكيات (`steps.mjs`)، **لا رسمٌ ولا توليد**.
 * وتحت كلِّ صفٍّ اسمُه بالعربيّة، **وما لم يُبلغ يُقال «لم يُبلغ» بعلّته** من `steps.json` لا يُخفى.
 * والصورةُ النهائيّةُ يصوّرها Chrome على Linux (`ios.yml › screens-board`) — فالعربيّةُ تُشكَّل كما يشكّلها المتصفّح.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [app, dir, mode] = process.argv.slice(2);
const COLUMNS = [
  { key: "android", title: "أندرويد" },
  { key: "ios-large", title: "iPhone 17 Pro Max" },
  { key: "ios-small", title: "iPhone SE" },
];
const logs = Object.fromEntries(
  COLUMNS.map((c) => {
    const f = join(dir, c.key, "steps.json");
    return [c.key, existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : []];
  }),
);
if (mode === "iphone") {
  iphoneBoard();
  process.exit(0);
}
const order = (logs["ios-large"].length ? logs["ios-large"] : logs.android).filter((s) => s.theme === mode);
const dark = mode === "dark";
const title = `${app === "driver-app" ? "تطبيقُ الكبتن" : "تطبيقُ الراكب"} — ${dark ? "الوضعُ الليليّ" : "الوضعُ النهاريّ"}`;

const rows = order
  .map((step) => {
    const cells = COLUMNS.map((c) => {
      const s = logs[c.key].find((x) => x.theme === mode && x.name === step.name);
      const img = s && existsSync(join(dir, c.key, s.file)) ? `<img src="${c.key}/${s.file}">` : `<div class="miss">لا لقطة</div>`;
      const note = s && !s.reached ? `<div class="warn">لم يُبلغ: ${s.notes.filter((n) => n.includes("✗")).join(" · ")}</div>` : "";
      return `<figure><figcaption class="col">${c.title}</figcaption>${img}${note}</figure>`;
    }).join("");
    return `<section><div class="row">${cells}</div><h2>${step.label}</h2></section>`;
  })
  .join("");

writeFileSync(
  join(dir, `board-${app}-${mode}.html`),
  `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
body{margin:0;padding:32px;background:${dark ? "#0E1013" : "#F4F5F7"};color:${dark ? "#F2F3F5" : "#171B20"};font-family:"Noto Sans Arabic","Noto Naskh Arabic",sans-serif}
h1{font-size:34px;margin:0 0 24px}h2{font-size:26px;margin:10px 0 36px;text-align:center}
.row{display:flex;gap:28px;justify-content:center;align-items:flex-start;direction:ltr}
figure{margin:0;display:flex;flex-direction:column;align-items:center}
.col{font-size:18px;opacity:.75;margin-bottom:8px}
img{height:720px;border-radius:22px;box-shadow:0 4px 18px rgba(0,0,0,.25)}
.miss{height:720px;width:330px;display:grid;place-items:center;border:2px dashed #888;border-radius:22px}
.warn{max-width:330px;color:#D81B73;font-size:15px;margin-top:6px;direction:rtl}
</style></head><body><h1>${title}</h1>${rows}
<p style="opacity:.7;font-size:16px">لقطاتٌ حقيقيّةٌ من محاكي iPhone ومحاكي أندرويد بالحزمة نفسِها ووضع الضيف (بياناتُ العرض) — لا رسم.</p></body></html>`,
);
console.log(`✓ board-${app}-${mode}.html — ${order.length} شاشة`);

/**
 * **لوحةُ iPhone — واحدةٌ لكلِّ تطبيق** (أمرُ المالك ٢٠٢٦-١١-١٨): `node tools/screens/board.mjs <app> <dir> iphone`
 *
 * شاشاتُ التطبيق صفّاً صفّاً: **Pro Max نهاراً وليلاً · SE نهاراً وليلاً**، ثمّ **ما يرسمه iOS نفسُه** (`native-run.sh`):
 * Dynamic Island والقفلُ والاختصاراتُ والأدواتُ والمكالمة — على الجهازين. وما لم يُلتقط يُقال لماذا تحته، لا يُخفى.
 */
function iphoneBoard() {
  const read = (f) => (existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : []);
  const large = read(join(dir, "ios-large", "steps.json"));
  const small = read(join(dir, "ios-small", "steps.json"));
  const cell = (col, title, s) => {
    const img = s && s.file && existsSync(join(dir, col, s.file)) ? `<img src="${col}/${s.file}">` : `<div class="miss">لا لقطة</div>`;
    const notes = (s && s.notes) || [];
    const bad = notes.filter((n) => n.includes("✗"));
    const why = s && !s.reached ? `<div class="warn">${s.file ? "لم يُبلغ: " : ""}${(bad.length ? bad : notes).join(" · ")}</div>` : "";
    return `<figure><figcaption class="col">${title}</figcaption>${img}${why}</figure>`;
  };
  const names = [...new Set([...large, ...small].filter((s) => s.theme === "light").map((s) => s.name))];
  const appRows = names
    .map((name) => {
      const pick = (log, theme) => log.find((x) => x.theme === theme && x.name === name);
      const label = (pick(large, "light") || pick(small, "light")).label;
      const cells = [
        cell("ios-large", "Pro Max · نهاريّ", pick(large, "light")),
        cell("ios-large", "Pro Max · ليليّ", pick(large, "dark")),
        cell("ios-small", "SE · نهاريّ", pick(small, "light")),
        cell("ios-small", "SE · ليليّ", pick(small, "dark")),
      ].join("");
      return `<section><div class="row">${cells}</div><h2>${label}</h2></section>`;
    })
    .join("");
  const nl = read(join(dir, "ios-large", "native", "native.json"));
  const ns = read(join(dir, "ios-small", "native", "native.json"));
  const nativeNames = [...new Set([...nl, ...ns].map((s) => s.name))];
  const nativeRows = nativeNames
    .map((name) => {
      const a = nl.find((x) => x.name === name);
      const b = ns.find((x) => x.name === name);
      const fix = (s) => (s && s.file ? { ...s, file: `native/${s.file}` } : s);
      const cells = [cell("ios-large", "iPhone 17 Pro Max", fix(a)), cell("ios-small", "iPhone SE", fix(b))].join("");
      return `<section><div class="row">${cells}</div><h2>${(a || b).label}</h2></section>`;
    })
    .join("");
  const title = app === "driver-app" ? "تطبيقُ الكبتن على iPhone" : "تطبيقُ الراكب على iPhone";
  writeFileSync(
    join(dir, `board-${app}-iphone.html`),
    `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
body{margin:0;padding:32px;background:#F4F5F7;color:#171B20;font-family:"Noto Sans Arabic","Noto Naskh Arabic",sans-serif}
h1{font-size:36px;margin:0 0 8px}h3{font-size:30px;margin:40px 0 20px;border-top:3px solid #D81B73;padding-top:16px}
h2{font-size:24px;margin:8px 0 30px;text-align:center}
.row{display:flex;gap:22px;justify-content:center;align-items:flex-start;direction:ltr}
figure{margin:0;display:flex;flex-direction:column;align-items:center}
.col{font-size:17px;opacity:.75;margin-bottom:6px}
img{height:600px;border-radius:20px;box-shadow:0 4px 18px rgba(0,0,0,.25)}
.miss{height:600px;width:280px;display:grid;place-items:center;border:2px dashed #888;border-radius:20px}
.warn{max-width:300px;color:#D81B73;font-size:14px;margin-top:6px;direction:rtl}
</style></head><body><h1>${title}</h1>
<p style="opacity:.75;font-size:17px;margin:0">لقطاتٌ حقيقيّةٌ من محاكي iPhone على أجهزة GitHub — بياناتُ تجربةٍ ووضعُ الضيف، لا مستخدمَ حقيقيّ ولا رسم.</p>
<h3>شاشاتُ التطبيق</h3>${appRows}<h3>ما يرسمه iOS: الأداةُ والقفلُ وDynamic Island والاختصاراتُ والمكالمة</h3>${nativeRows}</body></html>`,
  );
  console.log(`✓ board-${app}-iphone.html — ${names.length} شاشة و${nativeNames.length} من النظام`);
}
