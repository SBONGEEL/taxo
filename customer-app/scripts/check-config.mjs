/** حارسٌ ضد «حقلٌ بلا مرآة» — الشقيقُ الثاني لـ«قاعدةٌ بلا باب».
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

const SCHEMA = join(
  process.cwd(),
  "..",
  "backend",
  "app",
  "schemas",
  "config.py",
);
const TYPES = join(process.cwd(), "src", "api", "types.ts");

/** الزوجان المتقابلان: نموذجُ Pydantic ومرآتُه في `types.ts`. */
const MIRRORS = [
  { model: "CountryConfigOut", type: "CountryConfig" },
  { model: "ConfigOut", type: "AppConfig" },
];

/** حقولُ نموذج Pydantic بأسمائها.
 *
 * تُحذف السلاسلُ الثلاثية أولاً (سطرٌ في docstring قد يحمل نقطتين فيُقرأ حقلاً)،
 * ثم تعليقاتُ `#`. والحقلُ ما كان على مسافةِ أربعِ مسافاتٍ يبدأ بحرفٍ صغير.
 */
function modelFields(source, className) {
  const start = source.indexOf(`class ${className}(BaseModel):`);
  if (start === -1) throw new Error(`لا نموذج ${className} في ${SCHEMA}`);
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
  if (start === -1) throw new Error(`لا واجهة ${typeName} في ${TYPES}`);
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

const schema = readFileSync(SCHEMA, "utf8");
const types = readFileSync(TYPES, "utf8");

const problems = [];
let checked = 0;

for (const { model, type } of MIRRORS) {
  const published = modelFields(schema, model);
  const mirrored = interfaceFields(types, type);
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
  console.error("حقولٌ في `GET /config` بلا مرآةٍ في `api/types.ts`:\n");
  for (const problem of problems) console.error("  " + problem);
  console.error(
    "\nإضافةُ حقلٍ إلى `GET /config` عملٌ في نفس التغيير لا متابعةٌ لاحقة:" +
      "\n  ١. الحقل في `backend/app/schemas/config.py`" +
      "\n  ٢. مرآتُه في `src/api/types.ts` في **التطبيقات الثلاثة**" +
      "\n  ٣. ومن يقرؤه: حقلٌ بمرآةٍ لا تقرؤه شاشةٌ نصفُ عطبٍ لا حلٌّ.",
  );
  process.exit(1);
}

console.log(`✓ كل حقول \`GET /config\` (${checked}) لها مرآة في api/types.ts`);
