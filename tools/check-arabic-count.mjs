#!/usr/bin/env node
/**
 * check:arabic-count — **لا عددَ مكتوباً في القالب قبل معدوده** (أمرُ المالك ٢٠٢٦-١١-٢٥).
 *
 * **العلّة**: «يتبقّى {0} أيام» يثبّت صيغةً واحدةً لكلِّ عدد — تصدق على ٣–١٠ وتكذب على غيرها، **فرأى المالكُ «يتبقّى 1 أيام» على
 * هاتف كبتن**. وكان في التطبيقين عشرون قالباً بهذا الشكل. **والقاعدة**: القالبُ يحمل المعدودَ كاملاً («يتبقّى {0}»)، ويصوغه
 * `countOf` من `lib/arabic-count.ts` («يوم واحد» · «يومان» · «3 أيام» · «11 يوماً»).
 *
 * **ما يقيسه**: (١) نسختا `lib/arabic-count.ts` في التطبيقين **متطابقتان بايتاً**؛ (٢) لا حرفيّةَ فيها `{x}` يليها معدودٌ من
 * الخمسة (يوم · ساعة · دقيقة · رحلة · نقطة) **إلا في موضعٍ مصرَّحٍ بعلّته** أدناه — دالّةٌ تفرّع على العدد نفسِه، أو ثابتٌ عددُه
 * معروفٌ وصيغتُه صحيحةٌ له.
 *
 * **وما لا يقيسه — مكتوبٌ لا مسكوتٌ عنه**: النصوصَ المبنيّةَ بجمع سلاسل (`n + " يوم"`)، **ومعدوداتٍ غيرَ الخمسة**، ونصوصَ الخلفيّة
 * (لها `tests/test_arabic_count.py`)، **ولا يسأل أصحيحٌ نحوُ الجملة حول العدد**.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app"];
const UNIT = "(?:أيام|يوماً|يوم|ساعات|ساعةً|ساعة|دقائق|دقيقةً|دقيقة|رحلاتٍ|رحلات|رحلةً|رحلة|نقاط|نقطةً|نقطة)";
const TEMPLATE = new RegExp(`\\{\\w+\\}\\s+${UNIT}(?![\\u0600-\\u06FF])`, "u");

/** **مواضعُ مصرَّحةٌ بعلّتها** — `ملفٌّ نسبيٌّ إلى src` ⇐ العلّة. */
const ALLOWED = {
  "lib/arabic-count.ts": "بيتُ الصيغ نفسُه",
  "screens/t2/count.ts": "دوالُّ تفرّع على العدد (١ · ٢ · ٣–١٠ · فوقها)",
  "screens/t2/HourlyT2.tsx": "دالّةٌ تفرّع على العدد",
  "lib/hourly.ts": "دالّةٌ تفرّع على العدد",
  "lib/bookings.ts": "دوالُّ تفرّع على العدد",
  "screens/t2/UnconfirmedT2.tsx": "دالّةٌ تفرّع على العدد",
  "screens/t2/PayRequestT2.tsx": "`CARD_PAGE_MINUTES` ثابتٌ = 5 ⇐ «5 دقائق» صحيحة",
  "lib/deletion-text.ts": "`GRACE_DAYS` ثابتٌ = 30 ⇐ «30 يوماً» صحيحة",
  "screens/CliqSubscription.tsx": "تعليقٌ يقتبس نصَّ اللوحة لا نصٌّ يُرسم",
};

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name) && !/\.test\./.test(entry.name)) out.push(full);
  }
  return out;
}

let failed = 0;
const copies = APPS.map((app) => fs.readFileSync(path.join(ROOT, app, "src/lib/arabic-count.ts")));
if (!copies[0].equals(copies[1])) {
  console.error("✗ check:arabic-count — نسختا lib/arabic-count.ts في التطبيقين مختلفتان (تُنسخ بايتاً)");
  failed += 1;
}

let scanned = 0;
for (const app of APPS) {
  const src = path.join(ROOT, app, "src");
  for (const file of walk(src)) {
    scanned += 1;
    const rel = path.relative(src, file).split(path.sep).join("/");
    if (rel in ALLOWED) continue;
    const lines = fs.readFileSync(file, "utf8").split("\n");
    lines.forEach((line, index) => {
      if (/^\s*(\*|\/\/)/.test(line)) return;
      if (TEMPLATE.test(line)) {
        console.error(`✗ ${app}/src/${rel}:${index + 1} — عددٌ في القالب قبل معدوده: ${line.trim().slice(0, 140)}`);
        console.error("    اكتب المعدودَ كاملاً في القالب («يتبقّى {0}») واصغه بـcountOf(n, DAYS) من @/lib/arabic-count");
        failed += 1;
      }
    });
  }
}

// **إثباتُ أن المسحَ رأى شيئاً** — مسحٌ أعمى يخرج أخضر
if (scanned < 200) {
  console.error(`✗ check:arabic-count — لم يُقرأ إلا ${scanned} ملفّاً — المسحُ أعمى`);
  failed += 1;
}

if (failed) process.exit(1);
console.log(`✓ check:arabic-count — ${scanned} ملفّاً، ولا عددَ في قالبٍ قبل معدوده خارج المواضع المصرَّحة (${Object.keys(ALLOWED).length})`);
