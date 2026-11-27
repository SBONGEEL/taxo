# النسخةُ تُحقَّق على الخادم أوّلاً، والحاسوبُ بعد الرفع (قرارُ المالك ٢٠٢٦-١١-٢٧، الخيار B)

## نصُّ الأمر حرفاً

> Owner decision on deploy backups (option B), combined with the resumable download:
> 1. The backup gate stays mandatory before every deploy. Change only where the deploy waits:
>    - Take the full database backup on the server first and verify it there (size, checksum, and a restore-readability check such as pg_restore --list). Keep it in a protected folder on the server (mode 600, outside any web path).
>    - Once the server copy is verified, the deploy may continue immediately, without waiting for the download to my PC.
> 2. After the deploy, download a copy of that same backup to my PC in the background:
>    - resumable: if the connection drops, continue from where it stopped, never from zero;
>    - verify the checksum at the end so the copy is complete and intact;
>    - if it still fails after retries, keep the server copy, report it, and delete nothing.
> 3. Keep the last few verified backups on the server (your choice of the number, based on disk space) and never delete a server backup before its PC copy is verified.
> 4. Rollback must still work from the server copy at gates 4 and 5.
> Conditions: do not interrupt or change the running deploy; apply this only after it finishes and before the Freemius deploy. Never skip or weaken the backup gate: a complete, verified backup must exist before any migration. No change to database data. Low memory allowed. Report in Arabic with your next report.

## لماذا — العلّةُ مقيسة

**البوّابةُ الثالثةُ كانت تنزّل النسخةَ إلى الحاسوب في الاتصال نفسِه، والرفعُ ينتظرها.** رفعُ 1573 (`518ca9ce`، ٢٦–٢٧/١١)
بقي في البوّابة الثالثة **أكثرَ من ساعةٍ ونصف** على اتصالٍ يتقطّع.

**وفيها عطبٌ أخطرُ من البطء**: `ssh_try … > "$LOCAL/bundle.tar"` — **التوجيهُ على الدالّة كلِّها**، فالملفُّ يُفتح مرّةً واحدةً
وكلُّ إعادةٍ **تُلحِق بثاً جديداً من أوّله خلف البثِّ المقطوع**. قِيس: انقطع البثُّ الأوّلُ نحو ٤٧٢ MB، فبلغ الملفُّ ٦٧٠ MB وهو
يكبر — **أرشيفٌ مقطوعٌ يليه أرشيفٌ كامل**. والذي يحمي منه أن `tar -xf` يسقط على الوسط المقطوع **فيقف الرفعُ قبل أن يمسّ شيئاً** —
آمنٌ لكنه يضيّع الساعة كلَّها، **ثمّ يبدأ الرفعُ التالي من الصفر**.

## ما بُني

**الخادم أوّلاً** (`scripts/backup-on-server.sh`):
- يعمل **منفصلاً على الخادم** (`setsid nohup`) فلا يقتله انقطاعُ ssh، **وبقفلٍ** (`flock`) فإعادةُ البدء لا تشغّل اثنين.
- يجمع **الأربعةَ نفسَها** كما كانت (القاعدة، `.env` بمحتواها، ما خارج الشجرة، غيرُ المتتبَّع، الوثائق، جلسةُ واتساب).
- يقيس هناك: `gzip -t` لكلِّ جزء، **وخاتمةُ التفريغ «PostgreSQL database dump complete»** — وهي قابليّةُ الاستعادة لتفريغٍ نصّيّ
  (`pg_restore --list` لصيغة `-Fc` وحدَها، وتفريغُنا نصّيٌّ يُستعاد بـ`psql`)، وعددُ الجداول، وأسطرُ `.env`، وبيانُ النفق، والوثائقُ مقابل
  صفوفها، وملفُّ جلسة واتساب، **والحجمُ وsha256 للحزمة**.
- يبني في `…/$STAMP.partial` ولا يسمّيه `$STAMP` إلا بعد التمام، **في `/home/taxo/backups` (المجلّد 700 والملفّات 600)** — خارج كلِّ
  مسارٍ يخدمه nginx أو الحاويات.
- **ويقف قبل أن يبدأ إن لم يتّسع القرص** (ضعفُ آخر نسخةٍ أو ٢ GB): نسخةٌ تُقطع لامتلاء القرص أسوأُ من رفعٍ لم يبدأ.

**والحكمُ على الحاسوب لا على الخادم** (`scripts/backup-judge.sh`): الخادمُ يقيس أرقاماً، **والعتباتُ نفسُها** التي كانت في البوّابة الرابعة
تحكم — فلا يُخضِّر الخادمُ نفسَه.

**والرفعُ يمضي حين تخضرّ النسخةُ على الخادم**، والرجوعُ في البوّابتين ٤ و٥ من نسخة الخادم (مطبوعٌ في كلِّ رسالة سقوط).

**والحاسوبُ بعد الرفع** (`scripts/backup-fetch.sh`): يكمل من البايت الذي وقف عنده (`tail -c +N`) **ولا يبدأ من الصفر**، ويقارن sha256
في الآخر، ثمّ يفتح الحزمةَ **ويعيد الحكمَ نفسَه على ما وصل**. وإن سقط بعد الإعادات: **نسخةُ الخادم باقية، والجزءُ المنزَّل باقٍ يُكمَل منه،
ولا يُحذف شيء**. ويُشغَّل وحدَه أيضاً: `bash scripts/backup-fetch.sh <STAMP>`.

**والاستبقاء**: تبقى على الخادم **أحدثُ ثلاث نسخٍ** (`TAXO_SERVER_KEEP`)، **ولا تُحذف نسخةٌ لم يُتحقَّق من نسختها على الحاسوب**
(علامةُ `pc-verified` لا يكتبها إلا `backup-fetch.sh` بعد مطابقة sha256) — ولا تُحذف أحدثُها أبداً.

**والاختبار**: `scripts/tests/backup-fetch.test.sh` (في `guards.sh`) — انقطاعٌ ثمّ إكمالٌ من الموضع نفسِه، وsha256 مخالفٌ لا يُعلَّم ولا
يُحذف، وإعاداتٌ تنفد فيبقى الجزء، والاستبقاءُ لا يمسّ غيرَ المُعلَّم، والحَكَمُ يُسقط ما كانت البوّابةُ الرابعةُ تُسقطه.

## الرجوعُ من نسخة الخادم (البوّابتان ٤ و٥)

كلُّ رسالة سقوطٍ بعد البوّابة الثالثة تطبع `والنسخةُ في /home/taxo/backups/<STAMP> على الخادم`. **والقاعدةُ لا تُستعاد إلا بأمر المالك**
(ترحيلةٌ سقطت تنعكس وحدَها، واستعادةُ قاعدةٍ تمحو ما كُتب بعد الختم — وقعت ٢٦/١١ ولم تُستعد). وحين يأمر:

    cd /home/taxo/backups/<STAMP> && tar -xf bundle.tar taxo.sql.gz env.tar.gz     # على الخادم، في المجلّد نفسِه (700)
    gzip -dc taxo.sql.gz | docker compose -f docker-compose.yml -f docker-compose.prod-tunnel.yml exec -T db psql -U taxo -d <قاعدةٌ فارغة>

ثمّ تُحذف الأجزاءُ المفتوحةُ من المجلّد وتبقى الحزمة. **وما على الحاسوب نسخةٌ ثانيةٌ للحال التي يسقط فيها الخادمُ نفسُه.**
