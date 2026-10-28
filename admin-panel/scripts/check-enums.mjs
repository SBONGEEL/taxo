/** حارسٌ ضد الاتحاد المكتوب في الواجهة بدل نسخه من الخلفية.
 *
 * وقع هذا مرتين: `awaiting_confirmation` في `PaymentStatus` — حالٌ لا وجود لها
 * في `app/models/enums.py` — فبنت عليها ثلاث شاشات، ولم يستطع كبتنٌ تأكيد
 * دفعة كاش؛ و`mixed` في `PaymentMethod` — قناةٌ لا يرسلها المزود قط، والدفعُ
 * المختلط **صفّان** لا قناة. والبناءُ أخضر في الحالتين: السلسلة عضوٌ صحيح في
 * اتحادٍ أعلنه التطبيق نفسه، فلا TypeScript يعترض ولا الاختبارات ترى واجهة.
 *
 * فيقرأ هذا السكربت أعضاء كل `StrEnum` في الخلفية، ثم كل اتحادِ سلاسلَ في
 * `src`، ويرفض ما خلط قيمةً من تعدادٍ بقيمةٍ لا وجود لها فيه — وتلك بالضبط
 * بصمةُ الاتحاد المنسوخ ثم المزيد عليه.
 *
 * يعمل ضمن `npm run build` قبل `tsc`.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { certify } from "../../tools/certify.mjs";

const BACKEND = join(process.cwd(), "..", "backend", "app");
const SRC = join(process.cwd(), "src");

/** اتحاداتُ واجهةٍ خالصة تشترك في أسماءٍ مع تعدادات الخلفية بالمصادفة.
 *  كلُّ إعفاءٍ هنا يذكر لماذا هو اتحادُ عرضٍ لا مرآةُ عقد. */
const UI_UNIONS = new Set([
  // **ألواحُ «حماية الدفع»** (SPEC §٨٧) — أسماءُ ألواحٍ في الشاشة لا مرآةُ عقد
  "ProtectionTab",
  // **مرآةُ فهرس إشعارات المالك** (SPEC §٨١، `services/admin_alerts.py`) — قواميسُ لا تعدادات: قيمُها عامّةٌ («phone» · «ride»)
  // فتعدادٌ بها في الخلفية يُسقط اتحاداتِ التطبيقين (`Field` · `Step`). **ويقابلها قيمةً قيمةً ``check-enums.mjs → ALERT_MIRRORS`** — فلا تفترق بلا حارس
  "AlertCategory",
  "AlertTone",
  "AlertChannel",
  // **مرشِّحُ حال الملاحظات** (`screens/Feedback.tsx`، SPEC §٧٦/٤): «جديدةٌ/معالَجةٌ/الكلّ» تُشتقّ من `handled_at` فارغاً أو لا —
  // **لا تعدادَ لها في الخلفية**، والبابُ يقبلها معاملَ استعلامٍ (`Literal`) لا عموداً
  "FeedbackStatus",
  // حالُ الاشتراك الأربع تُشتق في `Subscription.tsx::stateOf` من
  // `is_active` و`days_remaining` و`coverage_until` — لا عمودَ لها
  "State",
  // سببُ آخر خروجٍ من اللوحة (`lib/session.tsx`، المرحلة 12-د): حالةُ متصفحٍ
  // خالصة لا ترحل إلى الخلفية ولا تصل منها. و`expired` منها يوافق بالمصادفة
  // قيمةً في تعدادِ اشتراكاتٍ لا علاقةَ لها بجلسةٍ إدارية
  "SignOutReason",
  // صنفُ إصابة البحث العامّ (§39٫١٢٫٤): **وجهةٌ لا حال** — لا جدولَ
  // اسمُه «صنفُ إصابة». و`driver` منها يوافق بالمصادفة قيمةً في
  // `UserRole` و`WalletOwnerType`، **والمعنى مختلف**: هناك دورُ إنسان،
  // وهنا **إلى أيِّ شاشةٍ يقفز الدرج**
  "SearchKind",
  // **أفعالُ طابور نظام الدفع** (SPEC §٧٣-هـ) — أيُّ حوارٍ يُفتح فوق الطلب: كلٌّ بابٌ بمساره (`approve` · `reject` · `refund` ·
  // `cancel`) **لا قيمةُ حالٍ في الخلفية**؛ و`refund` منها يوافق بالمصادفة نوعَ قيدٍ في الدفتر (`refund`)، **والمعنى مختلف**
  "RequestAction",
  // **حالُ صفٍّ في «المدفوعات غير المؤكدة»** (SPEC §٦٤-ز): مرآةُ `AdminUnconfirmedState` — **`Literal` في
  // `schemas/unconfirmed_payment.py` لا `StrEnum`**، وهذا الحارسُ يقرأ التعداداتِ وحدَها فلا يعرف أعضاءه.
  // **ويُعلَن لأنه مختلطٌ في عينه**: `disputed` يوافق `PaymentStatus` بالاسم، والأربعةُ الباقيةُ حالاتُ الطابور
  // تشتقّها الخدمةُ (`_queue_state`). فالإعلانُ تصريحٌ بمرآة `Literal` لا قيمةٍ مخترعة
  "AdminUnconfirmedState",
]);

/** يمحو تعليقات `/* *\/` و`//` ويترك ما عداها بطوله.
 *
 * لا يفهم السلاسل، فـ`"// ليس تعليقاً"` داخل نصٍّ يُمحى خطأً — وهو مقبولٌ هنا:
 * الضررُ الوحيد أن يفحص الحارس اتحاداً بعضوٍ ناقص، لا أن يتخطّى اتحاداً.
 * والخطأُ في هذا الاتجاه هو الاتجاه الصحيح للخطأ في حارس.
 */
function stripComments(text) {
  const block = /\/\*[\s\S]*?\*\//g;
  const line = new RegExp("//[^\n]*", "g");
  return text.replace(block, " ").replace(line, " ");
}

function walk(dir, test) {
  return readdirSync(dir).flatMap((entry) => {
    if (entry === "__pycache__" || entry === "node_modules") return [];
    const path = join(dir, entry);
    return statSync(path).isDirectory()
      ? walk(path, test)
      : test(path)
        ? [path]
        : [];
  });
}

// ------------------------------------------------------------- الخلفية
const enumValues = new Set();
for (const file of walk(BACKEND, (p) => p.endsWith(".py"))) {
  const text = readFileSync(file, "utf8");
  for (const member of text.matchAll(/^\s{4}[A-Z_0-9]+\s*=\s*"([^"]+)"/gm)) {
    enumValues.add(member[1]);
  }
  // أسماءُ الأحداث المبثوثة عقدٌ كذلك وإن لم تكن تعداداً في كل موضع
  for (const event of text.matchAll(/"type":\s*"([a-z_]+)"/g)) {
    enumValues.add(event[1]);
  }
}

// ------------------------------------------------------------- الواجهة
const problems = [];
for (const file of walk(SRC, (p) => /\.tsx?$/.test(p))) {
  // **التعليقات تُحذف قبل المطابقة.** النمطُ أدناه يقبل سلاسلَ وأنابيبَ فقط،
  // فتعليقٌ بين أعضاء الاتحاد يجعله لا يطابق — فيمر الاتحادُ **بلا فحص**
  // والبناءُ أخضر. وقع هذا فعلاً في `AuditAction` بلوحة الإدارة: شرحُ
  // `read` كُتب بين العضوين فتوقّف الحارس عن رؤية الاتحاد كله، ولا شيء
  // يقول ذلك. حارسٌ يُتخطّى بصمتٍ أسوأ من حارسٍ غائب — الغائبُ يُعرف.
  const text = stripComments(readFileSync(file, "utf8"));
  for (const match of text.matchAll(
    /type\s+(\w+)\s*=\s*((?:\s*\|?\s*"[^"]+")+)\s*;/g,
  )) {
    const [, name, body] = match;
    if (UI_UNIONS.has(name)) continue;
    const members = [...body.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    if (members.length < 2) continue;
    const known = members.filter((value) => enumValues.has(value));
    const strays = members.filter((value) => !enumValues.has(value));
    // اتحادٌ **بعضُه** من الخلفية وبعضُه لا: منسوخٌ ثم زِيد عليه
    if (known.length > 0 && strays.length > 0) {
      problems.push(
        `${file.replace(process.cwd(), ".")}: ${name} — ${strays.join(", ")}`,
      );
    }
  }
}

// ------------------------------------------------------------- مرآةُ فهرس إشعارات المالك (SPEC §٨١)
//
// **المستثناةُ الثلاثةُ أعلاه لا تُترك بلا حارس**: قيمُها مفاتيحُ قواميسَ في `services/admin_alerts.py` (لا تعدادات — قيمُها عامّة)،
// **فتُقابَل هنا قيمةً قيمة**. قيمةٌ تُضاف هناك ولا تُضاف هنا ترسم اللوحةُ صفَّها بلا أيقونةٍ ولا لون — بلا خطأٍ يُرى.
const ALERT_MIRRORS = { AlertTone: "TONES", AlertCategory: "CATEGORIES", AlertChannel: "CHANNELS" };
const alertsPy = walk(BACKEND, (p) => p.endsWith(join("services", "admin_alerts.py")))[0];
if (alertsPy) {
  const py = readFileSync(alertsPy, "utf8");
  const types = stripComments(readFileSync(join(SRC, "api", "types.ts"), "utf8"));
  for (const [union, name] of Object.entries(ALERT_MIRRORS)) {
    // **السطرُ الواحدُ أوّلاً** (`CHANNELS = ("panel", …)`) — وإلا ابتلع البديلُ متعدّدُ الأسطر ما بعده حتى أوّلِ قوسٍ في رأس سطر
    const pyBlock = py.match(new RegExp(`^${name}[^=]*=\\s*(\\([^\\n]*\\)|[({][\\s\\S]*?^[)}])`, "m"));
    const pyValues = pyBlock
      ? [...pyBlock[1].matchAll(/^\s*"([a-z_]+)"\s*:|"([a-z_]+)"(?=\s*[,)])/gm)].map((m) => m[1] ?? m[2])
      : [];
    const tsBlock = types.match(new RegExp(`type\\s+${union}\\s*=\\s*([^;]+);`));
    const tsValues = tsBlock ? [...tsBlock[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
    const missing = pyValues.filter((value) => !tsValues.includes(value));
    const extra = tsValues.filter((value) => !pyValues.includes(value));
    if (!pyValues.length || !tsValues.length || missing.length || extra.length) {
      problems.push(
        `./src/api/types.ts: ${union} ≠ admin_alerts.${name} — ناقص: ${missing.join(", ") || "—"} · زائد: ${extra.join(", ") || "—"}`,
      );
    }
  }
}

if (problems.length > 0) {
  console.error("اتحاداتٌ فيها قيمٌ لا يعرفها أيُّ تعدادٍ في الخلفية:\n");
  for (const problem of [...new Set(problems)]) console.error("  " + problem);
  console.error(
    "\nانسخ القيم من `backend/app/models/enums.py` كما هي." +
      " وإن كان اتحادَ عرضٍ لا مرآةَ عقد، أضف اسمه إلى `UI_UNIONS` بسببه.",
  );
  process.exit(1);
}
certify("check:enums", "✓ كل اتحادات السلاسل تطابق تعدادات الخلفية");
