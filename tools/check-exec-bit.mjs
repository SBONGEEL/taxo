/** **سكربتٌ فقد بتَّ التنفيذ** — يوقف الإيداع ويسمّي الملفّ.
 *
 * ## العلّةُ مقيسةٌ مرّتين في يومٍ واحد
 *
 * تحريرُ ملفٍّ عبر `\\wsl.localhost` من ويندوز **يكتبه بصلاحية `644`** —
 * فيفقد `x`. **ولا شيءَ يشكو حتى يُشغَّل**:
 *
 * · `scripts/guards.sh` — سقط بـ`Permission denied` عند أوّل تشغيلٍ بعد تحرير.
 * · `scripts/deploy.sh` — سقط بـ`EXIT=126` **قبل أن تبدأ البوّابةُ الأولى**.
 *
 * **وهو عينُ العطب على الخادم**: `git` يحفظ نمطَ الملفّ، **فملفٌّ أُودع بلا
 * `x` يُسحب بلا `x`** — و`deploy.sh` يشغّل `scripts/pull-release.sh` على
 * الإنتاج، **فيسقط رفعٌ في منتصفه بـ126 لسببٍ لا علاقةَ له بالشيفرة**.
 *
 * ## ولمَ حارسٌ لا قاعدةٌ تُتذكَّر
 *
 * **النمطُ لا يُرى في `git diff`** كما يُرى سطرُ نصّ — يظهر سطراً واحداً
 * (`mode change 100755 => 100644`) **يمرّ عليه القارئ**. **وقاعدةٌ تُطبَّق لا
 * قاعدةٌ تُتذكَّر** هي الفرقُ الذي أنشأ فهرسَ الحرّاس في هذا المستودع.
 *
 * ## ما يمسكه — **ما يُنادى باسمه لا بمُفسِّره**
 *
 * `*.sh` **وكلَّ ملفٍّ بلا امتدادٍ يبدأ بـ`#!`** (`gradlew` · `pre-commit`)،
 * **ولا يحمل `x` في فهرس git**. والفهرسُ هو المرجع لا القرصُ: **ما يُودَع هو
 * ما يُسحب**.
 *
 * **و`.mjs` و`.py` و`.js` خارجُه بقياسٍ لا بظنّ**: قِيس أنها تُنادى
 * `node tools/…` و`python -m …` في كلِّ موضعٍ في هذا المستودع — **فبتُّها
 * لا يُستعمل، وأربعةُ أسطرِ ضجيجٍ تُطفئ حارساً**. وأوّلُ تشغيلٍ أخرجها
 * أربعاً مقابل ثلاثةٍ حقيقية.
 *
 * ## وما لا يمسكه — يُقال ولا يُقرأ سكوتُه ضماناً
 *
 * · **لا يمسك العكس**: ملفٌّ عاديٌّ صار `755` — **زيادةُ صلاحيةٍ ليست عطباً
 *   في هذا المشروع**، والحارسُ الذي يصيح على السليم يُطفأ.
 * · **ولا يقرأ القرص**: يقرأ `git ls-files -s` — **فتغييرٌ محلّيٌّ لم يُودَع
 *   لا يمسّه**، وذاك صحيحٌ: المقصودُ ما يصل الخادم.
 * · **ولا يعرف أنّ سكربتاً يُشغَّل فعلاً**: يقيس النيّةَ (الامتدادَ والشِّبانغ)
 *   لا الاستعمال. **و`.mjs` يُستثنى بقياسِ استعماله لا بحدسٍ عنه.**
 */

import { execSync } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(/[\\/]tools$/, "");
const stamp = new Date().toISOString().slice(0, 16).replace("T", " ");

let rows;
try {
  rows = execSync("git ls-files -s", { cwd: ROOT, encoding: "utf8", maxBuffer: 64 << 20 })
    .split("\n")
    .filter(Boolean);
} catch {
  console.error("\n✗ check:exec-bit · تعذّر `git ls-files -s` — **يُوقَف ولا يُقرأ سلامة**\n");
  process.exit(1);
}

const shebang = new Map(); // مسار → نمط
for (const line of rows) {
  // "100644 <sha> 0\tpath"
  const m = line.match(/^(\d{6}) [0-9a-f]+ \d+\t(.+)$/);
  if (!m) continue;
  const [, mode, path] = m;
  if (mode === "120000" || mode === "160000") continue; // وصلةٌ أو وحدةٌ فرعية
  shebang.set(path, mode);
}

let head;
try {
  head = execSync("git grep -l -I --untracked -e '^#!' -- .", {
    cwd: ROOT,
    encoding: "utf8",
    maxBuffer: 64 << 20,
  });
} catch {
  head = ""; // `git grep` يخرج بـ1 حين لا مطابقة
}
const withShebang = new Set(head.split("\n").filter(Boolean));

//: **يُنادى باسمه؟** — `.sh`، أو بلا امتدادٍ وفيه شِبانغ. وما له امتدادُ
//: مُفسِّرٍ (`.mjs` · `.js` · `.py` · `.ts`) **يُنادى بمُفسِّره فيُستثنى**.
const INTERPRETED = /\.(mjs|cjs|js|ts|tsx|py|rb|pl)$/;
const invokedByName = (path) => {
  const base = path.split("/").pop() || "";
  if (base.endsWith(".sh")) return true;
  if (INTERPRETED.test(base)) return false;
  return !base.includes(".") && withShebang.has(path);
};

const bad = [];
let checked = 0;
for (const [path, mode] of shebang) {
  if (!invokedByName(path)) continue;
  checked += 1;
  if (mode !== "100755") bad.push(`${path} — النمط ${mode}`);
}

if (checked === 0) {
  console.error("\n✗ check:exec-bit · **صفرُ سكربتٍ مقروء** — وصفرٌ مقروءٌ عطبٌ لا سلامة\n");
  process.exit(1);
}

if (bad.length) {
  console.error(`\n✗ check:exec-bit · **سكربتٌ بلا بتِّ تنفيذ في فهرس git** (${bad.length}):`);
  for (const b of bad) console.error(`    ${b}`);
  console.error(
    "\n  **ويسقط عند التشغيل بـ`Permission denied` (رمز 126) لا عند القراءة.**\n" +
      "  العلاج:  git update-index --chmod=+x <الملفّ>   ثمّ  chmod +x <الملفّ>\n",
  );
  process.exit(1);
}

console.log(
  `✓ check:exec-bit · كلُّ سكربتٍ متتبَّعٍ يحمل \`x\` — ${checked} سكربتاً مقروءاً · ${stamp}Z`,
);
