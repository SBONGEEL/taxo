// check:mic-gate — **زرُّ «اتصال» في الغلاف لا يَعِد بما لا يقع** (SPEC §٦٦-د/٨، ٢٠٢٦-١٠-٠٨).
//
// **العلّة**: الويب‌فيو لا يبلغ الميكروفونَ في حزمةٍ لا تعلن `RECORD_AUDIO`، و`getUserMedia` قائمةٌ فيها وتُرفض عند النداء.
// **وكانت البوّابةُ رقمَ بناء** (`CALLS_MIN_NATIVE_BUILD = 759`) — **والرقمُ عددُ إيداعاتِ الفرع الذي بُنيت منه الحزمة**: قِيس يومَ
// كُتب فإذا `master` ٧٦٢ وفرعُ إعادة التصميم ٧٦٣ **وليس في بيانَي أيٍّ منهما الإذن** — فكلُّ حزمةٍ تُبنى منهما اليوم تجتاز البوّابة.
// **فصارت البوّابةُ علامةً تُشحن مع البيان** (`capacitor.config.ts → android.appendUserAgent`)، وهذا يقيس أنهما لا يفترقان.
//
// **ما يُقاس، لكلٍّ من التطبيقين:**
//   ١) **`src/lib/mic-gate.ts` يقرأ العلامةَ لا رقماً**: `CALLS_SHELL_MARK` معرَّفة، **ولا `App.getInfo` ولا `CALLS_MIN_NATIVE_BUILD`**.
//   ٢) **`capacitor.config.ts` يُلحق العلامةَ نفسَها حرفاً** (`appendUserAgent`) — علامةٌ في الشيفرة غيرُ التي يُلحقها الغلافُ تُطفئ
//      الزرَّ في كلِّ حزمة.
//   ٣) **البيانُ يعلن `RECORD_AUDIO` ⇔ الغلافُ يُلحق العلامة** — علامةٌ بلا إذنٍ زرٌّ بلا باب، وإذنٌ بلا علامةٍ زرٌّ غائبٌ بلا علّة.
//   ٤) **والبوّابةُ نسخةٌ واحدةٌ في التطبيقين بايتاً**.
//
// **وحدُّه مكتوبٌ فيه**: يقرأ الشجرةَ لا الحزمة — **لا يعرف ما في حزمةٍ بُنيت** (`assets/capacitor.config.json` وبيانُها؛ ذاك
// لِـ`check-apk` حين تُبنى)، ولا يقيس أنّ الويب‌فيو يُلحق العلامةَ فعلاً (`Bridge.java` يفعل؛ يُقاس على الهاتف مع أوّل حزمة).

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const APPS = ["customer-app", "driver-app"];

const failures = [];
const gates = [];
let measured = 0;

for (const app of APPS) {
  const gatePath = join(ROOT, app, "src", "lib", "mic-gate.ts");
  const configPath = join(ROOT, app, "capacitor.config.ts");
  const manifestPath = join(ROOT, app, "android", "app", "src", "main", "AndroidManifest.xml");
  const missing = [gatePath, configPath, manifestPath].filter((path) => !existsSync(path));
  if (missing.length) {
    failures.push(`${app}: غائب — ${missing.map((path) => path.slice(ROOT.length)).join(" · ")}`);
    continue;
  }
  const gate = readFileSync(gatePath, "utf8");
  gates.push([app, gate]);
  const config = readFileSync(configPath, "utf8");
  // **الأسطرُ لا التعليقات** — اسمٌ في تعليقٍ يشرح لمَ نُزع ليس استعمالاً
  const code = (text) =>
    text
      .split("\n")
      .filter((line) => !/^\s*(\/\/|\*|\/\*\*)/.test(line))
      .join("\n");
  const manifest = readFileSync(manifestPath, "utf8").replace(/<!--[\s\S]*?-->/g, "");

  // ١) العلامةُ لا الرقم
  const mark = code(gate).match(/export const CALLS_SHELL_MARK = "([^"]+)";/)?.[1] ?? null;
  if (!mark) failures.push(`${app}/src/lib/mic-gate.ts: لا \`export const CALLS_SHELL_MARK = "…"\` — بأيِّ شيءٍ يُعرف الغلافُ الذي يحمل الإذن؟`);
  if (/\bApp\.getInfo\b|\bCALLS_MIN_NATIVE_BUILD\b/.test(code(gate))) {
    failures.push(
      `${app}/src/lib/mic-gate.ts: البوّابةُ تقرأ رقمَ البناء — والرقمُ عددُ إيداعاتِ الفرع، فحزمةٌ بلا إذنٍ تجتازها (٧٦٢ و٧٦٣ يومَ قِيس)`,
    );
  }

  // ٢) الغلافُ يُلحق العلامةَ نفسَها
  const appended = code(config).match(/appendUserAgent:\s*"([^"]+)"/)?.[1] ?? null;
  if (mark && appended && appended !== mark) {
    failures.push(`${app}: الغلافُ يُلحق «${appended}» والبوّابةُ تبحث عن «${mark}» — فلا يظهر «اتصال» في أيِّ حزمة`);
  }

  // ٣) الإذنُ ⇔ العلامة
  const recordAudio = /<uses-permission\s+android:name="android\.permission\.RECORD_AUDIO"\s*\/>/.test(manifest);
  if (recordAudio && !appended) {
    failures.push(`${app}: البيانُ يعلن \`RECORD_AUDIO\` والغلافُ لا يُلحق العلامة — «اتصال» غائبٌ في حزمةٍ تملك الميكروفون`);
  }
  if (!recordAudio && appended) {
    failures.push(`${app}: الغلافُ يُلحق «${appended}» والبيانُ لا يعلن \`RECORD_AUDIO\` — «اتصال» يظهر و\`getUserMedia\` تُرفض`);
  }
  measured += 1;
}

// ٤) نسخةٌ واحدة
if (gates.length === 2 && gates[0][1] !== gates[1][1]) {
  failures.push("src/lib/mic-gate.ts يفترق بين التطبيقين — والبوّابةُ واحدةٌ بايتاً");
}

if (measured === 0) failures.push("لم يُقس تطبيقٌ واحد — صفرٌ مقيسٌ سقوطٌ لا سلامة");

if (failures.length) {
  console.error(`✗ check:mic-gate — ${failures.length}`);
  for (const line of failures) console.error(`  ${line}`);
  process.exit(1);
}
console.log(`✓ check:mic-gate — التطبيقان (${measured}): البوّابةُ علامةُ الغلاف لا رقمُ البناء، والعلامةُ والإذنُ معاً، ونسخةٌ واحدة.`);
