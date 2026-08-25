#!/usr/bin/env node
// **بوّابةُ الشرط الأول**: لا تُكتب `backend/` قبل أن يُفتح `ARCHITECTURE.md`.
//
// ═══════════════════════════════════════════════════════════════════════════
// **دعواها بحرفها — ولا تُوسَّع** (قرارُ المالك 2026-08-25)
//
//   تمسك «**لم يفتح**». ولا تمسك «**فتح ولم يستعمل**».
//
// وهذا حدٌّ **مقيس** لا محتاط: في 2026-08-25 فتح وكيلٌ `HANDOFF.md` **٥٣٩
// سطراً من ١٠١٢** في مهمّةٍ حقيقية، ثم قال إن قراءتَه «**لم تغيّر الجوابَ
// بحرف**» — ففُتح ولم يُستعمل، **وبوّابةٌ كهذه كانت ستمرّ خضراء**.
//
// **فلا يُكتب في وصفها ولا في رسالتها أنها تضمن القراءة.** تضمن الفتحَ وحدَه.
// ومن نقل خضرتَها شهادةً على أن المعمار قُرئ فقد نقل ما لم يُقَس — وهو
// «حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه» (`GUARDS.md`).
// ═══════════════════════════════════════════════════════════════════════════
//
// **ونطاقُها ضيّقٌ عمداً**: شرطُ الخلفية وحدَه. والأربعةُ دفعةً واحدةً تصنع بابَ
// إزعاجٍ يُلتفّ عليه، **والملتفُّ عليه ليس باباً**. فإن عملت شهراً، تُمَدّ.
import { existsSync, mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const GUARD = join(ROOT, ".claude", ".guard");
const OFF = join(GUARD, "OFF");
const LOG = join(GUARD, "bypass.log");

const allow = () => process.exit(0);
const deny = (reason) => {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(0);
};

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

let ev;
try {
  ev = JSON.parse(raw);
} catch {
  allow(); // مُدخلٌ لا يُفهم لا يوقف عملَ أحد
}

const p = String(ev.tool_input?.file_path || "").replace(/\\/g, "/");
if (!p) allow();
// ملفّاتُ الخلفية وحدَها — ولا شيءَ آخر
if (!/(^|\/)backend\//.test(p)) allow();

const session = String(ev.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "");
if (existsSync(join(GUARD, `arch-${session}`))) allow();

// **المخرجُ معلومٌ ومسجَّل**: بابٌ لا مخرجَ له يُقتلَع لا يُحترم.
if (existsSync(OFF)) {
  try {
    mkdirSync(GUARD, { recursive: true });
    appendFileSync(LOG, `${new Date().toISOString()}\t${session}\t${p}\n`);
  } catch {}
  process.stdout.write(
    JSON.stringify({
      systemMessage:
        "⚠ بوّابةُ المعمار معطَّلةٌ عمداً (.claude/.guard/OFF) — والتعطيلُ مسجَّلٌ في .claude/.guard/bypass.log",
    })
  );
  process.exit(0);
}

deny(
  [
    "الشرطُ الأول في `CLAUDE.md`: **قبل أن تمسّ الخلفيةَ أو تضيف باباً — يُفتح `ARCHITECTURE.md`.**",
    "",
    `الملفّ: ${p}`,
    "",
    "افتح `ARCHITECTURE.md` (بـ`Read` أو بأمرِ صدفةٍ يذكره) ثمّ أعِد المحاولة.",
    "",
    "**وحدُّ هذه البوّابة مكتوب**: تمسك «لم يُفتح» ولا تمسك «فُتح ولم يُستعمل» —",
    "فلا تُقرأ خضرتُها شهادةً على أن المعمار قُرئ.",
    "",
    "وللتعطيل المتعمَّد: أنشئ `.claude/.guard/OFF` — ويُسجَّل كلُّ تجاوزٍ في",
    "`.claude/.guard/bypass.log` باسم الجلسة والملفّ والوقت.",
  ].join("\n")
);
