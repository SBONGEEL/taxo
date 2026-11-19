// **مبلغٌ يُرسم بلا عملته** (اختبارُ طلب الرحلة ٢٠٢٦-١١-١٩) — `formatMoney(x)` بمعاملٍ واحدٍ يكمل ثلاثَ خاناتٍ في كلِّ سوق، فقرأ الراكبُ في
// الأردن «المتبقي 1.800» فوق «الأجرة النهائية 1.80». والرقمُ وحدَه بجانب علامةٍ مرسومةٍ له `formatAmount(x, currency)`.
// والعدُّ بالأقواس لا بنمطٍ نصّيّ: المعاملُ الأوّلُ قد يحمل فواصلَ داخل أقواسه.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? files(path) : /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

test("لا formatMoney بمعاملٍ واحد في الشجرة", () => {
  const src = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
  const found: string[] = [];
  for (const file of files(src)) {
    const text = readFileSync(file, "utf8");
    let at = 0;
    while ((at = text.indexOf("formatMoney(", at)) >= 0) {
      if (text.slice(Math.max(0, at - 9), at) === "function ") {
        at += 12;
        continue;
      }
      let depth = 0;
      let commas = 0;
      let end = at + 11;
      for (; end < text.length; end++) {
        const c = text[end];
        if ("([{".includes(c)) depth++;
        else if (")]}".includes(c)) {
          depth--;
          if (depth === 0) break;
        } else if (c === "," && depth === 1) commas++;
      }
      if (commas === 0) found.push(`${file}:${text.slice(0, at).split("\n").length}`);
      at = end;
    }
  }
  assert.deepEqual(found, []);
});
