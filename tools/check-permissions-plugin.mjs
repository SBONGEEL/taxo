/** **ملحقُ الأذونات منسوخٌ في التطبيقين — فيُقاس بايتاً** (SPEC §١٠٣ المرحلة A/28).
 *
 * نسختان لملفٍّ واحدٍ تفترقان أوّلَ ما يُصلح عطبٌ في إحداهما — **فتعرض صفحةُ الأذونات في الراكب حالاً لا تعرضها في الكبتن**.
 * يُقارن الملفّان بعد حذف سطر الحزمة وحدَه، **وأيُّ فرقٍ آخرَ يُسقط**. ولا يقيس سلوكَ الملحق على هاتف — ذاك على المحاكي.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const FILES = [
  "driver-app/android/app/src/main/java/ly/tajora/driver/PermissionsPlugin.java",
  "customer-app/android/app/src/main/java/ly/tajora/rider/PermissionsPlugin.java",
];
const body = (f) => readFileSync(join(ROOT, f), "utf8").replace(/^package [\w.]+;\n/m, "");
const [a, b] = FILES.map(body);
if (a !== b) {
  const la = a.split("\n"), lb = b.split("\n");
  const at = la.findIndex((line, i) => line !== lb[i]);
  console.error(`✗ check:permissions-plugin — النسختان تفترقان عند السطر ${at + 2}:\n  الكبتن: ${la[at]}\n  الراكب: ${lb[at]}`);
  process.exit(1);
}
for (const f of FILES) {
  if (!/registerPlugin\(PermissionsPlugin\.class\)/.test(readFileSync(join(ROOT, dirname(f), "MainActivity.java"), "utf8"))) {
    console.error(`✗ check:permissions-plugin — ${dirname(f)}/MainActivity.java لا يسجّل الملحق — والويبُ ينادي فلا يجد`);
    process.exit(1);
  }
}
// **ومنطقُ الويب منسوخٌ بايتاً كذلك** — `lib/permissions-center.ts`: الأساسيّةُ والشرحُ والخطواتُ واحدةٌ في التطبيقين
const LIBS = ["driver-app/src/lib/permissions-center.ts", "customer-app/src/lib/permissions-center.ts"];
const [la, lb] = LIBS.map((f) => readFileSync(join(ROOT, f), "utf8"));
if (la !== lb) {
  console.error("✗ check:permissions-plugin — lib/permissions-center.ts يفترق بين التطبيقين؛ انسخ أحدهما فوق الآخر بعد قراءة الفرق");
  process.exit(1);
}
console.log("✓ check:permissions-plugin · ملحقُ الأذونات ومنطقُه واحدان في التطبيقين، والملحقُ مسجَّلٌ فيهما");
