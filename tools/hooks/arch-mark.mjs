#!/usr/bin/env node
// **يضع علامةً أن `ARCHITECTURE.md` فُتح في هذه الجلسة** — ولا يفعل شيئاً غير ذلك.
//
// وهو نصفُ الخطّاف؛ النصفُ الآخرُ `arch-gate.mjs`. وقُسم نصفين عمداً: البديلُ
// أن تقرأ البوّابةُ سجلَّ الجلسة وتفتّش فيه، **وشكلُ السجلِّ ليس عقداً** — فحارسٌ
// مبنيٌّ على شكلٍ لا يملكه يصمت يومَ يتغيّر الشكل، **وصمتُه يُقرأ سلامة**.
//
// **ويقبل القراءةَ من بابين**: أداةُ `Read`، **وأمرُ صدفةٍ يذكر الملفّ** — لأن
// أكثرَ القراءة في هذا المستودع تقع بـ`sed`/`cat` عبر `Bash`. فحصرُها في
// `Read` وحدَها يجعل البوّابةَ تصيح على من قرأ فعلاً، **وحارسٌ يصيح على سليمٍ
// يُطفأ**.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const GUARD = join(ROOT, ".claude", ".guard");

let raw = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) raw += chunk;

let ev;
try {
  ev = JSON.parse(raw);
} catch {
  process.exit(0); // لا يُعطَّل عملُ أحدٍ لأن الخطّافَ لم يفهم مُدخلَه
}

const i = ev.tool_input || {};
const haystack = [i.file_path, i.command, i.pattern, i.path].filter(Boolean).join("\n");
if (!haystack.includes("ARCHITECTURE.md")) process.exit(0);

const session = String(ev.session_id || "unknown").replace(/[^A-Za-z0-9_-]/g, "");
try {
  mkdirSync(GUARD, { recursive: true });
  writeFileSync(join(GUARD, `arch-${session}`), new Date().toISOString() + "\n");
} catch {
  // تعذّرت الكتابة: البوّابةُ ستصيح، وهذا أسلمُ من فتحها صامتة
}
process.exit(0);
