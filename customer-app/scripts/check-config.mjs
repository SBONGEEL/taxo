/** حارسٌ ضد «حقلٌ بلا مرآة» — الشقيقُ الثاني لـ«قاعدةٌ بلا باب».
 *
 * يغطّي **حمولاتِ `GET /config` وأجوبةَ المصادقة معاً** (انظر `MIRRORS`): وُلد
 * لحمولة الإعدادات، ثم كشف عطبُ `LoginResponse` أن الشرخَ نفسَه يقع في أيِّ
 * جوابٍ تكتب الواجهةُ نوعَه بيدها.
 *
 * الحكايةُ التي أنشأته: الخلفيةُ تنشر `quiet_hours_*` في `GET /config` منذ
 * المرحلة 8، **ونوعُ `CountryConfig` في التطبيق لم يحملها قط** — فكانت البياناتُ
 * تصل في كل نداءٍ وتُرمى، والشاشةُ التي تحتاجها تكتب رقماً من عندها أو لا تعرضه.
 * لا `tsc` يرى ذلك ولا `check:enums` ولا `check:scale`: الحمولةُ تصل صحيحةً،
 * والنوعُ الأصغرُ منها **صحيحٌ في نفسه** تماماً كالاتحاد الناقص في `check:flags`.
 * وبقيت الفجوةُ من المرحلة 8 إلى 12-هـ لأن لا شيءَ كان يقيسها.
 *
 * **والاتجاهان كلاهما عطب**، ولذلك يُفحصان معاً:
 *
 * 1. **حقلٌ في الخلفية بلا مرآةٍ في النوع** — يصل ويُرمى. وهذا هو العطبُ الأصل:
 *    ميزةٌ مبنيةٌ في الخلفية لا تصل الشاشةَ أبداً، بلا خطأٍ في أي بناء.
 * 2. **حقلٌ في النوع لا تُرسله الخلفية** — يُقرأ `undefined` في زمن التشغيل بينما
 *    يَعِد النوعُ بقيمة، فتُفرَّع عليه شاشةٌ لا تُفرَّع أبداً. وهو بعينه شكلُ عطب
 *    `awaiting_confirmation`: قيمةٌ اخترعتها الواجهةُ وصدّقها المصرّف.
 *
 * **ونموذجان لا واحد**: `CountryConfigOut` (ما يختلف بين سوقين) و`ConfigOut`
 * (غلافُه). فحقلٌ يُضاف إلى الغلاف — كما أُضيف `default_country_code` — يسقط من
 * المرآة بنفس الصمت.
 *
 * **وما لا يفحصه**: الأنواعَ نفسَها. `providers` قاموسٌ مفتوحٌ عمداً في الخلفية
 * (`dict[str, dict[str, Any]]`) وكلُّ تطبيقٍ يضيّقه على ما يقرؤه هو، و`auth`
 * كائنٌ مسطورٌ في اللوحة ومُسمّىً في التطبيقين. فالمقارنةُ **بأسماء الحقول** —
 * وهي وحدَها ما يقرّر «هل تصل القيمة أم تُرمى».
 *
 * يعمل ضمن `npm run build` قبل `tsc`.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

const SCHEMAS = join(process.cwd(), "..", "backend", "app", "schemas");
const TYPES = join(process.cwd(), "src", "api", "types.ts");

/** الأزواجُ المتقابلة: نموذجُ Pydantic ومرآتُه في `types.ts`.
 *
 * **و`required` تعني «يجب أن يُعلَن في كل تطبيق»**؛ وما دونها يُفحص إن أُعلن
 * وحدَه. فتطبيقا الراكب والكبتن يعلنان `ChallengeResponse` (لهما شاشةُ إثبات)
 * واللوحةُ لا تعلنه (تدخل بكلمة مرور وعاملٍ ثانٍ لا برمزِ هاتف) — بينما
 * `LoginResponse` **مطلوبٌ في الثلاثة** لأن ثلاثتها تنادي `POST /auth/login`.
 */
const MIRRORS = [
  { file: "config.py", model: "CountryConfigOut", type: "CountryConfig", required: true },
  { file: "config.py", model: "ConfigOut", type: "AppConfig", required: true },
  // أجوبةُ المصادقة — أُضيفت بعد أن شُحن تطبيقا الراكب والكبتن يكتبان جوابَ
  // الدخول `AuthResponse` بـ`tokens` غير قابلةٍ للغياب، بينما ترد الخلفيةُ
  // `LoginResponse` بـ`tokens: null` حين يكون العاملُ الثاني مطلوباً. النوعُ
  // كان يَعِد بما لا يصل، و`GET /config` وحده لا يحرس ذلك
  { file: "auth.py", model: "LoginResponse", type: "LoginResponse", required: true },
  { file: "auth.py", model: "AuthResponse", type: "AuthResponse", required: true },
  { file: "auth.py", model: "TokenPair", type: "TokenPair", required: true },
  { file: "auth.py", model: "ChallengeResponse", type: "ChallengeResponse" },
];

/** حقولُ نموذج Pydantic بأسمائها.
 *
 * تُحذف السلاسلُ الثلاثية أولاً (سطرٌ في docstring قد يحمل نقطتين فيُقرأ حقلاً)،
 * ثم تعليقاتُ `#`. والحقلُ ما كان على مسافةِ أربعِ مسافاتٍ يبدأ بحرفٍ صغير.
 */
function modelFields(source, className, file) {
  const start = source.indexOf(`class ${className}(BaseModel):`);
  if (start === -1) throw new Error(`لا نموذج ${className} في ${file}`);
  const rest = source.slice(start);
  const end = rest.slice(1).search(/^class /m);
  const block = (end === -1 ? rest : rest.slice(0, end + 1))
    .replace(/"""[\s\S]*?"""/g, "")
    .replace(/^\s*#.*$/gm, "");
  return [...block.matchAll(/^ {4}([a-z_][a-z0-9_]*)\s*:/gm)].map((m) => m[1]);
}

/** حقولُ واجهة TypeScript بأسمائها — **في العمق صفراً وحدَه**.
 *
 * `providers` في تطبيق الراكب كائنٌ متداخلٌ يحمل `mapbox` و`fcm` وغيرَهما، وهي
 * مفاتيحُ مزوّدين لا حقولَ حمولة — فعدُّها يجعل الحارسَ يشكو مما لا يعني.
 */
function interfaceFields(source, typeName) {
  const start = source.indexOf(`export interface ${typeName} {`);
  if (start === -1) return null;
  const body = source.slice(source.indexOf("{", start) + 1);

  const clean = body
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/.*$/gm, "");

  const fields = [];
  let depth = 0;
  for (const line of clean.split("\n")) {
    if (depth === 0 && /^\s*\}/.test(line)) break;
    // الاسمُ يُلتقط قبل تعديل العمق: حقلٌ قيمتُه كائنٌ يفتح قوسَه في سطره
    if (depth === 0) {
      const match = line.match(/^\s*([a-z_][a-z0-9_]*)\s*\??\s*:/i);
      if (match) fields.push(match[1]);
    }
    for (const char of line) {
      if (char === "{") depth += 1;
      else if (char === "}") depth -= 1;
    }
  }
  return fields;
}

const types = readFileSync(TYPES, "utf8");
const sources = new Map();
const read = (file) => {
  if (!sources.has(file)) sources.set(file, readFileSync(join(SCHEMAS, file), "utf8"));
  return sources.get(file);
};

const problems = [];
let checked = 0;

for (const { file, model, type, required } of MIRRORS) {
  const published = modelFields(read(file), model, file);
  const mirrored = interfaceFields(types, type);

  // غيابُ الواجهةِ نفسِها: خطأٌ لما هو مطلوب، وتخطٍّ لما هو اختياري
  if (mirrored === null) {
    if (required) {
      problems.push(
        `لا واجهة \`${type}\` في api/types.ts — و\`${model}\` يُنشر منها ` +
          `${published.length} حقلاً`,
      );
    }
    continue;
  }
  checked += published.length;

  const unmirrored = published.filter((field) => !mirrored.includes(field));
  if (unmirrored.length > 0) {
    problems.push(
      `\`${type}\` لا يعكس ما تنشره \`${model}\`: ${unmirrored.join(", ")}` +
        ` — تصل في كل نداءٍ وتُرمى`,
    );
  }

  const invented = mirrored.filter((field) => !published.includes(field));
  if (invented.length > 0) {
    problems.push(
      `\`${type}\` يَعِد بما لا ترسله \`${model}\`: ${invented.join(", ")}` +
        ` — تُقرأ \`undefined\` في زمن التشغيل`,
    );
  }
}

if (problems.length > 0) {
  console.error("حمولاتُ الخلفية بلا مرآةٍ في `api/types.ts`:\n");
  for (const problem of problems) console.error("  " + problem);
  console.error(
    "\nإضافةُ حقلٍ إلى حمولةٍ تقرؤها الواجهةُ عملٌ في نفس التغيير لا متابعةٌ لاحقة:" +
      "\n  ١. الحقل في `backend/app/schemas/` (config.py أو auth.py)" +
      "\n  ٢. مرآتُه في `src/api/types.ts` في **التطبيقات الثلاثة**" +
      "\n  ٣. ومن يقرؤه: حقلٌ بمرآةٍ لا تقرؤه شاشةٌ نصفُ عطبٍ لا حلٌّ.",
  );
  process.exit(1);
}

console.log(`✓ كل حقول الحمولات المرصودة (${checked}) لها مرآة في api/types.ts`);
