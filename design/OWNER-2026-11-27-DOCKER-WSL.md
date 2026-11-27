# Docker وWSL يُغلقان متى لم يلزما (قرارُ المالك ٢٠٢٦-١١-٢٧ — قاعدةٌ دائمة)

## نصُّ الأمر حرفاً

> Standing rule from the owner (save it in CLAUDE.md and STATE.md): to free memory, close Docker and WSL whenever you do not need them, and start them again only when you need to work on them.
> 1. Docker: after every heavy task (tests, builds, deploy steps that need it), stop Docker Desktop and release the heavy lock. Start it again only right before the next task that needs it.
> 2. WSL: shut it down (wsl --shutdown) when no work needs it, and start it again when needed. Before shutting it down, check:
>    - that you are not running inside WSL yourself, and no running command, deploy, backup download or test depends on it;
>    - that no other agent (Fawri, Miqat, iOS) or my tools are using WSL or Docker at that moment. If something is using it, do not shut it down; leave it and continue.
> 3. Never shut down Docker or WSL in the middle of a deploy, a backup, a database step or a commit. Finish or reach a safe point first.
> 4. If shutting down WSL would stop your own session (for example the repo or your tools live inside WSL), do not shut it down; only stop Docker and free memory in safe ways that do not affect other work.
> Apply from now on. Mention in each report what you closed and reopened.

## كيف يُطبَّق

- **Docker**: `docker desktop stop` وحذفُ `C:\Users\loly3\taxo-heavy.lock` بعد كلِّ عملٍ ثقيل؛ ويُبدأ (`docker desktop start`) قبيل العمل التالي الذي يحتاجه وحدَه.
  **وحاوياتُ التطوير (`taxo-app`) تبدأ وحدَها مع Docker** بسياسة إعادة التشغيل — قِيس ٢٠٢٦-١١-٢٧: بدأت `taxo-backend` و`taxo-customer-app`
  مع Docker للاختبار، **وكتبت الثانيةُ `customer-app/package-lock.json` في الشجرة الرئيسيّة** (أُعيد من git). فتُوقَف فور بدء Docker إن لم تلزم.
- **WSL**: `wsl --shutdown` حين لا يحتاجه عمل، بعد الفحوص الثلاثة: (١) لا أمرَ ولا رفعَ ولا تنزيلَ نسخةٍ ولا اختبارَ يعتمد عليه؛
  (٢) لا وكيلَ آخرَ ولا جلسةَ تستعمله (Fawri · Miqat · iOS · **أيُّ جلسة tmux يعمل فيها claude**) — وإلا يُترك ويُمضى؛ (٣) جلسةُ الوكيل نفسُه
  لا تتوقّف به. **ومن الأمر الثاني (أدناه): المستودعُ في WSL لا يُبقيه مفتوحاً بين الخطوات** — يُغلق بعد كلِّ خطوة Docker متى لم يجرِ
  فيه رفعٌ ولا تنزيلُ نسخةٍ ولا إيداعٌ ولا اختبارٌ ولا سكربت، ويُعاد حين تحتاجه الخطوةُ التالية.
- **ولا إغلاقَ وسطَ رفعٍ أو نسخةٍ أو خطوةِ قاعدةٍ أو إيداع.**
- **وكلُّ تقريرٍ يذكر ما أُغلق وما أُعيد فتحُه.**

## الأمرُ الثاني حرفاً (٢٠٢٦-١١-٢٧ ‏~14:00Z) — يعلو على ما قبله حيث يختلفان

> 1. Check the tmux session "miqat" inside WSL: is the claude program running in it right now?
> 2. If it is empty (only a shell prompt, no claude running): close that tmux session.
> 3. If claude is running in it: do not touch it, keep WSL as it is, and tell me.
> 4. TAXO too: when TAXO work does not need WSL at that moment (no deploy, backup download, commit, test or script running in it), shut WSL down (wsl --shutdown) after each Docker step, the same way you close Docker. Start it again only when the next TAXO step needs it.
> 5. Before every WSL shutdown, check that no other agent or session is using WSL (Fawri, Miqat, iOS, any running tmux session with claude). If anything is using it, leave WSL running and continue.
> 6. Never shut WSL down in the middle of a deploy, a backup, a database step or a commit, and never if your own session or tools would stop because of it.
> 7. Update your memory and CLAUDE.md with this rule.
> Conditions: do not close anything else, and do not touch the folder D:\prj\miqat. Mention in each report what you closed and reopened.

### ما نُفّذ

- **جلسةُ `miqat` فُحصت ١٤:٠٢Z فكانت فارغة**: آخرُ ما فيها `Trust D:\prj\miqat? [y/N] [remote-control exited: 0]` ثمّ مِحثُّ bash بلا ابن —
  `claude.exe remote-control` خرج عند سؤال الثقة ولم يعمل. **فأُغلقت** (`tmux kill-session -t miqat`) بعد إعادة الفحص في الأمر نفسِه.
  ولم يُمسّ `D:\prj\miqat`، ولا بناءُ Gradle الجاري له على ويندوز، ولا جلساتُ claude الأخرى.
- **وفحصُ ما قبل كلِّ إغلاق**: `tmux list-sessions` وما يجري في كلِّ لوحة (`pane_current_command` وأبناؤه)؛ و`ps` داخل WSL لكلِّ ما ليس
  من النظام؛ وعمليّاتُ `wsl.exe` على ويندوز وآباؤها — **عمليّةُ `wsl.exe` لغير هذا الوكيل ⇐ لا إغلاق**.
