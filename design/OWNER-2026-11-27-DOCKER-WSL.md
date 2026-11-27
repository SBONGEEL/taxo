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
  (٢) لا وكيلَ آخرَ ولا أداةَ للمالك تستعمله (جلسةُ tmux ‏`miqat` قائمة ⇐ لا إغلاق)؛ (٣) جلسةُ الوكيل نفسُه لا تحتاجه — **ومستودعُ TAXO وأدواتُ
  الرفع في WSL**، فما دام عملٌ في المستودع جارياً أو قريباً يبقى، ويُغلق Docker وحدَه.
- **ولا إغلاقَ وسطَ رفعٍ أو نسخةٍ أو خطوةِ قاعدةٍ أو إيداع.**
- **وكلُّ تقريرٍ يذكر ما أُغلق وما أُعيد فتحُه.**
