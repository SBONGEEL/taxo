/** حسابُ مالٍ في الواجهة — **§14 يمنعه، وهذا حارسُه**.
 *
 * **القاعدةُ قائمةٌ منذ المواصفة**: «التسعيرُ وكلُّ حسابٍ ماليٍّ في الخلفية
 * وحدها؛ والواجهاتُ تعرض». **وكانت مكتوبةً بلا حارس** — فبقيت تُنقَض بلا أن
 * يفشل شيء.
 *
 * **العطبُ الذي وُجد له** (قِيس على الجهاز 2026-08-23): شاشةُ تحويل الراكب
 * تحسب «رصيدك بعده» بـ`subtractMoney(balance, amount)` **في المتصفّح**،
 * فأعطت **«−12.500 د.أ»** على رصيدٍ صفر. **والحدُّ الذي يمنع السالبَ موجودٌ
 * في الخلفية** (`withdrawals.available_balance` منذ 2026-08-20) — **ولا
 * يبلغ حساباً في شاشة**.
 *
 * > **حدٌّ في موضعٍ لا يحرس موضعاً ثانياً يحسب الشيءَ نفسَه.**
 *
 * **ولا يراه حارسٌ قائم**: لا حقلَ ناقصاً، ولا مبلغاً بلا قارئ، ولا ردَّين
 * يفترقان — **فالرقمُ لا يمرّ بباب أصلاً**، يُحسب في الشاشة ولا شيءَ يقارنه.
 *
 * **وما يمسكه ضيّقٌ بحدّه**: عملياتُ `+ - * /` **على قيمةٍ اسمُها مالٌ**.
 * ولا يمسك «حدّاً في موضعٍ دون موضع» — **ذاك يحتاج جدولاً يُكتب بيدٍ يربط
 * كلَّ قيمةٍ بحدِّها، وهو «هل تذكّرتَ؟» التي يُبنى الحارسُ لإلغائها**
 * (قرارُ المالك 2026-08-23: يُبنى الشقُّ الأولُ وحدَه).
 *
 * **ومفرداتُ المال من بيتها الواحد** (`backend/tests/money_format.py`) — لا
 * قائمةٌ ثانيةٌ هنا تفترق عنها أوّلَ إضافة.
 *
 * **والمقارناتُ ليست حساباً**: `Number(amount) <= 0` يقرأ ولا يشتقّ رقماً
 * يُعرض. **وما يُمنع هو اشتقاقُ مبلغٍ جديد.**
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { certify } from "./certify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APPS = ["customer-app", "driver-app", "admin-panel"];

/** **مُحلِّلٌ من حزمة تطبيقٍ لا من الجذر** — لا `node_modules` في جذر
 *  المستودع، وهي قاعدةُ `check:readers` نفسُها. **وغيابُه وقوفٌ لا سلامة.** */
function loadTypeScript() {
  for (const app of APPS) {
    try {
      return createRequire(new URL(`../${app}/package.json`, import.meta.url))(
        "typescript",
      );
    } catch {
      /* جرّبْ التالي */
    }
  }
  console.error("✗ لم يوجد `typescript` في أيٍّ من التطبيقات — الحارسُ لا يقيس.");
  process.exit(1);
}
const ts = loadTypeScript();

/** مفرداتُ المال — **تُقرأ من بيتها الواحد** لا تُكتب هنا. */
function moneyVocabulary() {
  const source = readFileSync(
    join(ROOT, "backend/tests/money_format.py"),
    "utf8",
  );
  const block = (name) => {
    const start = source.indexOf(`${name} = `);
    if (start < 0) return [];
    const body = source.slice(start, source.indexOf(")", start));
    return [...body.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  };
  const suffixes = block("MONEY_SUFFIXES");
  const names = block("MONEY_NAMES");
  const notMoney = new Set(block("NOT_MONEY"));
  if (suffixes.length === 0 || names.length === 0) return null;
  return { suffixes, names: new Set(names), notMoney };
}

/** `ملف:سطر` ← علّةُ قبوله. **ولا تُقبل فجوةٌ بلا نصّ.**
 *
 * **والمفتاحُ يحمل السطرَ عمداً**: نقلُ الحساب أو إضافةُ ثانٍ يُظهره من جديد
 * فيُراجَع، ولا يختبئ تحت عذرٍ كُتب لغيره — قاعدةُ `_ACCEPTED` نفسُها. */
const DELIBERATE = {
  // **مقارنةٌ لا عرض**: يُنتقى بها أفضلُ عرضٍ، **وناتجُها لا يصل شاشة** —
  // والأرقامُ المعروضةُ نصوصٌ كما جاءت من الخلفية. والعلّةُ مكتوبةٌ في الملفّ
  // نفسِه فوق السطر منذ كُتب.
  "driver-app/src/lib/welcome.ts:107":
    "مقارنةٌ لاختيار أفضل عرض — لا يُعرض ناتجُها",
  // **معاينةُ ما يكتبه المشرفُ الآن**: `amount` و`bonus` حالُ نموذجٍ محلّيّةٌ
  // يحرّرها بيده، **والخلفيةُ تنشر مجموعَ المحفوظ لا مجموعَ المكتوب**
  // (`female_total_amount`). فلا بابَ يعطي هذا الرقمَ قبل الحفظ.
  // **ويبقى تحفّظٌ مكتوب**: هذا جمعُ مالٍ عبر `Number` — أي عبر عائم — وهو ما
  // يمنعه §14؛ يُحتمل هنا لأنه معاينةُ إدخالٍ لا مبلغٌ يُحصَّل.
  "admin-panel/src/screens/Settings.tsx:993":
    "معاينةٌ حيّةٌ لِما يُكتب قبل الحفظ — ولا باب ينشره",
  // **فرضٌ لا مبلغ**: «رصيدك بعده» جوابُ «ماذا لو أرسلتُ هذا الرقمَ الذي
  // أكتبه الآن؟» — **ولا بابَ ينشره**، وبناءُ بابٍ له نداءٌ لكلِّ ضغطة مفتاح.
  // **والحسابُ ليس عبر عائم**: `subtractMoney` تعمل بأجزاء الألف صحيحةً
  // (`utils.ts:148`) فهي مضبوطةٌ تماماً في صيغة المال ذات الخانات الثلاث.
  //
  // **وليس هذا عذرَ «للعرض فقط»**: عطبُ «رصيدك بعده −١٢٫٥٠٠ د.أ» لم يكن في
  // الطرح بل في **عرض المستحيل كأنه واقع** — وقد أُغلق في موضعه: الزرُّ
  // يُعطَّل والنقصُ يُسمّى قبل أن يُرسم فرضٌ لا يقع.
  "customer-app/src/screens/WalletTransfer.tsx:275":
    "فرضٌ لِما يُكتب الآن ولا بابَ ينشره — وحسابُه بأجزاء الألف صحيحةً لا بعائم",
};

function files(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) files(path, out);
    else if (/\.tsx?$/.test(entry)) out.push(path);
  }
  return out;
}

/** مسارٌ نسبيٌّ بفواصل «/» — **بلا تعبيرٍ نمطيّ**: شرطةٌ مائلةٌ عكسيةٌ
 *  داخل تعبيرٍ نمطيٍّ في مولِّدٍ نصّيٍّ عطبٌ وقع مرتين هنا. */
const rel = (file) => relative(ROOT, file).split("\\").join("/");

const ARITHMETIC = new Set([
  ts.SyntaxKind.PlusToken,
  ts.SyntaxKind.MinusToken,
  ts.SyntaxKind.AsteriskToken,
  ts.SyntaxKind.SlashToken,
]);

const vocab = moneyVocabulary();
if (vocab === null) {
  console.error("✗ لم تُقرأ مفرداتُ المال من `tests/money_format.py` — المسحُ أعمى.");
  process.exit(1);
}

/** أهذا الاسمُ مالٌ؟ — بالمفردات من بيتها الواحد. */
function isMoneyName(word) {
  const snake = word.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
  if (vocab.notMoney.has(snake)) return false;
  return vocab.names.has(snake) || vocab.suffixes.some((s) => snake.endsWith(s));
}

/** **أهذا التعبيرُ قيمةُ مالٍ؟ — بالعقدة لا بالنصّ.**
 *
 * **والفرقُ قِيس**: القراءةُ النصّيةُ عدّت `currencyOf(price.country_code)`
 * مالاً لأن كلمةَ `price` تقع فيها — **فاخترع الحارسُ بلاغاً على سطرٍ سليم**.
 * والصحيحُ أن يُقرأ **آخرُ اسمٍ في سلسلة الوصول**: `price.country_code`
 * حقلُه `country_code` لا `price`.
 *
 * **ونتيجةُ نداءٍ ليست مالاً بحكم اسم وسيطه** — إلا `Number(x)`/`String(x)`
 * وأمثالِها، فهي أغلفةٌ تُمرّر قيمتَها. */
function isMoneyValue(node) {
  if (node === undefined) return false;
  if (ts.isParenthesizedExpression(node)) return isMoneyValue(node.expression);
  if (ts.isNonNullExpression(node) || ts.isAsExpression(node))
    return isMoneyValue(node.expression);
  if (ts.isIdentifier(node)) return isMoneyName(node.text);
  if (ts.isPropertyAccessExpression(node)) return isMoneyName(node.name.text);
  if (ts.isElementAccessExpression(node)) return isMoneyValue(node.expression);
  if (ts.isBinaryExpression(node))
    return isMoneyValue(node.left) || isMoneyValue(node.right);
  if (ts.isCallExpression(node)) {
    const callee = node.expression.getText();
    // **أغلفةٌ تمرّر قيمتَها** — لا تشتقّ مالاً جديداً
    if (/^(Number|String|parseFloat|parseInt)$/.test(callee))
      return node.arguments.some(isMoneyValue);
    return false;
  }
  return false;
}

const problems = [];
const stale = [];
/** فجواتٌ وقعت فعلاً في هذا الشوط — **وما لم يقع منها عذرٌ شاخ**. */
const matched = new Set();
let scanned = 0;
let expressions = 0;

for (const app of APPS) {
  for (const file of files(join(ROOT, app, "src"))) {
    scanned += 1;
    const source = ts.createSourceFile(
      file,
      readFileSync(file, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const visit = (node) => {
      if (ts.isBinaryExpression(node) && ARITHMETIC.has(node.operatorToken.kind)) {
        expressions += 1;
        const left = node.left.getText(source);
        const right = node.right.getText(source);
        // **النصُّ زائدَ نصٍّ ليس حساباً**: `"a" + x` وصلٌ لا اشتقاق
        const literal =
          ts.isStringLiteral(node.left) || ts.isStringLiteral(node.right);
        if (!literal && (isMoneyValue(node.left) || isMoneyValue(node.right))) {
          const line =
            source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
          const where = `${rel(file)}:${line}`;
          const shown = `${left} ${node.operatorToken.getText(source)} ${right}`
            .replace(/\s+/g, " ")
            .slice(0, 70);
          if (DELIBERATE[where]) {
            matched.add(where);
            return ts.forEachChild(node, visit);
          }
          problems.push(`${where} — ${shown}`);
        }
      }
      // **والاشتقاقُ يقع بنداءٍ كما يقع بمعامل**: `subtractMoney(balance,
      // amount)` لا معاملَ فيه، **وهو الذي أعطى «−12.500»**. فحارسٌ يقرأ
      // المعاملاتِ وحدَها كان سيمرّ عليه أخضر — قِيس، ثم وُسِّع.
      //
      // **والقاعدةُ «وسيطان ماليّان في نداءٍ واحد»**: `formatMoney(fare,
      // currency)` وسيطٌ ماليٌّ واحدٌ فيمرّ، **واثنان اشتقاق**.
      if (ts.isCallExpression(node)) {
        // **خطّافُ React ليس اشتقاقاً**: `useEffect(fn, deps)` وسيطاه دالّةٌ
        // ومصفوفةُ اعتماد — والنصُّ فيهما يذكر المال ولا يحسبه. قِيس: أوّلُ
        // صياغةٍ اخترعت بلاغاً على `useEffect` في `ConfirmRide`.
        const callee = node.expression.getText(source);
        const isHook = /^use[A-Z]/.test(callee.split(".").pop() ?? "");
        const takesFunction = node.arguments.some(
          (a) => ts.isArrowFunction(a) || ts.isFunctionExpression(a),
        );
        const moneyArgs = node.arguments.filter(isMoneyValue);
        if (!isHook && !takesFunction && moneyArgs.length >= 2) {
          const line =
            source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
          const where = `${rel(file)}:${line}`;
          const shown = node.getText(source).replace(/\s+/g, " ").slice(0, 70);
          if (DELIBERATE[where]) matched.add(where);
          else problems.push(`${where} — ${shown}`);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
}

for (const key of Object.keys(DELIBERATE)) {
  if (!matched.has(key)) stale.push(key);
}

// **إثباتُ الصمت**: صفرُ تعبيرٍ حسابيٍّ يعني مسحاً أعمى لا شجرةً سليمة
if (expressions === 0) {
  console.error("✗ لم يُقرأ تعبيرٌ حسابيٌّ واحد — المسحُ أعمى، لا الشجرةُ سليمة.");
  process.exit(1);
}

if (stale.length > 0) {
  console.error("✗ فجواتٌ مكتوبةٌ لم تعد تقع — تُنظَّف وإلا صارت أعذاراً:");
  for (const line of stale) console.error(`  ${line}`);
  process.exit(1);
}

if (problems.length > 0) {
  console.error("✗ حسابُ مالٍ في الواجهة — و§14 يحصره في الخلفية:");
  for (const line of problems) console.error(`  ${line}`);
  console.error(
    "  اطلب الرقمَ محسوباً من الخلفية، أو اكتب علّتَه في `DELIBERATE`.",
  );
  console.error(
    "  **والعلّةُ ليست «للعرض فقط»**: «رصيدك بعده −12.500 د.أ» كان للعرض.",
  );
  process.exit(1);
}

certify(
  "check:money-math",
  `لا حسابَ مالٍ في الواجهة (${expressions} تعبيراً في ${scanned} ملفّاً)`,
  `فجواتٌ مكتوبةٌ ${Object.keys(DELIBERATE).length}`,
);
