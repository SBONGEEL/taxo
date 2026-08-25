#!/usr/bin/env node
// **بوّابةُ الشرط الأول**: لا تُكتب `backend/` قبل أن يُقرأ `ARCHITECTURE.md`.
//
// ═══════════════════════════════════════════════════════════════════════════
// **دعواها بحرفها — ولا تُوسَّع** (قرارُ المالك 2026-08-25)
//
//   تمسك «**لم يُقرأ**». ولا تمسك «**قُرئ ولم يُستعمل**».
//
// وهذا حدٌّ **مقيس** لا محتاط: في 2026-08-25 فتح وكيلٌ `HANDOFF.md` **٥٣٩
// سطراً من ١٠١٢** في مهمّةٍ حقيقية، ثم قال إن قراءتَه «**لم تغيّر الجوابَ
// بحرف**» — ففُتح ولم يُستعمل، **وبوّابةٌ كهذه كانت ستمرّ خضراء**.
//
// **فلا يُكتب في وصفها ولا في رسالتها أنها تضمن القراءة.** تضمن أن المحتوى
// خرج وحدَه. ومن نقل خضرتَها شهادةً على أن المعمار قُرئ فقد نقل ما لم يُقَس —
// وهو «حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه» (`GUARDS.md`).
// ═══════════════════════════════════════════════════════════════════════════
//
// **ونطاقُها ضيّقٌ عمداً**: شرطُ الخلفية وحدَه. والأربعةُ دفعةً واحدةً تصنع بابَ
// إزعاجٍ يُلتفّ عليه، **والملتفُّ عليه ليس باباً**. فإن عملت شهراً، تُمَدّ.
//
// ═══════════════════════════════════════════════════════════════════════════
// **حدُّ تغطية `Bash` — يُقال قبل أن يُصدَّق** (قرارُ المالك 2026-08-25)
//
// النسخةُ الأولى حرست `Edit|Write` وحدَهما، **وقِيس أن `echo … > backend/x`
// تمرّ**. وهو الثقبُ في المسار **المستعمَل**: أكثرُ التحرير في هذا المستودع
// يقع بالصدفة.
//
// **وما تمسكه الآن من أشكال الكتابة، مسمّىً لا مُجمَلاً:**
//   · إعادةُ التوجيه `>` و`>>`
//   · `tee` · `sed -i` / `perl -i` · `dd of=`
//   · `cp`/`mv`/`ln`/`install`/`rsync` — **الوجهةُ وحدَها** (آخرُ رمز)
//   · `rm`/`rmdir`/`touch`/`mkdir`/`truncate`/`unlink`/`shred` — كلُّ الأهداف
//   · `git checkout|restore|apply|clean` حين يسمّي مساراً تحت `backend/`
//   · مُفسِّرٌ (`python`/`node`/`perl`/`ruby`/`sh`) يذكر مساراً تحت `backend/`
//     **ومعه أثرُ كتابةٍ في نصّه** (`open(…,"w")`، `writeFileSync`، …)
//
// **وما لا تمسكه — ولا تدّعي أنها تمسكه:**
//   · مُفسِّرٌ يكتب بلا أثرٍ من الأنماط أعلاه، أو ببناءِ مسارٍ في متغيّر
//   · `git checkout <فرع>` وأخواتُه ممّا يبدّل الشجرةَ بلا تسمية مسار
//   · `patch < diff` — الوجهةُ داخلُ الرقعة لا سطرُ الأمر
//   · مُحرِّرٌ تفاعليّ، أو أداةٌ تكتب عبر حاويةٍ (`docker … > /app/…`)
//
// **فحارسٌ محدودُ الدعوى خيرٌ من حارسٍ دعواه أوسعُ من نطاقه** — والحدُّ مكتوبٌ
// في رسالة المنع أيضاً، لا هنا وحدَه.
// ═══════════════════════════════════════════════════════════════════════════
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

const slash = (t) => t.replace(/\\/g, "/");
const unquote = (t) => t.replace(/^['"]/, "").replace(/['"]$/, "");
const isBackend = (p) => /(^|\/)backend\//.test(slash(p));

// ── أشكالُ الكتابة في أمرِ صدفة ─────────────────────────────────────────
const ALL_TARGETS = new Set([
  "rm", "rmdir", "touch", "mkdir", "truncate", "unlink", "shred",
]);
const DEST_LAST = new Set(["cp", "mv", "ln", "install", "rsync"]);
const INTERPRETERS = new Set([
  "python", "python3", "py", "node", "perl", "ruby", "sh", "bash", "zsh",
]);
// أثرُ كتابةٍ داخل نصِّ مُفسِّر — **دلالةٌ لا برهان**، والحدُّ مكتوبٌ أعلاه
const WRITE_HINTS =
  /\bopen\s*\([^)]*["'][rwax+]*[wax]|writeFileSync|appendFileSync|createWriteStream|write_text|write_bytes|\bshutil\.(copy|move)|\bos\.(remove|unlink|rename|makedirs|mkdir)|\bfs\.(write|append|rm|unlink|rename|mkdir|copy)/;

/** المساراتُ التي **يكتبها** هذا الأمر — قدرَ ما يُقرأ من سطره. */
function writtenPaths(command) {
  const out = [];
  const add = (t) => {
    const p = slash(unquote(t));
    if (p) out.push(p);
  };

  // ١ — إعادةُ التوجيه في الأمر كلِّه: `> x`، `>> x` — ولا `2>&1` ولا `>&2`
  for (const m of command.matchAll(/(?<![0-9&<>])>>?(?![&|>])\s*([^\s;|&<>()]+)/g)) {
    add(m[1]);
  }

  // ٢ — الأوامرُ بأسمائها، مقطعاً مقطعاً
  for (const segment of command.split(/[\n;|&]+/)) {
    const tokens = segment.trim().split(/\s+/).filter(Boolean);
    let at = 0;
    while (at < tokens.length && /^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[at])) at += 1;
    if (at >= tokens.length) continue;
    const name = slash(unquote(tokens[at])).split("/").pop();
    const rest = tokens.slice(at + 1);
    const args = rest.filter((t) => !t.startsWith("-"));

    if (name === "tee" || ALL_TARGETS.has(name)) args.forEach(add);
    else if (DEST_LAST.has(name) && args.length) add(args[args.length - 1]);
    else if ((name === "sed" || name === "perl") && rest.some((t) => /^-[a-z]*i/.test(t)))
      args.forEach(add);
    else if (name === "dd") rest.filter((t) => t.startsWith("of=")).forEach((t) => add(t.slice(3)));
    else if (name === "git" && /^(checkout|restore|apply|clean)$/.test(unquote(rest[0] || "")))
      args.forEach(add);
    else if (INTERPRETERS.has(name) && WRITE_HINTS.test(command)) {
      // مُفسِّرٌ لا يُقرأ نصُّه: تُؤخذ كلُّ سلسلةٍ تشبه مساراً تحت `backend/`
      for (const m of command.matchAll(/[^\s'"`;|&()]*backend[/\\][^\s'"`;|&()]*/g)) add(m[0]);
    }
  }
  return out;
}

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

let ev;
try {
  ev = JSON.parse(raw);
} catch {
  allow(); // مُدخلٌ لا يُفهم لا يوقف عملَ أحد
}

const input = ev.tool_input || {};
const targets = (
  ev.tool_name === "Bash"
    ? writtenPaths(String(input.command || ""))
    : [String(input.file_path || "")]
).filter((p) => p && isBackend(p));

if (!targets.length) allow();

const session = String(ev.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "");
if (existsSync(join(GUARD, `arch-${session}`))) allow();

// **المخرجُ معلومٌ ومسجَّل**: بابٌ لا مخرجَ له يُقتلَع لا يُحترم.
if (existsSync(OFF)) {
  try {
    mkdirSync(GUARD, { recursive: true });
    appendFileSync(LOG, `${new Date().toISOString()}\t${session}\t${targets.join(" ")}\n`);
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
    "الشرطُ الأول في `CLAUDE.md`: **قبل أن تمسّ الخلفيةَ أو تضيف باباً — يُقرأ `ARCHITECTURE.md`.**",
    "",
    `ما يُكتب: ${targets.join(" · ")}`,
    "",
    "اقرأ `ARCHITECTURE.md` — بأداة `Read`، أو بأمرٍ **يُخرج محتواه** (`cat`/`sed -n`/`head`).",
    "**وذكرُ اسمه في `grep` أو `wc` أو `ls` ليس قراءةً ولا يفتح هذه البوّابة** (قِيس 2026-08-25:",
    "`grep -c 'ARCHITECTURE.md' CLAUDE.md` كان يسمها مفتوحةً وهو لا يفتح شيئاً).",
    "",
    "**وحدُّ هذه البوّابة مكتوب** — يُقرأ قبل أن تُصدَّق خضرتُها:",
    "· تمسك «لم يُقرأ» ولا تمسك «قُرئ ولم يُستعمل» — فخضرتُها ليست شهادةً على أن المعمار قُرئ.",
    "· وفي `Bash` تمسك: `>`/`>>` · `tee` · `sed -i` · `dd of=` · وجهةَ `cp`/`mv`/`ln` ·",
    "  أهدافَ `rm`/`touch`/`mkdir`/`truncate` · `git checkout|restore|apply|clean` بمسارٍ مسمّى ·",
    "  ومُفسِّراً يذكر مساراً تحت `backend/` ومعه أثرُ كتابةٍ في نصّه.",
    "· **ولا تمسك**: مُفسِّراً يبني مسارَه في متغيّر، ولا `git checkout <فرع>`، ولا `patch < diff`،",
    "  ولا كتابةً تمرّ عبر حاوية. **فلا تُقرأ خضرتُها ضماناً أن الخلفيةَ لم تُمسّ.**",
    "",
    "وللتعطيل المتعمَّد: أنشئ `.claude/.guard/OFF` — ويُسجَّل كلُّ تجاوزٍ في",
    "`.claude/.guard/bypass.log` باسم الجلسة والملفّ والوقت.",
  ].join("\n")
);
