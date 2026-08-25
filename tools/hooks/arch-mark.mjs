#!/usr/bin/env node
// **يضع علامةً أن `ARCHITECTURE.md` قُرئ في هذه الجلسة** — ولا يفعل شيئاً غير ذلك.
//
// وهو نصفُ الخطّاف؛ النصفُ الآخرُ `arch-gate.mjs`. وقُسم نصفين عمداً: البديلُ
// أن تقرأ البوّابةُ سجلَّ الجلسة وتفتّش فيه، **وشكلُ السجلِّ ليس عقداً** — فحارسٌ
// مبنيٌّ على شكلٍ لا يملكه يصمت يومَ يتغيّر الشكل، **وصمتُه يُقرأ سلامة**.
//
// ═══════════════════════════════════════════════════════════════════════════
// **ذكرُ الاسم ليس قراءتَه** (قرارُ المالك 2026-08-25، بعد قياس)
//
// النسخةُ الأولى وسمت على **ورودِ السلسلة في أيِّ حقلِ مُدخل**. فوسمت جلسةً
// كاملةً على `grep -c 'ARCHITECTURE.md' CLAUDE.md` — **أمرٌ يعدّ ذكرَ الاسم في
// ملفٍّ آخر ولا يفتح المعمارَ البتّة**. وأثرُها أخطرُ من أثر بوّابةٍ غائبة:
// **السلاحُ يُنزع صامتاً** ثم تمرّ كتابةٌ على خلفيةٍ لم يُقرأ معمارُها،
// **والمالكُ يظنّها محروسة** — وهي «خُضرةٌ كاذبة» بعينها.
//
// **وهي عينُ ثغرةِ التعليق في `check:money-visible`** التي أُصلحت اليومَ نفسَه:
// اسمٌ في تعليقٍ كان يُعدّ قارئاً. **فالدرسُ واحد، وطُبِّق على الأداة كما
// طُبِّق على الشجرة.**
//
// **فالقاعدةُ الآن**: يُوسَم ما **يُخرج محتوى الملفّ** — أداةُ `Read`، أو أمرُ
// صدفةٍ من عائلة `cat`/`sed`/`head`. **ولا يُوسَم ما يذكر اسمَه بحثاً أو
// عدّاً** — `grep`/`rg`/`wc`/`ls`/`git`.
//
// **واتجاهُ الشكِّ معكوسٌ هنا عن `check:money-visible` عمداً**: هناك يُفسَّر
// الشكُّ لصالح السكوت لأن الصياحَ على سليمٍ يُطفئ الحارس؛ **وهنا الصمتُ هو
// الذي يُطفئه** — فما ليس في قائمة المُخرِجين **لا يَسِم**. وثمنُ الخطأ هنا
// رخيصٌ ومعلوم: من قرأ فعلاً بأمرٍ غيرِ معروفٍ يفتحه بـ`Read` مرّةً، ورسالةُ
// المنع تقول له ذلك.
//
// **وحدُّه مكتوبٌ كحدِّ البوّابة**: يقيس أن المحتوى **خرج**، لا أنه **قُرئ** —
// و`head -3 ARCHITECTURE.md` يَسِم. ومن نقل وسمَه شهادةً على أن المعمار فُهم
// فقد وسّع دعوى الأداة فوق نطاقها.
// ═══════════════════════════════════════════════════════════════════════════
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const GUARD = join(ROOT, ".claude", ".guard");

/** الملفُّ نفسُه، لا اسمُه داخل نمطٍ أو نصّ: الرمزُ **ينتهي** به مساراً. */
const TARGET = /(^|[/\\])ARCHITECTURE\.md$/;

/** أوامرُ **تُخرج المحتوى**. وما ليس هنا لا يَسِم — ولو قرأ. */
const EMITTERS = new Set([
  "cat", "bat", "tac", "head", "tail", "sed", "awk", "gawk", "nl", "more",
  "less", "od", "xxd", "strings", "fold", "pr", "expand",
]);

const unquote = (t) => t.replace(/^['"]/, "").replace(/['"]$/, "");
const slash = (t) => t.replace(/\\/g, "/");

/** أيُخرج هذا الأمرُ محتوى `ARCHITECTURE.md`؟ */
function emitsArchitecture(command) {
  for (const segment of command.split(/[\n;|&]+/)) {
    const tokens = segment.trim().split(/\s+/).filter(Boolean);
    // تجاوزُ إسنادات البيئة: `LC_ALL=C cat …`
    let at = 0;
    while (at < tokens.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[at])) at += 1;
    if (at >= tokens.length) continue;
    const name = slash(unquote(tokens[at])).split("/").pop();
    if (!EMITTERS.has(name)) continue;
    // **الرمزُ مسارٌ لا نمط**: `sed -n '/ARCHITECTURE.md/p' CLAUDE.md` يقرأ غيرَه
    if (tokens.slice(at + 1).some((t) => TARGET.test(slash(unquote(t))))) return true;
  }
  return false;
}

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

let ev;
try {
  ev = JSON.parse(raw);
} catch {
  process.exit(0); // لا يُعطَّل عملُ أحدٍ لأن الخطّافَ لم يفهم مُدخلَه
}

const input = ev.tool_input || {};
const read =
  ev.tool_name === "Read"
    ? TARGET.test(slash(String(input.file_path || "")))
    : ev.tool_name === "Bash"
      ? emitsArchitecture(String(input.command || ""))
      : false;

if (!read) process.exit(0);

const session = String(ev.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "");
try {
  mkdirSync(GUARD, { recursive: true });
  writeFileSync(join(GUARD, `arch-${session}`), new Date().toISOString() + "\n");
} catch {
  // تعذّرت الكتابة: البوّابةُ ستصيح، وهذا أسلمُ من فتحها صامتة
}
process.exit(0);
