/** **ملحقا الأذونات والمُطلِق منسوخان في التطبيقين — فيُقاسان بايتاً** (SPEC §١٠٣ المرحلة A).
 *
 * نسختان لملفٍّ واحدٍ تفترقان أوّلَ ما يُصلح عطبٌ في إحداهما — **فتعرض صفحةُ الأذونات في الراكب حالاً لا تعرضها في الكبتن**.
 * يُقارن كلُّ ملحقٍ بعد حذف سطر الحزمة وحدَه، **وأيُّ فرقٍ آخرَ يُسقط**؛ ويُشترط تسجيلُه في `MainActivity` (وإلا نادى الويبُ فلم يجد).
 * ومنطقُ الويب `lib/permissions-center.ts` يُقاس بايتاً كذلك. **ولا يقيس سلوكَ الملحق على هاتف** — ذاك على المحاكي.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const fail = (message) => {
  console.error(`✗ check:permissions-plugin — ${message}`);
  process.exit(1);
};
const body = (f) => readFileSync(join(ROOT, f), "utf8").replace(/^package [\w.]+;\n/m, "");

const PLUGINS = ["PermissionsPlugin", "LauncherPlugin"];
for (const name of PLUGINS) {
  const files = [
    `driver-app/android/app/src/main/java/ly/tajora/driver/${name}.java`,
    `customer-app/android/app/src/main/java/ly/tajora/rider/${name}.java`,
  ];
  const [a, b] = files.map(body);
  if (a !== b) {
    const la = a.split("\n");
    const lb = b.split("\n");
    const at = la.findIndex((line, i) => line !== lb[i]);
    fail(`${name}: النسختان تفترقان عند السطر ${at + 2}:\n  الكبتن: ${la[at]}\n  الراكب: ${lb[at]}`);
  }
  for (const f of files) {
    const main = readFileSync(join(ROOT, dirname(f), "MainActivity.java"), "utf8");
    if (!main.includes(`registerPlugin(${name}.class)`)) fail(`${dirname(f)}/MainActivity.java لا يسجّل ${name} — والويبُ ينادي فلا يجد`);
  }
}

// و`location-help.ts` (SPEC §١٠٩-ج): رسالةُ «لم نتمكن من تحديد موقعك» بنصّ المالك حرفاً — ومنسوخةٌ لا تفترق جملتُها بين التطبيقين
for (const lib of ["permissions-center.ts", "haptics.ts", "location-help.ts"]) {
  const [la, lb] = ["driver-app", "customer-app"].map((app) => readFileSync(join(ROOT, app, "src/lib", lib), "utf8"));
  if (la !== lb) fail(`lib/${lib} يفترق بين التطبيقين؛ انسخ أحدهما فوق الآخر بعد قراءة الفرق`);
}

console.log(`✓ check:permissions-plugin · ${PLUGINS.join(" و")} ومنطقُ الأذونات واحدةٌ في التطبيقين، ومسجَّلةٌ فيهما`);
